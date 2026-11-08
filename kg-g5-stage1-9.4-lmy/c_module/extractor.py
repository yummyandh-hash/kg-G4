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

PROJECT_NUMBER_CATEGORY_PREFIXES = {
    "Ⅰ": "民间文学",
    "I": "民间文学",
    "Ⅱ": "传统音乐",
    "II": "传统音乐",
    "Ⅲ": "传统舞蹈",
    "III": "传统舞蹈",
    "Ⅳ": "传统戏剧",
    "IV": "传统戏剧",
    "Ⅴ": "曲艺",
    "V": "曲艺",
    "Ⅵ": "传统体育、游艺与杂技",
    "VI": "传统体育、游艺与杂技",
    "Ⅶ": "传统美术",
    "VII": "传统美术",
    "Ⅷ": "传统技艺",
    "VIII": "传统技艺",
    "Ⅸ": "传统医药",
    "IX": "传统医药",
    "Ⅹ": "民俗",
    "X": "民俗",
}

NON_CATEGORY_TOKENS = frozenset(
    {
        "新增项目",
        "扩展项目",
        "代表性项目",
        "保护单位",
        "国家级",
        "国家级非物质文化遗产代表性项目",
    }
)

CULTURAL_FRAGMENT_PREFIXES = (
    "共有",
    "多则",
    "少则",
    "受",
    "使",
    "亦",
    "又",
    "也",
    "仍",
    "一种",
    "另一种",
    "而另一种",
    "再一种",
    "单纯",
    "大量",
    "重要",
    "原始",
    "优秀",
    "大型",
    "大凡",
    "堪称",
    "博采",
    "兼收",
    "融入",
    "糅进",
    "糅合",
    "吸纳",
    "纳入",
    "展现",
    "体现",
    "反映",
    "展开",
    "融合",
    "中华",
    "中国",
    "全国",
    "地方",
    "各地",
    "各类",
    "民族",
    "民间",
    "传统",
    "早期",
    "目前",
    "古代",
    "后来",
    "现代",
    "当代",
    "当时",
    "此外",
    "然后",
    "同时",
    "其",
    "这",
    "该",
    "在",
    "有",
    "以",
    "最后",
    "接下来",
    "一般",
    "着",
    "种",
    "要",
    "男女",
    "多人",
    "青年",
)

CULTURAL_FRAGMENT_MARKERS = (
    "一种是",
    "另一种",
    "热烈而丰富",
    "热烈",
    "丰富",
    "共有",
    "多则",
    "少则",
    "基础上",
    "组建",
    "吸取",
    "吸收",
    "保留",
    "形成",
    "演变",
    "发展",
    "培养",
    "传入",
    "传到",
    "继承",
    "改革了",
    "身体随着",
    "便出现",
    "含打闹",
    "手拉手",
    "轻盈踏地",
    "燃点篝火",
    "围之起舞",
    "我国",
    "致习",
    "树跳",
    "初具",
    "初具戏曲",
    "全曲",
    "随着",
    "西藏族",
    "东民间",
    "南岸彝族",
    "传统舞",
    "传统歌",
    "传统戏",
    "传统曲",
    "传统画",
    "民间",
    "表演",
    "演出",
    "活动",
    "形式",
    "内容",
    "进行",
    "包括",
    "群众性",
    "参加",
    "令人",
    "压阵",
    "最后压阵",
    "接下来是",
    "一般有",
    "都是",
    "为内容",
    "以...为",
    "借鉴",
    "作为",
    "并用",
    "是中国",
    "中国",
    "五大",
    "发展",
    "成为",
    "表演",
    "演出",
    "活动",
    "形式",
    "内容",
    "群众性",
    "影响",
    "传承",
    "流传",
    "起源",
    "创作",
    "创编",
    "借鉴",
    "发展",
    "结合",
    "逐渐",
    "逐步",
    "采用",
    "包括",
    "单纯",
    "唱支",
    "一大批",
)

CULTURAL_FRAGMENT_TOKENS = frozenset(
    {
        "在",
        "是",
        "和",
        "了",
        "着",
        "个",
        "一起",
        "对于",
        "或",
        "把",
        "将",
        "由",
        "用",
        "从",
        "向",
        "到",
        "被",
        "于",
        "为",
        "以",
        "及",
        "与",
        "等",
        "所",
        "对",
    }
)

