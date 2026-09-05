"""基于 schema 的抽取器。

当前版本使用规则 + 可插拔 LLM 接口的方式。
这版的目标是 Stage 1 稳定 baseline：
1. 不把批次误当 Category；
2. 不把地名误当 ProtectionUnit；
3. 尽量从正文里挖到文化元素；
4. 保留完整 provenance，方便答辩解释。
"""

from __future__ import annotations

import html
import json
import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .graph_ops import deduplicate_result
from .ontology import ONTOLOGY_V1
from .resolver import correct_entity_type, looks_like_protection_unit, looks_like_region, normalize_region_name
from .schemas import EntityRecord, ExtractionResult, Provenance, RelationRecord


SUPPORTED_HERITAGE_CATEGORIES = frozenset(
    {
        "民间文学",
        "传统音乐",
        "传统舞蹈",
        "传统戏剧",
        "曲艺",
        "传统体育、游艺与杂技",
        "传统美术",
        "传统技艺",
        "传统医药",
        "民俗",
    }
)

REGION_SUFFIXES = (
    "维吾尔自治区",
    "回族自治区",
    "壮族自治区",
    "自治区",
    "特别行政区",
    "自治州",
    "自治县",
    "省",
    "市",
    "区",
    "县",
    "旗",
    "盟",
)

ORG_HINTS = (
    "保护中心",
    "保护管理办公室",
    "保护管理中心",
    "文化馆",
    "博物馆",
    "纪念馆",
    "研究院",
    "研究所",
    "传习所",
    "传承中心",
    "非遗中心",
    "非物质文化遗产保护中心",
    "文化中心",
    "艺术团",
    "剧团",
    "学校",
    "学院",
    "大学",
    "协会",
    "学会",
    "委员会",
    "管理局",
    "办公室",
    "局",
    "馆",
    "所",
    "院",
    "中心",
)

BATCH_MARKERS = (
    "第一批",
    "第二批",
    "第三批",
    "第四批",
    "第五批",
    "第六批",
    "第七批",
    "第八批",
    "第九批",
    "第十批",
)

LLM_TEMPERATURE = 0.15

EXTRACTION_PROMPT = """你是一个非遗知识图谱抽取器，必须严格遵守以下规则：
1. Region 只允许表示行政地域，例如省、市、区、县、自治州、自治县，不是机构。
2. ProtectionUnit 只允许表示保护机构，例如文化馆、保护中心、博物馆、传习所等组织，绝对不能是地名。
3. Category 只允许表示非遗门类，例如民间文学、传统音乐、传统舞蹈、传统戏剧、曲艺、传统体育、游艺与杂技、传统美术、传统技艺、传统医药、民俗。
4. 第一批、第二批、第三批、2006、2011 等批次信息不属于 Category，禁止写入 Category。
5. CulturalElement 要尽可能多提取项目的文化要素，但必须和原文证据一致。
6. 所有实体和关系必须输出为合法 JSON，禁止输出解释性文字。

输出时优先遵守 schema，不确定时宁可少抽，不要乱抽。
温度参数：{temperature}
"""


@dataclass(frozen=True)
class SourceContext:
    document_id: str
    source_name: str
    source_url: str
    heritage_category: str | None
    batch_label: str | None
    region: str
    protection_unit: str
    raw_category_name: str | None
    raw_type: str | None
    retrieved_at: str
    evidence_text: str


@dataclass(frozen=True)
class RawMetadata:
    document_id: str
    source_name: str
    heritage_category: str | None
    batch_label: str | None
    region: str
    protection_unit: str
    raw_category_name: str | None
    raw_type: str | None
    source_url: str
    retrieved_at: str
    score: int


def _clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = text.replace("\r", "\n")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _document_id_from_key(key: str) -> str:
    return f"ihchina_{hashlib.md5(key.encode('utf-8')).hexdigest()[:12]}"


def _extract_batch_label(*texts: str) -> str:
    for text in texts:
        if not text:
            continue
        m = re.search(r"第[一二三四五六七八九十]+批", text)
        if m:
            return m.group(0)
    return ""


