import json

from c_module.extractor import extract_from_chunk
from c_module.quality import compute_quality
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
        "content": "项目名称：苏绣\n项目编号：Ⅶ-16\n批次：第一批\n类别：传统美术",
        "source_name": "苏绣",
        "source_category": "传统美术",
        "source_region": "江苏省苏州市",
        "source_org": "苏州市非物质文化遗产保护管理办公室",
        "source_url": "https://www.ihchina.cn/project/15338",
        "retrieved_at": "2026-09-04T09:00:00+08:00",
        "document_id": "ihchina_demo",
        "source_batch": "第一批",
    }
    result = extract_from_chunk(chunk)
    assert any(e.entity_type == "InheritProject" for e in result.entities)
    assert any(r.relation_type == "BELONGS_TO" for r in result.relations)
    assert any(e.entity_type == "Category" and e.name == "传统美术" for e in result.entities)


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


def test_legacy_batch_category_is_split_from_project_number():
    chunk = {
        "chunk_id": "demo_legacy",
        "chunk_type": "basic_info",
        "content": "项目名称：朝鲜族农乐舞（象帽舞）\n项目编号：Ⅲ-024_01_222400\n批次：2006\n类别：第一批",
        "source_name": "朝鲜族农乐舞（象帽舞）",
        "source_category": "第一批",
        "source_region": "吉林省延边朝鲜族自治州",
        "source_org": "吉林省延边朝鲜族自治州",
        "source_url": "https://www.ihchina.cn/project/12962",
        "retrieved_at": "2026-09-04T09:51:37+08:00",
        "document_id": "ihchina_00175424c493",
        "source_batch": "2006",
    }
    result = extract_from_chunk(chunk)
    project = next(e for e in result.entities if e.entity_type == "InheritProject")
    assert project.attributes["batch"] == "第一批"
    assert project.attributes["heritage_category"] == "传统舞蹈"
    assert project.attributes["raw_category_name"] == "传统舞蹈"
    assert any(e.entity_type == "Category" and e.name == "传统舞蹈" for e in result.entities)
    assert not any(e.entity_type == "Category" and e.name in {"第一批", "2006"} for e in result.entities)
    assert not any(e.entity_type == "ProtectionUnit" and e.name == "吉林省延边朝鲜族自治州" for e in result.entities)


def test_category_conflict_prefers_heritage_category():
    chunk = {
        "chunk_id": "demo_conflict",
        "chunk_type": "basic_info",
        "content": "项目名称：测试舞蹈\n项目编号：Ⅲ-001\n批次：第一批\n类别：传统舞蹈",
        "source_name": "测试舞蹈",
        "source_category": "传统舞蹈",
        "heritage_category": "传统舞蹈",
        "raw_category_name": "传统美术",
        "source_region": "北京市",
        "source_org": "北京市文化馆",
        "source_url": "https://www.ihchina.cn/project/demo",
        "retrieved_at": "2026-09-04T09:00:00+08:00",
        "document_id": "ihchina_demo_conflict",
        "source_batch": "第一批",
    }
    result = extract_from_chunk(chunk)
    project = next(e for e in result.entities if e.entity_type == "InheritProject")
    assert project.attributes["heritage_category"] == "传统舞蹈"
    assert project.attributes["raw_category_name"] == "传统舞蹈"
    assert any(e.entity_type == "Category" and e.name == "传统舞蹈" for e in result.entities)
    assert not any(e.entity_type == "Category" and e.name == "传统美术" for e in result.entities)
    assert compute_quality(result)["risk_report"]["project_category_conflict_count"] == 0


