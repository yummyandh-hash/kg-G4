from c_module.extractor import extract_from_chunk
from c_module.resolver import resolve_entity
from c_module.resolver import correct_entity_type


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
