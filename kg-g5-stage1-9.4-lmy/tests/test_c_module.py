import json

from c_module.extractor import extract_from_chunk
from c_module.graph_ops import deduplicate_result
from c_module.resolver import resolve_entity
from c_module.resolver import correct_entity_type
from c_module.entity_resolution import generate_candidates, resolve_entities
from c_module.neo4j_writer import entity_merge_cypher, relation_merge_cypher
from c_module.schemas import EntityRecord, ExtractionResult, Provenance, RelationRecord


def test_extract_basic_info():
    chunk = {
        "chunk_id": "demo_1",
        "chunk_type": "basic_info",
        "content": "项目名称：苏绣\n项目编号：Ⅰ-FRZX-2\n批次：2006\n类别：第一批",
        "source_name": "苏绣",
        "source_category": "第一批",
        "source_region": "江苏省苏州市",
        "source_org": "苏州市非物质文化遗产保护管理办公室",
        "source_url": "https://www.ihchina.cn/project/15338",
        "retrieved_at": "2026-09-04T09:00:00+08:00",
        "document_id": "ihchina_demo",
        "source_batch": "2006",
    }
    result = extract_from_chunk(chunk)
    assert any(e.entity_type == "InheritProject" for e in result.entities)
    assert any(r.relation_type == "BELONGS_TO" for r in result.relations)


def test_resolve_entity():
    decision = resolve_entity("苏绣", ["苏州刺绣", "蜀绣", "苏绣"])
    assert decision.canonical_name == "苏绣"
    assert decision.matched is True


def test_type_correction_and_category_guard():
    chunk = {
        "chunk_id": "demo_2",
        "chunk_type": "basic_info",
        "content": "项目名称：京绣\n项目编号：Ⅰ-FRZX-1\n批次：2006\n类别：第一批",
        "source_name": "京绣",
        "source_category": "第一批",
        "source_type": "传统技艺",
        "source_region": "北京市房山区",
        "source_org": "北京市房山区",
        "source_url": "https://www.ihchina.cn/project/15331",
        "retrieved_at": "2026-09-04T09:00:00+08:00",
        "document_id": "ihchina_15331",
        "source_batch": "2006",
    }
    result = extract_from_chunk(chunk)
    assert any(e.entity_type == "Category" and e.name == "传统技艺" for e in result.entities)
    assert not any(e.entity_type == "Category" and e.name in {"第一批", "2006"} for e in result.entities)
    assert any(e.entity_type == "Region" for e in result.entities)
    assert not any(e.entity_type == "ProtectionUnit" and e.name == "北京市房山区" for e in result.entities)


def test_protection_unit_correction():
    region_type, reason = correct_entity_type("河南省开封市", "ProtectionUnit")
    assert region_type == "Region"
    assert reason == "place-name override"


def test_stage2_resolution_merges_exact_normalized_alias():
    left = EntityRecord(
        entity_id="CulturalElement:长鼓舞",
        entity_type="CulturalElement",
        name="长鼓舞",
    )
    right = EntityRecord(
        entity_id="CulturalElement:长鼓舞（ ）",
        entity_type="CulturalElement",
        name="长鼓舞（ ）",
    )
    result = ExtractionResult(entities=[left, right])
    candidates = generate_candidates(result)
    assert candidates[0]["action"] == "MERGE"
    resolved, _, report = resolve_entities(result)
    assert report["auto_merge_count"] == 1
    assert len(resolved.entities) == 1


def test_stage2_similarity_candidate_requires_review():
    left = EntityRecord(
        entity_id="CulturalElement:长鼓舞",
        entity_type="CulturalElement",
        name="长鼓舞",
    )
    right = EntityRecord(
        entity_id="CulturalElement:长鼓舞表演",
        entity_type="CulturalElement",
        name="长鼓舞表演",
    )
    result = ExtractionResult(entities=[left, right])
    candidates = generate_candidates(result)
    assert candidates[0]["action"] == "REVIEW"


def test_stage2_merge_rewrites_relation_and_keeps_provenance():
    first = EntityRecord(
        entity_id="CulturalElement:长鼓舞",
        entity_type="CulturalElement",
        name="长鼓舞",
        provenance=[Provenance("url-1", "doc-1", "chunk-1", "now")],
    )
    second = EntityRecord(
        entity_id="CulturalElement:长鼓舞（ ）",
        entity_type="CulturalElement",
        name="长鼓舞（ ）",
        provenance=[Provenance("url-2", "doc-2", "chunk-2", "now")],
    )
    relation = RelationRecord(
        relation_type="RELATED_TO",
        source_entity_id=second.entity_id,
        target_entity_id=first.entity_id,
        confidence=0.8,
        provenance=[Provenance("url-2", "doc-2", "chunk-2", "now")],
    )
    result, _, _ = resolve_entities(ExtractionResult([first, second], [relation]))
    assert len(result.entities) == 1
    assert result.relations[0].source_entity_id == first.entity_id
    assert len(result.relations[0].provenance) == 1
    assert len(result.entities[0].provenance) == 2


def test_stage2_exact_project_name_merges_without_context():
    left = EntityRecord(
        entity_id="InheritProject:demo-a",
        entity_type="InheritProject",
        name="同名项目（ ）",
    )
    right = EntityRecord(
        entity_id="InheritProject:demo-b",
        entity_type="InheritProject",
        name="同名项目",
    )
    result, _, report = resolve_entities(ExtractionResult([left, right]))
    assert report["auto_merge_count"] == 1
    assert len(result.entities) == 1


