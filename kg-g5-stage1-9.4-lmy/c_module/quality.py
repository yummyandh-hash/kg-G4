"""KG 质量统计。"""

from __future__ import annotations

from collections import Counter

from .schemas import ExtractionResult
from .graph_ops import deduplicate_result
from .resolver import looks_like_protection_unit, looks_like_region, looks_like_batch
from .extractor import SUPPORTED_HERITAGE_CATEGORIES, _looks_like_cultural_element


def compute_quality(result: ExtractionResult) -> dict:
    deduped = deduplicate_result(result)
    entity_counter = Counter(entity.entity_type for entity in result.entities)
    relation_counter = Counter(relation.relation_type for relation in result.relations)
    dedup_entity_counter = Counter(entity.entity_type for entity in deduped.entities)
    dedup_relation_counter = Counter(relation.relation_type for relation in deduped.relations)
    unique_entity_ids = {entity.entity_id for entity in result.entities}
    unique_relation_ids = {
        (rel.relation_type, rel.source_entity_id, rel.target_entity_id) for rel in result.relations
    }
    duplicate_entity_count = len(result.entities) - len(unique_entity_ids)
    duplicate_relation_count = len(result.relations) - len(unique_relation_ids)
    isolated_entities = _count_isolated_entities(result)
    risk = _risk_report(deduped)

    return {
        "entity_count": len(result.entities),
        "relation_count": len(result.relations),
        "deduped_entity_count": len(deduped.entities),
        "deduped_relation_count": len(deduped.relations),
        "duplicate_entity_count": duplicate_entity_count,
        "duplicate_relation_count": duplicate_relation_count,
        "isolated_entity_count": isolated_entities,
        "entity_type_distribution": dict(entity_counter),
        "relation_type_distribution": dict(relation_counter),
        "deduped_entity_type_distribution": dict(dedup_entity_counter),
        "deduped_relation_type_distribution": dict(dedup_relation_counter),
        "warning_count": len(result.warnings),
        "risk_report": risk,
    }


def _count_isolated_entities(result: ExtractionResult) -> int:
    linked = set()
    for rel in result.relations:
        linked.add(rel.source_entity_id)
        linked.add(rel.target_entity_id)
    return sum(1 for entity in result.entities if entity.entity_id not in linked)


def _risk_report(result: ExtractionResult) -> dict:
    place_as_unit = []
    batch_as_category = []
    weird_categories = []
    cultural_fragments = []
    project_category_conflicts = []
    project_raw_batch_values = []
    for entity in result.entities:
        if entity.entity_type == "ProtectionUnit" and looks_like_region(entity.name):
            place_as_unit.append(entity.name)
        if entity.entity_type == "Category" and looks_like_batch(entity.name):
            batch_as_category.append(entity.name)
        if entity.entity_type == "Category" and entity.name not in SUPPORTED_HERITAGE_CATEGORIES:
            weird_categories.append(entity.name)
        if entity.entity_type == "CulturalElement" and not _looks_like_cultural_element(entity.name):
            cultural_fragments.append(entity.name)
        if entity.entity_type == "InheritProject":
            heritage_category = str(entity.attributes.get("heritage_category") or "").strip()
            raw_category_name = str(entity.attributes.get("raw_category_name") or "").strip()
            if raw_category_name and looks_like_batch(raw_category_name):
                project_raw_batch_values.append(f"{entity.name}: raw_category_name={raw_category_name}")
            if (
                heritage_category in SUPPORTED_HERITAGE_CATEGORIES
                and raw_category_name in SUPPORTED_HERITAGE_CATEGORIES
                and heritage_category != raw_category_name
            ):
                project_category_conflicts.append(
                    f"{entity.name}: heritage_category={heritage_category}, raw_category_name={raw_category_name}"
                )
    return {
        "region_as_protection_unit_count": len(place_as_unit),
        "batch_as_category_count": len(batch_as_category),
        "nonstandard_category_count": len(list(dict.fromkeys(weird_categories))),
        "cultural_fragment_count": len(list(dict.fromkeys(cultural_fragments))),
        "project_category_conflict_count": len(list(dict.fromkeys(project_category_conflicts))),
        "project_raw_category_batch_count": len(list(dict.fromkeys(project_raw_batch_values))),
        "region_as_protection_unit_samples": list(dict.fromkeys(place_as_unit))[:20],
        "batch_as_category_samples": list(dict.fromkeys(batch_as_category))[:20],
        "nonstandard_category_samples": list(dict.fromkeys(weird_categories))[:20],
        "cultural_fragment_samples": list(dict.fromkeys(cultural_fragments))[:20],
        "project_category_conflict_samples": list(dict.fromkeys(project_category_conflicts))[:20],
        "project_raw_category_batch_samples": list(dict.fromkeys(project_raw_batch_values))[:20],
    }