def test_cultural_element_filters_sentence_fragments():
    chunk = {
        "chunk_id": "demo_detail",
        "chunk_type": "detail_content",
        "content": "创始于农业劳作，并具有古代祭祀成分的朝鲜族代表性民间传统活动“农乐舞”，一般有两种形式，一种是以舞蹈和哑剧形式进行情节性的演出；而另一种，是在新年伊始和欢庆丰收时节，以热烈而丰富的传统舞蹈为内容所进行的群众性表演活动。",
        "source_name": "朝鲜族农乐舞（象帽舞）",
        "source_category": "传统舞蹈",
        "source_region": "吉林省延边朝鲜族自治州",
        "source_org": "吉林省延边朝鲜族自治州",
        "source_url": "https://www.ihchina.cn/project/12962",
        "retrieved_at": "2026-09-04T09:51:37+08:00",
        "document_id": "ihchina_00175424c493",
        "source_batch": "第一批",
    }
    result = extract_from_chunk(chunk)
    cultural_names = {e.name for e in result.entities if e.entity_type == "CulturalElement"}
    assert "农乐舞" in cultural_names
    assert "一种是以舞" not in cultural_names
    assert "热烈而丰富的传统舞" not in cultural_names
    assert "一种是" not in cultural_names

    chunk2 = {
        "chunk_id": "demo_detail_2",
        "chunk_type": "detail_content",
        "content": "清末湖北省黄梅县一带的采茶调传入毗邻的安徽省怀宁县等地区，与当地民间艺术结合，并用安庆方言歌唱和念白，逐渐发展为一个新的戏曲剧种，当时称为怀腔或怀调，这就是早期的黄梅戏。黄梅戏是中国五大戏曲剧种之一，影响十分深远。",
        "source_name": "黄梅戏",
        "source_category": "传统戏剧",
        "source_region": "湖北省黄梅县",
        "source_org": "湖北省黄梅县",
        "source_url": "https://www.ihchina.cn/project/demo2",
        "retrieved_at": "2026-09-04T09:51:37+08:00",
        "document_id": "ihchina_demo_detail_2",
        "source_batch": "第一批",
    }
    result2 = extract_from_chunk(chunk2)
    cultural_names2 = {e.name for e in result2.entities if e.entity_type == "CulturalElement"}
    assert "黄梅戏是中国五大戏" not in cultural_names2
    assert "并用安庆方言歌" not in cultural_names2
    assert "早期黄梅戏" not in cultural_names2

    chunk3 = {
        "chunk_id": "demo_detail_3",
        "chunk_type": "detail_content",
        "content": "这个表演在村寨以外举行，主要在节庆时以歌舞形式出现，也常常与仪式一起进行，或由长者带领。",
        "source_name": "测试项目",
        "source_category": "民俗",
        "source_region": "云南省",
        "source_org": "云南省文化馆",
        "source_url": "https://www.ihchina.cn/project/demo3",
        "retrieved_at": "2026-09-04T09:51:37+08:00",
        "document_id": "ihchina_demo_detail_3",
        "source_batch": "第一批",
    }
    result3 = extract_from_chunk(chunk3)
    cultural_names3 = {e.name for e in result3.entities if e.entity_type == "CulturalElement"}
    assert "在村寨以外举行" not in cultural_names3
    assert "以歌舞形式" not in cultural_names3
    assert "与仪式一起" not in cultural_names3
    assert "由长者带领" not in cultural_names3

    chunk4 = {
        "chunk_id": "demo_detail_4",
        "chunk_type": "detail_content",
        "content": "共有小曲以唱腔为主，础上组建上海木偶皮影后逐渐发展。",
        "source_name": "测试项目2",
        "source_category": "曲艺",
        "source_region": "上海市",
        "source_org": "上海市文化馆",
        "source_url": "https://www.ihchina.cn/project/demo4",
        "retrieved_at": "2026-09-04T09:51:37+08:00",
        "document_id": "ihchina_demo_detail_4",
        "source_batch": "第一批",
    }
    result4 = extract_from_chunk(chunk4)
    cultural_names4 = {e.name for e in result4.entities if e.entity_type == "CulturalElement"}
    assert "共有小曲" not in cultural_names4
    assert "础上组建上海木偶皮影" not in cultural_names4

    chunk5 = {
        "chunk_id": "demo_detail_5",
        "chunk_type": "detail_content",
        "content": "舞龙人数少则一人舞双龙，多则百人舞一大龙。清代咸丰、道光年间，广东民间乐曲和时调。红河南岸彝族舞蹈的别称。陈塘夏尔巴歌舞流行。岭南民间舞蹈史研究。",
        "source_name": "测试项目3",
        "source_category": "传统舞蹈",
        "source_region": "浙江省",
        "source_org": "浙江省文化馆",
        "source_url": "https://www.ihchina.cn/project/demo5",
        "retrieved_at": "2026-09-04T09:51:37+08:00",
        "document_id": "ihchina_demo_detail_5",
        "source_batch": "第一批",
    }
    result5 = extract_from_chunk(chunk5)
    cultural_names5 = {e.name for e in result5.entities if e.entity_type == "CulturalElement"}
    assert "多则百人舞" not in cultural_names5
    assert "东民间乐曲" not in cultural_names5
    assert "南岸彝族舞" not in cultural_names5
    assert "塘夏尔巴歌" not in cultural_names5
    assert "岭南民间舞" not in cultural_names5
    assert compute_quality(result5)["risk_report"]["cultural_fragment_count"] == 0

    chunk6 = {
        "chunk_id": "demo_detail_6",
        "chunk_type": "detail_content",
        "content": "这是一则流传很广的民间故事，具有鲜明的地方特色。",
        "source_name": "测试项目4",
        "source_category": "民间文学",
        "source_region": "云南省",
        "source_org": "云南省文化馆",
        "source_url": "https://www.ihchina.cn/project/demo6",
        "retrieved_at": "2026-09-04T09:51:37+08:00",
        "document_id": "ihchina_demo_detail_6",
        "source_batch": "第一批",
    }
    result6 = extract_from_chunk(chunk6)
    cultural_names6 = {e.name for e in result6.entities if e.entity_type == "CulturalElement"}
    assert "民间故事" in cultural_names6
    assert compute_quality(result6)["risk_report"]["cultural_fragment_count"] == 0

    chunk7 = {
        "chunk_id": "demo_detail_7",
        "chunk_type": "detail_content",
        "content": "改革了秧歌的音乐和表演，手拉手轻盈踏地起舞，海城喇叭戏初具戏曲形态。",
        "source_name": "测试项目5",
        "source_category": "传统戏剧",
        "source_region": "辽宁省",
        "source_org": "辽宁省文化馆",
        "source_url": "https://www.ihchina.cn/project/demo7",
        "retrieved_at": "2026-09-04T09:51:37+08:00",
        "document_id": "ihchina_demo_detail_7",
        "source_batch": "第一批",
    }
    result7 = extract_from_chunk(chunk7)
    cultural_names7 = {e.name for e in result7.entities if e.entity_type == "CulturalElement"}
    assert "改革了秧歌" not in cultural_names7
    assert "手拉手轻盈踏地起舞" not in cultural_names7
    assert "海城喇叭戏初具戏曲" not in cultural_names7
    assert all(len(name) <= 8 for name in cultural_names7)


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
    # These names have similarity 0.75, below the default threshold of 0.78.
    assert generate_candidates(result) == []
    candidates = generate_candidates(result, review_threshold=0.75)
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
    cypher = entity_merge_cypher(entity, include_provenance=True)
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
    relation_cypher = relation_merge_cypher(relation, include_provenance=True)
    assert "rel.attributes_json" in relation_cypher
    assert "rel.provenance_json" in relation_cypher
    assert relation_cypher.rstrip().endswith(";")


def test_export_cypher_supports_filename_and_optional_provenance(tmp_path):
    from c_module.neo4j_writer import export_cypher

    result = ExtractionResult(entities=[EntityRecord(
        entity_id="Category:demo", entity_type="Category", name="demo",
    )])
    default_path = export_cypher(result, tmp_path)
    assert default_path.name == "kg_export.cypher"
    assert "provenance_json" not in default_path.read_text(encoding="utf-8")
    stage2_path = export_cypher(
        result, tmp_path, include_provenance=True, filename="kg_v2.cypher",
    )
    text = stage2_path.read_text(encoding="utf-8")
    assert stage2_path.name == "kg_v2.cypher"
    assert "provenance_json" in text
    assert ";;" not in text


def test_export_cypher_supports_main_positional_filename(tmp_path):
    from c_module.neo4j_writer import export_cypher

    result = ExtractionResult(entities=[EntityRecord(
        entity_id="Category:demo", entity_type="Category", name="demo",
    )])
    output = export_cypher(result, tmp_path, "main-style.cypher")
    assert output.name == "main-style.cypher"
    assert "provenance_json" in output.read_text(encoding="utf-8")