CULTURAL_SUFFIX_CONTINUATIONS = {
    "舞": frozenset({"蹈"}),
    "歌": frozenset({"舞"}),
    "戏": frozenset({"曲"}),
    "曲": frozenset({"艺"}),
    "影": frozenset({"戏", "剧"}),
    "木偶": frozenset({"戏", "剧"}),
    "皮影": frozenset({"戏", "剧"}),
}

CULTURAL_CORE_TERMS = (
    "刺绣艺术",
    "民间故事",
    "口头文学",
    "秧歌戏",
    "皮影戏",
    "木偶戏",
    "调腔",
    "调声",
    "铜鼓舞",
    "摆手舞",
    "喇叭戏",
    "目连戏",
    "花鼓戏",
    "宗教仪式",
    "歌舞",
    "戏曲",
    "舞蹈",
    "音乐",
    "服饰",
    "技艺",
    "说唱",
    "吟唱",
    "祭祀",
    "婚俗",
    "节庆",
    "礼仪",
    "木版",
    "年画",
    "皮影",
    "雕版",
    "乐器",
    "神话",
    "传说",
    "面具",
    "鼓舞",
    "农耕",
    "民歌",
    "舞龙",
    "舞狮",
    "山歌",
    "秧歌",
    "打闹歌",
    "花灯",
    "号子",
    "刺绣",
    "织锦",
    "剪纸",
    "木雕",
    "泥塑",
    "陶瓷",
)

CULTURAL_CORE_TERM_SET = frozenset(CULTURAL_CORE_TERMS)

LLM_TEMPERATURE = 0.15