def _score_raw_metadata(meta: RawMetadata) -> int:
    score = 0
    if meta.heritage_category:
        score += 10
    if meta.protection_unit:
        score += 3
    if meta.region:
        score += 3
    if meta.raw_type:
        score += 2
    if meta.batch_label:
        score += 1
    if meta.source_name:
        score += 1
    if meta.raw_category_name and meta.raw_category_name not in BATCH_MARKERS:
        score += 1
    return score


def _derive_heritage_category(raw_type: str, category_name: str) -> str:
    for cand in (raw_type, category_name):
        cand = (cand or "").strip()
        if cand in SUPPORTED_HERITAGE_CATEGORIES:
            return cand
    return ""


def _build_raw_metadata_index() -> dict[str, RawMetadata]:
    """把 raw manifest 建成 document_id -> 元数据的索引。"""
    root = Path(__file__).resolve().parent.parent / "data" / "raw"
    index: dict[str, RawMetadata] = {}

    if not root.exists():
        return index

    manifests = sorted(root.glob("category_*/manifest.jsonl"))
    for manifest in manifests:
        if not manifest.exists():
            continue
        for line in manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            project_data = record.get("project_data") or {}
            project_num = str(project_data.get("project_num") or "").strip()
            title = str(project_data.get("title") or record.get("project_name") or "").strip()
            doc_key = project_num or title
            if not doc_key:
                continue
            document_id = _document_id_from_key(doc_key)
            raw_type = str(project_data.get("type") or "").strip()
            raw_category_name = str(record.get("category_name") or "").strip()
            heritage_category = _derive_heritage_category(raw_type, raw_category_name)
            region = str(project_data.get("province") or project_data.get("unit") or "").strip()
            protection_unit = str(project_data.get("protect_unit") or "").strip()
            batch_label = _extract_batch_label(str(project_data.get("rx_time") or ""), raw_category_name)
            source_url = f"https://www.ihchina.cn/project/{project_data.get('id', '')}"
            retrieved_at = str(record.get("retrieved_at") or "").strip()
            meta = RawMetadata(
                document_id=document_id,
                source_name=title,
                heritage_category=heritage_category or None,
                batch_label=batch_label or None,
                region=region,
                protection_unit=protection_unit,
                raw_category_name=raw_category_name or None,
                raw_type=raw_type or None,
                source_url=source_url,
                retrieved_at=retrieved_at,
                score=0,
            )
            meta = RawMetadata(**{**meta.__dict__, "score": _score_raw_metadata(meta)})
            existing = index.get(document_id)
            if existing is None or meta.score > existing.score:
                index[document_id] = meta
    return index


def _raw_metadata_for_chunk(chunk: dict) -> RawMetadata | None:
    doc_id = str(chunk.get("document_id") or "").strip()
    if not doc_id:
        return None
    return _RAW_METADATA_INDEX.get(doc_id)


_RAW_METADATA_INDEX = _build_raw_metadata_index()


def _chunk_provenance(chunk: dict) -> Provenance:
    return Provenance(
        source_url=chunk.get("source_url", ""),
        document_id=chunk.get("document_id", ""),
        chunk_id=chunk.get("chunk_id", ""),
        retrieved_at=chunk.get("retrieved_at", ""),
        source_name=chunk.get("source_name"),
        source_category=chunk.get("source_category"),
        source_region=chunk.get("source_region"),
        source_org=chunk.get("source_org"),
        source_batch=chunk.get("source_batch"),
        evidence_text=_clean_text(chunk.get("content", "")),
    )


def _entity_key(entity_type: str, name: str, canonical_name: str | None = None, attrs: dict | None = None) -> str:
    key = (canonical_name or name or "").strip()
    attrs = attrs or {}
    if entity_type == "InheritProject":
        document_id = str(attrs.get("document_id") or "").strip()
        if document_id:
            return document_id
        project_number = str(attrs.get("project_number") or "").strip()
        if project_number:
            return project_number
    if entity_type == "Region":
        return normalize_region_name(key)
    if entity_type == "ProtectionUnit":
        return re.sub(r"\s+", "", key)
    if entity_type == "Category":
        return key
    return key


