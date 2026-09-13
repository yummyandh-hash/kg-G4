"""Stage 2 实体消歧与融合。

设计原则：
1. 规则高精度自动合并，避免把相近但不同的非遗项目误合并；
2. 中等相似度只进入人工复核，不直接改图；
3. 每个候选都写入 merge log，保证结果可解释、可回溯。
"""

from __future__ import annotations

from dataclasses import asdict, replace
from difflib import SequenceMatcher
import json
import re
from pathlib import Path
from typing import Any, Iterable

from .schemas import EntityRecord, ExtractionResult, Provenance, RelationRecord


B_AUTO_MERGE_CONFIDENCE = 0.85


def normalize_entity_name(name: str) -> str:
    """用于候选发现的保守规范化，不改变展示名称。"""
    value = (name or "").strip().lower()
    value = re.sub(r"[（）()\[\]【】《》“”‘’·•、，,。；;：:\s]", "", value)
    value = value.replace("非物质文化遗产", "非遗")
    return value


def _name_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_entity_name(left), normalize_entity_name(right)).ratio()


def _provenance_context(entity: EntityRecord) -> set[str]:
    context: set[str] = set()
    for item in entity.provenance:
        for value in (item.document_id, item.source_url, item.source_region):
            if value:
                context.add(str(value).strip())
    return context


def _same_context(left: EntityRecord, right: EntityRecord) -> bool:
    return bool(_provenance_context(left) & _provenance_context(right))


def _entity_from_dict(data: dict[str, Any]) -> EntityRecord:
    provenance = [_provenance_from_dict(item) for item in data.get("provenance", [])]
    return EntityRecord(
        entity_id=str(data["entity_id"]),
        entity_type=data["entity_type"],
        name=str(data.get("name") or ""),
        canonical_name=data.get("canonical_name"),
        aliases=list(data.get("aliases") or []),
        attributes=dict(data.get("attributes") or {}),
        provenance=provenance,
    )


def _relation_from_dict(data: dict[str, Any]) -> RelationRecord:
    provenance = [_provenance_from_dict(item) for item in data.get("provenance", [])]
    return RelationRecord(
        relation_type=data["relation_type"],
        source_entity_id=str(data["source_entity_id"]),
        target_entity_id=str(data["target_entity_id"]),
        confidence=float(data.get("confidence") or 0.0),
        provenance=provenance,
        attributes=dict(data.get("attributes") or {}),
    )


def _provenance_from_dict(item: Provenance | dict[str, Any]) -> Provenance:
    """Read both full Stage 1 provenance and reduced hand-written fixtures."""
    if isinstance(item, Provenance):
        return item
    return Provenance(
        source_url=str(item.get("source_url") or ""),
        document_id=str(item.get("document_id") or ""),
        chunk_id=str(item.get("chunk_id") or ""),
        retrieved_at=str(item.get("retrieved_at") or ""),
        source_name=item.get("source_name"),
        source_category=item.get("source_category"),
        source_region=item.get("source_region"),
        source_org=item.get("source_org"),
        source_batch=item.get("source_batch"),
        evidence_text=item.get("evidence_text"),
    )


def load_kg_json(path: str | Path) -> ExtractionResult:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ExtractionResult(
        entities=[_entity_from_dict(item) for item in payload.get("entities", [])],
        relations=[_relation_from_dict(item) for item in payload.get("relations", [])],
        warnings=list(payload.get("warnings") or []),
    )


def _candidate_record(
    left: EntityRecord,
    right: EntityRecord,
    score: float,
    action: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "left_entity_id": left.entity_id,
        "right_entity_id": right.entity_id,
        "left_name": left.name,
        "right_name": right.name,
        "entity_type": left.entity_type,
        "score": round(score, 4),
        "action": action,
        "reason": reason,
    }


def _entity_name_keys(entity: EntityRecord) -> set[str]:
    names = {entity.name}
    if entity.canonical_name:
        names.add(entity.canonical_name)
    names.update(entity.aliases)
    return {normalize_entity_name(name) for name in names if normalize_entity_name(name)}


def _load_external_records(candidates_path: str | Path | None) -> list[dict[str, Any]]:
    if not candidates_path:
        return []
    path = Path(candidates_path)
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    records = json.loads(raw) if path.suffix.lower() == ".json" else [
        json.loads(line) for line in raw.splitlines() if line.strip()
    ]
    if isinstance(records, dict):
        records = records.get("candidates") or records.get("entity_candidates") or []
    return [item for item in records if isinstance(item, dict)]


