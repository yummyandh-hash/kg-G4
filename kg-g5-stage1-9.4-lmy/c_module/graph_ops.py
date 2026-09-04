"""图谱去重与合并工具。

Stage 1 需要的是一版能交付的小规模 KG，而不是原始抽取日志。
这里负责把原始抽取结果整理成可落 Neo4j 的最终图数据。
"""

from __future__ import annotations

from dataclasses import replace

from .schemas import EntityRecord, ExtractionResult, RelationRecord
from .resolver import correct_entity_type


def _merge_provenance(target: list, source: list) -> list:
    seen = set()
    merged = []
    for item in list(target) + list(source):
        key = tuple(sorted(getattr(item, "__dict__", item).items())) if not isinstance(item, dict) else tuple(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def deduplicate_result(result: ExtractionResult) -> ExtractionResult:
    """按 entity_id / relation signature 去重，并合并 provenance。"""
    entity_map: dict[str, EntityRecord] = {}
    relation_map: dict[tuple[str, str, str], RelationRecord] = {}
    id_map: dict[str, str] = {}

    for entity in result.entities:
        corrected_type, correction_reason = correct_entity_type(entity.name, entity.entity_type)
        corrected_id = entity.entity_id
        if corrected_type != entity.entity_type:
            corrected_id = f"{corrected_type}:{entity.name}"
        id_map[entity.entity_id] = corrected_id
        attrs = dict(entity.attributes)
        if correction_reason != "as-is":
            attrs["type_correction"] = correction_reason
        entity = replace(
            entity,
            entity_id=corrected_id,
            entity_type=corrected_type,  # type: ignore[arg-type]
            attributes=attrs,
        )
        existing = entity_map.get(entity.entity_id)
        if existing is None:
            entity_map[entity.entity_id] = entity
            continue
        aliases = list(dict.fromkeys(list(existing.aliases) + list(entity.aliases)))
        attrs = {**existing.attributes, **entity.attributes}
        prov = _merge_provenance(existing.provenance, entity.provenance)
        entity_map[entity.entity_id] = replace(existing, aliases=aliases, attributes=attrs, provenance=prov)

    for relation in result.relations:
        source = id_map.get(relation.source_entity_id, relation.source_entity_id)
        target = id_map.get(relation.target_entity_id, relation.target_entity_id)
        relation = replace(relation, source_entity_id=source, target_entity_id=target)
        key = (relation.relation_type, relation.source_entity_id, relation.target_entity_id)
        existing = relation_map.get(key)
        if existing is None:
            relation_map[key] = relation
            continue
        attrs = {**existing.attributes, **relation.attributes}
        prov = _merge_provenance(existing.provenance, relation.provenance)
        score = max(existing.confidence, relation.confidence)
        relation_map[key] = replace(existing, confidence=score, attributes=attrs, provenance=prov)

    return ExtractionResult(
        entities=list(entity_map.values()),
        relations=list(relation_map.values()),
        warnings=list(result.warnings),
    )


def build_entity_index(result: ExtractionResult) -> dict[str, EntityRecord]:
    return {entity.entity_id: entity for entity in result.entities}


def relation_signature(relation: RelationRecord) -> tuple[str, str, str]:
    return (relation.relation_type, relation.source_entity_id, relation.target_entity_id)