def _entity(
    entity_type: str,
    name: str,
    provenance: Provenance,
    *,
    canonical_name: str | None = None,
    aliases=None,
    attrs=None,
) -> EntityRecord:
    entity_type, _ = correct_entity_type(name, entity_type)
    attrs = dict(attrs or {})
    canon = canonical_name or name
    eid = f"{entity_type}:{_entity_key(entity_type, name, canon, attrs)}"
    return EntityRecord(
        entity_id=eid,
        entity_type=entity_type,  # type: ignore[arg-type]
        name=name,
        canonical_name=canon,
        aliases=list(aliases or []),
        attributes=attrs,
        provenance=[provenance],
    )


def _entity_id(entity_type: str, name: str, attrs: dict | None = None) -> str:
    entity_type, _ = correct_entity_type(name, entity_type)
    attrs = dict(attrs or {})
    return f"{entity_type}:{_entity_key(entity_type, name, attrs=attrs)}"


def _project_entity_id(ctx: SourceContext) -> str:
    return _entity_id("InheritProject", ctx.source_name, attrs={"document_id": ctx.document_id or ctx.source_name})


def _relation(
    relation_type: str,
    source: str,
    target: str,
    provenance: Provenance,
    *,
    confidence: float = 0.9,
    attrs=None,
) -> RelationRecord:
    return RelationRecord(
        relation_type=relation_type,  # type: ignore[arg-type]
        source_entity_id=source,
        target_entity_id=target,
        confidence=confidence,
        provenance=[provenance],
        attributes=dict(attrs or {}),
    )


def _extract_category(chunk: dict, ctx: SourceContext) -> str:
    """优先识别真实门类，识别不到就返回空。"""
    candidates = [
        (ctx.heritage_category or "").strip(),
        str(chunk.get("heritage_category") or "").strip(),
        str(chunk.get("source_category") or "").strip(),
        str(chunk.get("raw_category_name") or "").strip(),
        str(chunk.get("category_name") or "").strip(),
        str(chunk.get("source_type") or "").strip(),
    ]
    for cand in candidates:
        if not cand:
            continue
        if cand in SUPPORTED_HERITAGE_CATEGORIES:
            return cand
        if cand in BATCH_MARKERS:
            continue
        if any(marker in cand for marker in BATCH_MARKERS):
            continue
        if cand.isdigit():
            continue
        if len(cand) <= 2 and cand not in SUPPORTED_HERITAGE_CATEGORIES:
            continue
        if cand in {"新增项目", "扩展项目", "代表性项目", "保护单位"}:
            continue
        if "批" in cand:
            continue
        if cand in SUPPORTED_HERITAGE_CATEGORIES:
            return cand
    return ""


def _split_regions(text: str) -> list[str]:
    text = _clean_text(text)
    if not text:
        return []
    parts = re.split(r"[，,、;；\s]+", text)
    regions = []
    for part in parts:
        cand = part.strip()
        if not cand:
            continue
        if looks_like_protection_unit(cand):
            continue
        if looks_like_region(cand):
            regions.append(cand)
    return list(dict.fromkeys(regions))


def _split_protection_units(text: str) -> list[str]:
    text = _clean_text(text)
    if not text:
        return []
    parts = re.split(r"[，,、;；\s]+", text)
    units = []
    for part in parts:
        cand = part.strip()
        if not cand:
            continue
        if looks_like_region(cand):
            continue
        if looks_like_protection_unit(cand):
            units.append(cand)
    return list(dict.fromkeys(units))


def _looks_like_cultural_element(text: str) -> bool:
    if not text or len(text) < 2:
        return False
    if looks_like_region(text) or looks_like_protection_unit(text) or text in SUPPORTED_HERITAGE_CATEGORIES:
        return False
    return True