def _external_candidate_pairs(
    result: ExtractionResult,
    candidates_path: str | Path | None,
) -> list[tuple[EntityRecord | None, EntityRecord | None, dict[str, Any]]]:
    """兼容外部二元组候选，以及 B 交付的 entity_candidate.json 格式。"""
    records = _load_external_records(candidates_path)
    if not records:
        return []

    by_id = {item.entity_id: item for item in result.entities}
    by_name: dict[str, list[EntityRecord]] = {}
    for entity in result.entities:
        for key in _entity_name_keys(entity):
            by_name.setdefault(key, []).append(entity)

    pairs: list[tuple[EntityRecord | None, EntityRecord | None, dict[str, Any]]] = []
    for item in records:
        # 旧格式：直接给 C 模块的实体 ID 二元组。
        left = item.get("left_entity_id") or item.get("left") or item.get("entity_a")
        right = item.get("right_entity_id") or item.get("right") or item.get("entity_b")
        if left and right:
            pairs.append((by_id.get(str(left)), by_id.get(str(right)), {"source": "external-pair"}))
            continue

        # B Stage2 格式：canonical_name + aliases + confidence。
        canonical_name = str(item.get("canonical_name") or "").strip()
        aliases = [str(alias).strip() for alias in item.get("aliases") or [] if str(alias).strip()]
        if not canonical_name and not aliases:
            continue
        keys = {normalize_entity_name(canonical_name)}
        keys.update(normalize_entity_name(alias) for alias in aliases)
        keys.discard("")
        matched: dict[str, EntityRecord] = {}
        for key in keys:
            for entity in by_name.get(key, []):
                matched[entity.entity_id] = entity
        entities = list(matched.values())
        meta = {
            "source": "b-entity-candidate",
            "canonical_name": canonical_name,
            "aliases": aliases,
            "category": item.get("category"),
            "region": item.get("region"),
            "confidence": float(item.get("confidence") or 0.0),
            "source_documents": list(item.get("source_documents") or []),
        }
        for index, left_entity in enumerate(entities):
            for right_entity in entities[index + 1:]:
                pairs.append((left_entity, right_entity, meta))
    return pairs


def _external_canonical_updates(
    result: ExtractionResult,
    candidates_path: str | Path | None,
) -> dict[str, dict[str, Any]]:
    records = _load_external_records(candidates_path)
    if not records:
        return {}
    updates: dict[str, dict[str, Any]] = {}
    for item in records:
        canonical_name = str(item.get("canonical_name") or "").strip()
        aliases = [str(alias).strip() for alias in item.get("aliases") or [] if str(alias).strip()]
        confidence = float(item.get("confidence") or 0.0)
        if confidence < B_AUTO_MERGE_CONFIDENCE or (not canonical_name and not aliases):
            continue
        keys = {normalize_entity_name(canonical_name)}
        keys.update(normalize_entity_name(alias) for alias in aliases)
        keys.discard("")
        for entity in result.entities:
            if _entity_name_keys(entity) & keys:
                updates[entity.entity_id] = {
                    "candidate_source": "b-entity-candidate",
                    "canonical_name": canonical_name,
                    "aliases": aliases,
                    "category": item.get("category"),
                    "region": item.get("region"),
                    "b_confidence": confidence,
                    "left_name": entity.name,
                    "right_name": canonical_name,
                    "source_documents": list(item.get("source_documents") or []),
                }
    return updates