def test_stage2_consumes_b_entity_candidate_json(tmp_path):
    first = EntityRecord(
        entity_id="CulturalElement:陕北剪纸",
        entity_type="CulturalElement",
        name="陕北剪纸",
    )
    second = EntityRecord(
        entity_id="CulturalElement:陕西民间剪纸",
        entity_type="CulturalElement",
        name="陕西民间剪纸",
    )
    candidate_path = tmp_path / "entity_candidate.json"
    candidate_path.write_text(
        json.dumps([
            {
                "canonical_name": "陕北剪纸",
                "aliases": ["陕西民间剪纸"],
                "category": "传统美术",
                "region": "陕西",
                "confidence": 0.92,
                "source_documents": ["ihchina_demo"],
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )

    result, candidates, report = resolve_entities(
        ExtractionResult([first, second]),
        external_candidates=candidate_path,
    )

    assert candidates[0]["reason"] == "b-candidate-high-confidence"
    assert report["b_auto_merge_count"] == 1
    assert len(result.entities) == 1
    assert result.entities[0].canonical_name == "陕北剪纸"
    assert result.entities[0].attributes["b_candidate_confidence"] == 0.92


def test_stage2_keeps_low_confidence_b_candidate_for_review(tmp_path):
    first = EntityRecord(
        entity_id="CulturalElement:河北剪纸",
        entity_type="CulturalElement",
        name="河北剪纸",
    )
    second = EntityRecord(
        entity_id="CulturalElement:陕北剪纸",
        entity_type="CulturalElement",
        name="陕北剪纸",
    )
    candidate_path = tmp_path / "entity_candidate.json"
    candidate_path.write_text(
        json.dumps([
            {
                "canonical_name": "河北剪纸",
                "aliases": ["陕北剪纸"],
                "category": "传统美术",
                "region": "陕西",
                "confidence": 0.7,
                "source_documents": [],
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )

    result, candidates, report = resolve_entities(
        ExtractionResult([first, second]),
        external_candidates=candidate_path,
    )

    assert candidates[0]["action"] == "REVIEW"
    assert candidates[0]["reason"] == "b-candidate-low-confidence"
    assert report["b_review_candidate_count"] == 1
    assert len(result.entities) == 2


def test_stage2_applies_b_canonical_name_to_single_match(tmp_path):
    entity = EntityRecord(
        entity_id="CulturalElement:陕西民间剪纸",
        entity_type="CulturalElement",
        name="陕西民间剪纸",
    )
    candidate_path = tmp_path / "entity_candidate.json"
    candidate_path.write_text(
        json.dumps([
            {
                "canonical_name": "陕北剪纸",
                "aliases": ["陕西民间剪纸"],
                "category": "传统美术",
                "region": "陕西",
                "confidence": 0.9,
                "source_documents": ["ihchina_demo"],
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )

    result, _, report = resolve_entities(
        ExtractionResult([entity]),
        external_candidates=candidate_path,
    )

    assert len(result.entities) == 1
    assert result.entities[0].canonical_name == "陕北剪纸"
    assert result.entities[0].attributes["resolution_source"] == "B entity_candidate.json"
    assert report["b_canonicalized_entity_count"] == 1


def test_cultural_element_noise_blacklist_keeps_real_short_names():
    dirty_names = [
        "热情地歌",
        "时仍演白面具戏",
        "惊八种刻画",
        "属羽调式民歌",
        "手持云阳板作舞",
        "大家会齐唱副歌",
        "遗存较原始曲",
        "梅林戏俗称土戏",
        "艺人根据某种戏",
        "不受戏曲",
        "担任迥巴藏戏",
        "导致曲",
        "不少戏",
        "不仅具有戏曲",
        "既能够体现人戏",
        "前多演奏现代曲",
        "够掌握传统秧歌",
    ]
    clean_names = ["四平戏", "公仔戏", "陇板歌", "鼓点舞", "汕尾渔歌", "唐宋大曲", "彝族烟盒舞"]
    entities = [
        EntityRecord(f"CulturalElement:{name}", "CulturalElement", name)
        for name in [*dirty_names, *clean_names]
    ]

    result = deduplicate_result(ExtractionResult(entities=entities))
    names = {entity.name for entity in result.entities}

    assert not any(name in names for name in dirty_names)
    assert all(name in names for name in clean_names)


def test_neo4j_export_uses_json_properties_and_statement_delimiters():
    entity = {
        "entity_id": "Category:传统技艺",
        "entity_type": "Category",
        "name": "传统技艺",
        "canonical_name": "传统技艺",
        "aliases": [],
        "attributes": {"source": "demo"},
        "provenance": [],
    }
    cypher = entity_merge_cypher(entity)
    assert "attributes_json" in cypher
    assert "provenance_json" in cypher
    assert 'attributes_json = "{' in cypher
    assert "n.attributes =" not in cypher
    assert cypher.rstrip().endswith(";")

    relation = {
        "relation_type": "BELONGS_TO",
        "source_entity_id": "InheritProject:demo",
        "target_entity_id": "Category:传统技艺",
        "confidence": 0.9,
        "attributes": {"verified": True},
        "provenance": [],
    }
    relation_cypher = relation_merge_cypher(relation)
    assert "r.attributes_json" in relation_cypher
    assert "r.provenance_json" in relation_cypher
    assert relation_cypher.rstrip().endswith(";")