def _find_keyword_entities(text: str) -> list[str]:
    """保守但比旧版更宽一些的文化元素抽取。"""
    text = _clean_text(text)
    keywords = [
        "刺绣",
        "织锦",
        "剪纸",
        "木雕",
        "泥塑",
        "陶瓷",
        "戏曲",
        "舞蹈",
        "音乐",
        "服饰",
        "技艺",
        "说唱",
        "吟唱",
        "歌舞",
        "祭祀",
        "婚俗",
        "节庆",
        "礼仪",
        "木版",
        "年画",
        "皮影",
        "雕版",
        "乐器",
        "方言",
        "神话",
        "传说",
        "面具",
        "鼓舞",
        "农耕",
        "口头文学",
        "民歌",
        "民间故事",
        "舞龙",
        "舞狮",
        "刺绣艺术",
        "宗教仪式",
    ]
    candidates: list[str] = []
    for kw in keywords:
        if kw in text:
            candidates.append(kw)

    # 额外抓取少量“X舞 / X歌 / X绣 / X戏”等模式，提升 recall
    for m in re.finditer(r"[\u4e00-\u9fff]{2,8}(?:舞|歌|绣|戏|画|曲|书法|木版年画|年画|剪纸|刺绣)", text):
        cand = m.group(0)
        if _looks_like_cultural_element(cand):
            candidates.append(cand)

    return list(dict.fromkeys(candidates))


def _source_context_from_chunk(chunk: dict) -> SourceContext:
    content = _clean_text(chunk.get("content", ""))
    source_region = str(chunk.get("source_region") or "").strip()
    source_org = str(chunk.get("source_org") or "").strip()
    raw_category_name = str(chunk.get("source_category") or "").strip()
    batch_label = str(chunk.get("source_batch") or "").strip()
    raw_meta = _raw_metadata_for_chunk(chunk)
    heritage_category = ""
    if raw_meta and raw_meta.heritage_category:
        heritage_category = raw_meta.heritage_category
    if not heritage_category:
        for key in ("heritage_category", "raw_type", "source_type"):
            cand = str(chunk.get(key) or "").strip()
            if cand in SUPPORTED_HERITAGE_CATEGORIES:
                heritage_category = cand
                break
    if not heritage_category and raw_category_name in SUPPORTED_HERITAGE_CATEGORIES:
        heritage_category = raw_category_name
    if raw_meta:
        if raw_meta.region:
            source_region = raw_meta.region
        if raw_meta.protection_unit:
            source_org = raw_meta.protection_unit
        if raw_meta.batch_label:
            batch_label = raw_meta.batch_label
    return SourceContext(
        document_id=str(raw_meta.document_id if raw_meta else chunk.get("document_id") or ""),
        source_name=str(chunk.get("source_name") or ""),
        source_url=str(raw_meta.source_url if raw_meta else chunk.get("source_url") or ""),
        heritage_category=heritage_category or None,
        batch_label=batch_label or None,
        region=source_region,
        protection_unit=source_org,
        raw_category_name=(raw_meta.raw_category_name if raw_meta and raw_meta.raw_category_name else raw_category_name) or None,
        raw_type=(raw_meta.raw_type if raw_meta and raw_meta.raw_type else str(chunk.get("source_type") or "").strip()) or None,
        retrieved_at=str(raw_meta.retrieved_at if raw_meta else chunk.get("retrieved_at") or ""),
        evidence_text=content,
    )