def generate_candidates(
    result: ExtractionResult,
    external_candidates: str | Path | None = None,
    review_threshold: float = 0.78,
) -> list[dict[str, Any]]:
    """生成候选，不直接删除任何实体。"""
    external_pairs = _external_candidate_pairs(result, external_candidates)
    if external_pairs:
        raw_pairs = external_pairs
    else:
        grouped: dict[str, list[EntityRecord]] = {}
        for entity in result.entities:
            grouped.setdefault(entity.entity_type, []).append(entity)
        # Blocking：先按规范化名称/首字和尾字分桶，避免全量 O(n^2) 比较。
        # B 若交付候选文件则优先使用候选文件，不经过此近似召回。
        raw_pairs: list[tuple[EntityRecord | None, EntityRecord | None, dict[str, Any]]] = []
        for entities in grouped.values():
            blocks: dict[str, list[EntityRecord]] = {}
            for entity in entities:
                normalized = normalize_entity_name(entity.name)
                if not normalized:
                    continue
                keys = {f"exact:{normalized}", f"prefix:{normalized[:2]}"}
                if len(normalized) >= 3:
                    keys.add(f"shape:{normalized[:2]}:{normalized[-1]}")
                for key in keys:
                    blocks.setdefault(key, []).append(entity)
            pair_ids: set[tuple[str, str]] = set()
            for block_key, bucket in blocks.items():
                # 极端情况下同一首字桶可能很大，跳过宽泛首字桶，
                # 但仍保留精确名称桶和更窄的首尾形状桶。
                if len(bucket) > 300 and block_key.startswith("prefix:"):
                    continue
                for index, left in enumerate(bucket):
                    for right in bucket[index + 1:]:
                        pair_key = tuple(sorted((left.entity_id, right.entity_id)))
                        if pair_key in pair_ids:
                            continue
                        pair_ids.add(pair_key)
                        left_norm = normalize_entity_name(left.name)
                        right_norm = normalize_entity_name(right.name)
                        if left_norm == right_norm or _name_similarity(left.name, right.name) >= review_threshold:
                            raw_pairs.append((left, right, {}))

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for left, right, external_meta in raw_pairs:
        if left is None or right is None or left.entity_type != right.entity_type:
            continue
        key = tuple(sorted((left.entity_id, right.entity_id)))
        if key in seen:
            continue
        seen.add(key)
        score = _name_similarity(left.name, right.name)
        exact = normalize_entity_name(left.name) == normalize_entity_name(right.name)
        context_match = _same_context(left, right)
        containment = (
            normalize_entity_name(left.name) in normalize_entity_name(right.name)
            or normalize_entity_name(right.name) in normalize_entity_name(left.name)
        )

        if external_meta.get("source") == "b-entity-candidate":
            confidence = float(external_meta.get("confidence") or 0.0)
            if confidence >= B_AUTO_MERGE_CONFIDENCE:
                action = "MERGE"
                reason = "b-candidate-high-confidence"
            else:
                action = "REVIEW"
                reason = "b-candidate-low-confidence"
        else:
            # 只对高确定性候选自动合并；项目名必须还有共同来源上下文。
            auto_merge = (
                exact
                or (
                    score >= 0.97
                    and containment
                    and (left.entity_type != "InheritProject" or context_match)
                )
            )
            if auto_merge:
                action = "MERGE"
                reason = "normalized-name-equal" if exact else "high-similarity-with-context"
            elif score >= review_threshold:
                action = "REVIEW"
                reason = "similar-name-needs-human-confirmation"
            else:
                action = "KEEP_SEPARATE"
                reason = "similarity-below-threshold"
        record = _candidate_record(left, right, score, action, reason)
        if external_meta:
            record.update(
                {
                    "candidate_source": external_meta.get("source"),
                    "canonical_name": external_meta.get("canonical_name"),
                    "aliases": external_meta.get("aliases") or [],
                    "category": external_meta.get("category"),
                    "region": external_meta.get("region"),
                    "b_confidence": external_meta.get("confidence"),
                    "source_documents": external_meta.get("source_documents") or [],
                }
            )
        candidates.append(record)
    return candidates