EXTRACTION_PROMPT = """你是一个非遗知识图谱抽取器，必须严格遵守以下规则：
1. Region 只允许表示行政地域，例如省、市、区、县、自治州、自治县，不是机构。
2. ProtectionUnit 只允许表示保护机构，例如文化馆、保护中心、博物馆、传习所等组织，绝对不能是地名。
3. Category 只允许表示非遗门类，例如民间文学、传统音乐、传统舞蹈、传统戏剧、曲艺、传统体育、游艺与杂技、传统美术、传统技艺、传统医药、民俗。
4. 第一批、第二批、第三批、2006、2011 等批次信息不属于 Category，禁止写入 Category。
5. CulturalElement 只允许抽取名词或名词短语，禁止抽取完整句子、动词短语、过渡句、解释句、描述句。
   像“一种是以舞...”“改革了秧歌...”“在村寨以外举行”“手拉手轻盈踏地起舞”这类碎片一律不要输出。
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
    for text in texts:
        if not text:
            continue
        m = re.search(r"(?:19|20)\d{2}", text)
        if m:
            return m.group(0)
    return ""


def _looks_like_batch_label(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    if any(marker in text for marker in BATCH_MARKERS):
        return True
    if re.fullmatch(r"(?:19|20)\d{2}", text):
        return True
    if "批" in text:
        return True
    return False


def _clean_heritage_category(text: str) -> str:
    cand = (text or "").strip()
    if cand in SUPPORTED_HERITAGE_CATEGORIES:
        return cand
    return ""


def _clean_raw_category_name(text: str) -> str:
    cand = (text or "").strip()
    if not cand:
        return ""
    if _looks_like_batch_label(cand):
        return ""
    if cand in NON_CATEGORY_TOKENS:
        return ""
    if cand in SUPPORTED_HERITAGE_CATEGORIES:
        return cand
    for category in SUPPORTED_HERITAGE_CATEGORIES:
        if category in cand:
            return category
    return ""


def _first_heritage_category(*texts: str) -> str:
    for text in texts:
        category = _clean_heritage_category(text)
        if category:
            return category
    return ""


def _category_from_project_number(project_number: str) -> str:
    text = (project_number or "").strip()
    if not text:
        return ""
    first_token = re.split(r"[-_—\s]+", text, maxsplit=1)[0].strip().upper()
    if not first_token:
        return ""
    return PROJECT_NUMBER_CATEGORY_PREFIXES.get(first_token, "")


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
    if meta.raw_category_name and not _looks_like_batch_label(meta.raw_category_name):
        score += 1
    return score


def _derive_heritage_category(raw_type: str, category_name: str) -> str:
    return _first_heritage_category(raw_type, category_name)


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
            manifest_category_name = str(record.get("category_name") or "").strip()
            raw_category_name = _clean_raw_category_name(manifest_category_name)
            heritage_category = _derive_heritage_category(raw_type, raw_category_name)
            region = str(project_data.get("province") or project_data.get("unit") or "").strip()
            protection_unit = str(project_data.get("protect_unit") or "").strip()
            batch_label = _extract_batch_label(str(project_data.get("rx_time") or ""), manifest_category_name)
            if heritage_category and raw_category_name and heritage_category != raw_category_name:
                raw_category_name = heritage_category
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


def _chunk_provenance(chunk: dict, ctx: SourceContext | None = None) -> Provenance:
    source_category = ctx.heritage_category if ctx else _first_heritage_category(
        str(chunk.get("heritage_category") or ""),
        str(chunk.get("source_type") or ""),
        str(chunk.get("raw_type") or ""),
        str(chunk.get("source_category") or ""),
        str(chunk.get("raw_category_name") or ""),
        _category_from_project_number(_match_line(_clean_text(chunk.get("content", "")), "项目编号")),
    )
    source_batch = ctx.batch_label if ctx else _extract_batch_label(
        str(chunk.get("source_category") or ""),
        str(chunk.get("raw_category_name") or ""),
        str(chunk.get("source_batch") or ""),
        str(chunk.get("batch") or ""),
        _clean_text(chunk.get("content", "")),
    )
    return Provenance(
        source_url=chunk.get("source_url", ""),
        document_id=chunk.get("document_id", ""),
        chunk_id=chunk.get("chunk_id", ""),
        retrieved_at=chunk.get("retrieved_at", ""),
        source_name=chunk.get("source_name"),
        source_category=source_category or None,
        source_region=chunk.get("source_region"),
        source_org=chunk.get("source_org"),
        source_batch=source_batch or None,
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
    project_number = _match_line(_clean_text(chunk.get("content", "")), "项目编号") or str(
        chunk.get("source_number") or chunk.get("number") or ""
    )
    return _first_heritage_category(
        (ctx.heritage_category or "").strip(),
        str(chunk.get("heritage_category") or "").strip(),
        str(chunk.get("raw_category_name") or "").strip(),
        str(chunk.get("source_type") or "").strip(),
        str(chunk.get("raw_type") or "").strip(),
        str(chunk.get("source_category") or "").strip(),
        str(chunk.get("category_name") or "").strip(),
        _category_from_project_number(project_number),
    )


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


def _looks_like_cultural_element(
    text: str,
    *,
    source_text: str | None = None,
    span: tuple[int, int] | None = None,
) -> bool:
    if not text or len(text) < 2:
        return False
    if looks_like_region(text) or looks_like_protection_unit(text) or text in SUPPORTED_HERITAGE_CATEGORIES:
        return False
    if text in CULTURAL_CORE_TERM_SET:
        return True
    if "的" in text:
        return False
    if "方言" in text and len(text) > 2:
        return False
    if any(text.startswith(prefix) for prefix in CULTURAL_FRAGMENT_PREFIXES):
        return False
    if any(marker in text for marker in CULTURAL_FRAGMENT_MARKERS):
        return False
    if any(token in text for token in CULTURAL_FRAGMENT_TOKENS):
        return False
    if source_text is not None and span is not None:
        start, end = span
        if 0 <= start < end <= len(source_text):
            right = source_text[end : end + 1]
            for suffix, continuations in CULTURAL_SUFFIX_CONTINUATIONS.items():
                if text.endswith(suffix) and right and right in continuations:
                    return False
    if len(text) > 8:
        return False
    if len(text) < 3 and text not in {"歌", "舞", "戏", "曲", "绣", "画"}:
        return False
    if len(text) <= 4 and text[0] in {"共", "础", "多", "态", "东", "南", "岭", "塘", "永"}:
        return False
    if len(text) <= 5 and text.endswith(("的", "地", "在", "以", "为", "和", "与", "或", "用", "由", "从", "向", "于")):
        return False
    return True


def _find_keyword_entities(text: str) -> list[str]:
    """保守但比旧版更宽一些的文化元素抽取。"""
    text = _clean_text(text)
    candidates: list[str] = []
    for kw in CULTURAL_CORE_TERMS:
        for m in re.finditer(re.escape(kw), text):
            if _looks_like_cultural_element(kw, source_text=text, span=m.span()):
                candidates.append(kw)
                break

    # 额外抓取少量“X舞 / X歌 / X绣 / X戏”等模式，提升 recall
    for m in re.finditer(r"[\u4e00-\u9fff]{2,6}(?:舞|歌|绣|戏|画|曲|书法|木版年画|年画|剪纸|刺绣)", text):
        cand = m.group(0)
        if _looks_like_cultural_element(cand, source_text=text, span=m.span()):
            candidates.append(cand)

    return list(dict.fromkeys(candidates))


def _source_context_from_chunk(chunk: dict) -> SourceContext:
    content = _clean_text(chunk.get("content", ""))
    source_region = str(chunk.get("source_region") or "").strip()
    source_org = str(chunk.get("source_org") or "").strip()
    raw_meta = _raw_metadata_for_chunk(chunk)
    project_number = _match_line(content, "项目编号") or str(chunk.get("source_number") or chunk.get("number") or "")
    chunk_raw_category_name = _clean_raw_category_name(
        str(chunk.get("raw_category_name") or chunk.get("category_name") or chunk.get("source_category") or "")
    )
    source_category = str(chunk.get("source_category") or "").strip()
    heritage_category = _first_heritage_category(
        str(chunk.get("heritage_category") or "").strip(),
        str(chunk.get("source_type") or "").strip(),
        str(chunk.get("raw_type") or "").strip(),
        source_category,
        chunk_raw_category_name,
        raw_meta.heritage_category if raw_meta and raw_meta.heritage_category else "",
        raw_meta.raw_type if raw_meta and raw_meta.raw_type else "",
        raw_meta.raw_category_name if raw_meta and raw_meta.raw_category_name else "",
        _category_from_project_number(project_number),
    )
    raw_category_name = chunk_raw_category_name
    if not raw_category_name and raw_meta and raw_meta.raw_category_name:
        raw_category_name = _clean_raw_category_name(raw_meta.raw_category_name)
    if raw_category_name and heritage_category and raw_category_name != heritage_category:
        raw_category_name = heritage_category
    if not raw_category_name and heritage_category:
        raw_category_name = heritage_category

    batch_label = _extract_batch_label(
        source_category,
        str(chunk.get("raw_category_name") or ""),
        str(chunk.get("source_batch") or ""),
        str(chunk.get("batch") or ""),
        content,
        raw_meta.batch_label if raw_meta and raw_meta.batch_label else "",
    )
    if raw_meta:
        if raw_meta.region:
            source_region = raw_meta.region
        if raw_meta.protection_unit:
            source_org = raw_meta.protection_unit
    return SourceContext(
        document_id=str(raw_meta.document_id if raw_meta else chunk.get("document_id") or ""),
        source_name=str(chunk.get("source_name") or ""),
        source_url=str(raw_meta.source_url if raw_meta else chunk.get("source_url") or ""),
        heritage_category=heritage_category or None,
        batch_label=batch_label or None,
        region=source_region,
        protection_unit=source_org,
        raw_category_name=raw_category_name or None,
        raw_type=(raw_meta.raw_type if raw_meta and raw_meta.raw_type else str(chunk.get("source_type") or "").strip()) or None,
        retrieved_at=str(raw_meta.retrieved_at if raw_meta else chunk.get("retrieved_at") or ""),
        evidence_text=content,
    )


def extract_from_chunk(chunk: dict) -> ExtractionResult:
    """从单个 chunk 里做可解释抽取。"""
    ctx = _source_context_from_chunk(chunk)
    prov = _chunk_provenance(chunk, ctx)
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
            r"[\u4e00-\u9fff]{2,6}舞",
            r"[\u4e00-\u9fff]{2,6}歌",
            r"[\u4e00-\u9fff]{2,6}绣",
            r"[\u4e00-\u9fff]{2,6}戏",
            r"[\u4e00-\u9fff]{2,6}画",
            r"[\u4e00-\u9fff]{2,6}曲",
            r"[\u4e00-\u9fff]{2,6}书法",
            r"[\u4e00-\u9fff]{2,6}木版年画",
            r"[\u4e00-\u9fff]{2,6}皮影",
        ):
            for match in re.finditer(pattern, content):
                cand = match.group(0)
                if _looks_like_cultural_element(cand, source_text=content, span=match.span()):
                    extra_names.append(cand)
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
    next_labels = (
        "项目名称",
        "项目编号",
        "批次",
        "类别",
        "申报地区",
        "地区简称",
        "保护单位",
    )
    label_pattern = "|".join(re.escape(label) for label in next_labels if label != prefix)
    pattern = rf"{re.escape(prefix)}[:：]\s*(.*?)(?=\s+(?:{label_pattern})[:：]|$)"
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