def extract_from_chunk(chunk: dict) -> ExtractionResult:
    """从单个 chunk 里做可解释抽取。"""
    prov = _chunk_provenance(chunk)
    ctx = _source_context_from_chunk(chunk)
    content = _clean_text(chunk.get("content", ""))
    result = ExtractionResult()

    if not content:
        result.warnings.append(f"{chunk.get('chunk_id')} 为空")
        return result

    raw_meta = _raw_metadata_for_chunk(chunk)
    source_name = ctx.source_name or (raw_meta.source_name if raw_meta else "")
    if not source_name:
        result.warnings.append(f"{chunk.get('chunk_id')} 缺少 source_name")
        return result

    # 根节点始终保底
    project_entity_id = _project_entity_id(ctx)
    project_attrs = {
        "project_number": _match_line(content, "项目编号") or chunk.get("source_number", ""),
        "batch": ctx.batch_label or "",
        "heritage_category": ctx.heritage_category or "",
        "raw_category_name": ctx.raw_category_name or "",
        "document_id": ctx.document_id or chunk.get("document_id", ""),
    }

    result.entities.append(
        _entity(
            "InheritProject",
            source_name,
            prov,
            attrs=project_attrs,
        )
    )

    category = _extract_category(chunk, ctx)
    if category:
        result.entities.append(_entity("Category", category, prov))
        result.relations.append(
            _relation("BELONGS_TO", project_entity_id, _entity_id("Category", category), prov)
        )

    if ctx.region:
        for region in _split_regions(ctx.region):
            result.entities.append(
                _entity("Region", region, prov, aliases=[_normalize_region(region)])
            )
            result.relations.append(
                _relation("LOCATED_IN", project_entity_id, _entity_id("Region", region), prov)
            )

    if ctx.protection_unit:
        for unit in _split_protection_units(ctx.protection_unit):
            result.entities.append(_entity("ProtectionUnit", unit, prov))
            result.relations.append(
                _relation("PROTECTED_BY", project_entity_id, _entity_id("ProtectionUnit", unit), prov)
            )

    # 详情内容里继续挖文化元素、技艺和表现形式
    if chunk.get("chunk_type") == "detail_content":
        elements = _find_keyword_entities(content)
        for name in elements:
            result.entities.append(_entity("CulturalElement", name, prov))
            result.relations.append(
                _relation(
                    "RELATED_TO",
                    project_entity_id,
                    _entity_id("CulturalElement", name),
                    prov,
                    confidence=0.72,
                )
            )

    # 再从正文做一次轻量扫描，尽量提高 CulturalElement recall
    if chunk.get("chunk_type") in {"basic_info", "detail_content"}:
        extra_names = []
        for pattern in (
            r"[\u4e00-\u9fff]{2,8}舞",
            r"[\u4e00-\u9fff]{2,8}歌",
            r"[\u4e00-\u9fff]{2,8}绣",
            r"[\u4e00-\u9fff]{2,8}戏",
            r"[\u4e00-\u9fff]{2,8}画",
            r"[\u4e00-\u9fff]{2,8}曲",
            r"[\u4e00-\u9fff]{2,8}书法",
            r"[\u4e00-\u9fff]{2,8}木版年画",
            r"[\u4e00-\u9fff]{2,8}皮影",
        ):
            for match in re.findall(pattern, content):
                if _looks_like_cultural_element(match):
                    extra_names.append(match)
        for name in list(dict.fromkeys(extra_names)):
            result.entities.append(_entity("CulturalElement", name, prov))
            result.relations.append(
                _relation(
                    "RELATED_TO",
                    project_entity_id,
                    _entity_id("CulturalElement", name),
                    prov,
                    confidence=0.6,
                )
            )

    # 始终保底写入项目节点，保证图上有根节点
    has_project = any(e.entity_id == project_entity_id for e in result.entities)
    if not has_project:
        result.entities.insert(0, _entity("InheritProject", source_name, prov, attrs=project_attrs))

    return result


def _match_line(content: str, prefix: str) -> str:
    pattern = rf"{re.escape(prefix)}[:：]\s*([^\n]+)"
    m = re.search(pattern, content)
    return m.group(1).strip() if m else ""


def _normalize_region(region: str) -> str:
    return normalize_region_name(region)


def extract_chunks(chunks: Iterable[dict]) -> ExtractionResult:
    merged = ExtractionResult()
    for chunk in chunks:
        one = extract_from_chunk(chunk)
        merged.entities.extend(one.entities)
        merged.relations.extend(one.relations)
        merged.warnings.extend(one.warnings)
    return merged


def extract_chunks_deduped(chunks: Iterable[dict]) -> ExtractionResult:
    return deduplicate_result(extract_chunks(chunks))


def load_chunks(jsonl_path: str | Path) -> list[dict]:
    path = Path(jsonl_path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def result_to_json(result: ExtractionResult) -> dict:
    return {
        "ontology": {
            "nodes": list(ONTOLOGY_V1.node_types),
            "relations": list(ONTOLOGY_V1.relation_types),
        },
        "entities": [asdict(entity) for entity in result.entities],
        "relations": [asdict(relation) for relation in result.relations],
        "warnings": list(result.warnings),
    }