def _merge_provenance(left: Iterable[Provenance], right: Iterable[Provenance]) -> list[Provenance]:
    output: list[Provenance] = []
    seen: set[str] = set()
    for item in [*left, *right]:
        key = json.dumps(asdict(item), ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _merge_entities(left: EntityRecord, right: EntityRecord) -> EntityRecord:
    # 选择来源更多者作为展示主体；同分时选择名称更短者作为规范名。
    if len(right.provenance) > len(left.provenance):
        primary, secondary = right, left
    elif len(right.provenance) == len(left.provenance) and len(right.name) < len(left.name):
        primary, secondary = right, left
    else:
        primary, secondary = left, right
    aliases = list(dict.fromkeys([
        *primary.aliases,
        *secondary.aliases,
        secondary.name,
    ]))
    attrs = {**secondary.attributes, **primary.attributes}
    attrs["resolution_status"] = "merged"
    merged_ids = attrs.get("merged_entity_ids", [])
    if not isinstance(merged_ids, list):
        merged_ids = [merged_ids]
    secondary_merged_ids = secondary.attributes.get("merged_entity_ids", [])
    if not isinstance(secondary_merged_ids, list):
        secondary_merged_ids = [secondary_merged_ids]
    attrs["merged_entity_ids"] = list(dict.fromkeys([
        *merged_ids,
        *secondary_merged_ids,
        secondary.entity_id,
    ]))
    return replace(
        primary,
        # 关系重定向统一指向左侧ID，避免合并后实体ID和关系端点不一致。
        entity_id=left.entity_id,
        canonical_name=primary.canonical_name or primary.name,
        aliases=aliases,
        attributes=attrs,
        provenance=_merge_provenance(primary.provenance, secondary.provenance),
    )


def _apply_external_candidate_metadata(entity: EntityRecord, candidate: dict[str, Any]) -> EntityRecord:
    if candidate.get("candidate_source") != "b-entity-candidate":
        return entity
    aliases = list(dict.fromkeys([
        *entity.aliases,
        candidate.get("left_name"),
        candidate.get("right_name"),
        *(candidate.get("aliases") or []),
    ]))
    attrs = dict(entity.attributes)
    attrs["resolution_source"] = "B entity_candidate.json"
    attrs["b_candidate_confidence"] = candidate.get("b_confidence")
    if candidate.get("category"):
        attrs["b_candidate_category"] = candidate["category"]
    if candidate.get("region"):
        attrs["b_candidate_region"] = candidate["region"]
    return replace(
        entity,
        canonical_name=candidate.get("canonical_name") or entity.canonical_name or entity.name,
        aliases=[alias for alias in aliases if alias and alias != entity.name],
        attributes=attrs,
    )


def resolve_entities(
    result: ExtractionResult,
    external_candidates: str | Path | None = None,
) -> tuple[ExtractionResult, list[dict[str, Any]], dict[str, Any]]:
    candidates = generate_candidates(result, external_candidates)
    entity_map = {entity.entity_id: entity for entity in result.entities}
    redirects: dict[str, str] = {}
    merge_count = 0

    for item in candidates:
        if item["action"] != "MERGE":
            continue
        left_id = redirects.get(item["left_entity_id"], item["left_entity_id"])
        right_id = redirects.get(item["right_entity_id"], item["right_entity_id"])
        if left_id == right_id or left_id not in entity_map or right_id not in entity_map:
            continue
        merged = _merge_entities(entity_map[left_id], entity_map[right_id])
        merged = _apply_external_candidate_metadata(merged, item)
        entity_map[left_id] = merged
        redirects[right_id] = left_id
        entity_map.pop(right_id, None)
        item["canonical_entity_id"] = left_id
        merge_count += 1

    canonicalized_count = 0
    canonical_updates = _external_canonical_updates(
        ExtractionResult(list(entity_map.values()), [], list(result.warnings)),
        external_candidates,
    )
    for entity_id, update in canonical_updates.items():
        if entity_id not in entity_map:
            continue
        before = entity_map[entity_id]
        after = _apply_external_candidate_metadata(before, update)
        if after != before:
            canonicalized_count += 1
            entity_map[entity_id] = after

    # 关系端点跟随实体重定向，并按签名重新去重。
    relation_map: dict[tuple[str, str, str], RelationRecord] = {}
    for relation in result.relations:
        source = relation.source_entity_id
        target = relation.target_entity_id
        while source in redirects:
            source = redirects[source]
        while target in redirects:
            target = redirects[target]
        updated = replace(relation, source_entity_id=source, target_entity_id=target)
        key = (updated.relation_type, source, target)
        old = relation_map.get(key)
        if old is None:
            relation_map[key] = updated
        elif updated.confidence > old.confidence:
            relation_map[key] = replace(
                updated,
                provenance=_merge_provenance(old.provenance, updated.provenance),
            )
        else:
            relation_map[key] = replace(
                old,
                provenance=_merge_provenance(old.provenance, updated.provenance),
            )

    resolved = ExtractionResult(
        entities=list(entity_map.values()),
        relations=list(relation_map.values()),
        warnings=list(result.warnings),
    )
    report = {
        "input_entity_count": len(result.entities),
        "output_entity_count": len(resolved.entities),
        "auto_merge_count": merge_count,
        "review_candidate_count": sum(item["action"] == "REVIEW" for item in candidates),
        "keep_separate_count": sum(item["action"] == "KEEP_SEPARATE" for item in candidates),
        "candidate_count": len(candidates),
        "b_candidate_count": sum(item.get("candidate_source") == "b-entity-candidate" for item in candidates),
        "b_auto_merge_count": sum(
            item.get("candidate_source") == "b-entity-candidate" and item["action"] == "MERGE"
            for item in candidates
        ),
        "b_review_candidate_count": sum(
            item.get("candidate_source") == "b-entity-candidate" and item["action"] == "REVIEW"
            for item in candidates
        ),
        "b_canonicalized_entity_count": canonicalized_count,
    }
    return resolved, candidates, report


def write_merge_log(candidates: list[dict[str, Any]], path: str | Path) -> None:
    Path(path).write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in candidates),
        encoding="utf-8",
    )


def write_review_candidates(candidates: list[dict[str, Any]], path: str | Path) -> None:
    review = [item for item in candidates if item["action"] == "REVIEW"]
    Path(path).write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in review),
        encoding="utf-8",
    )
