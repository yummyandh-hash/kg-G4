from orchestration.context import build_context
from orchestration.models import Evidence


def make_evidence(
    evidence_id,
    content,
    score,
    source_id="source-1",
    source_url="https://example.com",
    retrieval_method="vector",
    relation_path=None,
):
    return Evidence(
        evidence_id=evidence_id,
        content=content,
        retrieval_method=retrieval_method,
        score=score,
        source_id=source_id,
        source_url=source_url,
        entity_ids=[],
        relation_path=relation_path,
    )


def test_build_context_empty_evidence():
    result = build_context("什么是蜀绣？", [])

    assert "用户问题：什么是蜀绣？" in result
    assert "暂无可用检索证据" in result


def test_build_context_deduplicates_evidence():
    e1 = make_evidence("e1", "证据A", 0.8)
    e2 = make_evidence("e1", "证据A", 0.7)
    e3 = make_evidence("e3", "证据B", 0.6)

    result = build_context("测试问题", [e1, e2, e3])

    assert result.count("[证据 ") == 2


def test_build_context_sorts_by_score():
    e1 = make_evidence("e1", "低分证据", 0.3)
    e2 = make_evidence("e2", "高分证据", 0.9)
    e3 = make_evidence("e3", "中分证据", 0.6)

    result = build_context("测试问题", [e1, e2, e3])

    assert result.index("高分证据") < result.index("中分证据")
    assert result.index("中分证据") < result.index("低分证据")


def test_build_context_limits_evidence():
    evidences = [
        make_evidence(f"e{i}", f"证据{i}", 1.0 - i * 0.01)
        for i in range(10)
    ]

    result = build_context(
        "测试问题",
        evidences,
        max_evidence=5,
    )

    assert result.count("[证据 ") == 5


def test_build_context_preserves_relation_path():
    evidence = make_evidence(
        "e1",
        "关系证据",
        0.9,
        retrieval_method="graph",
        relation_path=[
            "实体A",
            "关系1",
            "实体B",
            "关系2",
            "实体C",
        ],
    )

    result = build_context("测试问题", [evidence])

    assert (
    "关系路径：实体A --[关系1]--> 实体B "
    "实体B --[关系2]--> 实体C"
) in result


def test_build_context_limits_length():
    evidences = [
        make_evidence(
            f"e{i}",
            "很长的证据内容" * 100,
            1.0,
        )
        for i in range(10)
    ]

    result = build_context(
        "测试问题",
        evidences,
        max_chars=1000,
    )

    assert len(result) <= 1050
    assert "Context 已达到长度限制" in result

def test_build_context_collects_entities():
    e1 = make_evidence(
        "e1",
        "证据A",
        0.9,
    )
    e1.entity_ids = ["entity_a", "entity_b"]

    e2 = make_evidence(
        "e2",
        "证据B",
        0.8,
    )
    e2.entity_ids = ["entity_b", "entity_c"]

    result = build_context(
        "测试问题",
        [e1, e2],
    )

    assert "【相关实体】" in result
    assert "- entity_a" in result
    assert "- entity_b" in result
    assert "- entity_c" in result


def test_build_context_collects_paths():
    e1 = make_evidence(
        "e1",
        "证据A",
        0.9,
        retrieval_method="graph",
        relation_path=[
            "实体A",
            "关系1",
            "实体B",
        ],
    )

    result = build_context(
        "测试问题",
        [e1],
    )

    assert "【关系路径】" in result
    assert "[路径 1]" in result
    assert "实体A --[关系1]--> 实体B" in result


def test_build_context_collects_sources():
    e1 = make_evidence(
        "e1",
        "证据A",
        0.9,
        source_id="source-1",
        source_url="https://example.com/1",
    )

    result = build_context(
        "测试问题",
        [e1],
    )

    assert "【来源】" in result
    assert "source-1" in result
    assert "https://example.com/1" in result


def test_build_context_limits_paths():
    evidences = [
        make_evidence(
            f"e{i}",
            f"证据{i}",
            1.0 - i * 0.1,
            relation_path=[
                f"实体{i}",
                f"关系{i}",
                f"实体{i + 1}",
            ],
        )
        for i in range(5)
    ]

    result = build_context(
        "测试问题",
        evidences,
        max_paths=2,
    )

    assert "[路径 1]" in result
    assert "[路径 2]" in result
    assert "[路径 3]" not in result

def test_build_context_formats_relation_path_as_triplet():
    evidence = make_evidence(
        "e1",
        "三元组关系证据",
        0.9,
        retrieval_method="graph",
        relation_path=[
            "实体A",
            "关系1",
            "实体B",
        ],
    )

    result = build_context("测试问题", [evidence])

    assert "实体A --[关系1]--> 实体B" in result


def test_build_context_formats_relation_path_as_dict():
    evidence = make_evidence(
        "e1",
        "字典关系证据",
        0.9,
        retrieval_method="graph",
        relation_path=[
            {
                "source": "实体A",
                "relation": "关系1",
                "target": "实体B",
            }
        ],
    )

    result = build_context("测试问题", [evidence])

    assert "实体A --[关系1]--> 实体B" in result


def test_build_context_formats_stringified_relation_path():
    evidence = make_evidence(
        "e1",
        "字符串关系证据",
        0.9,
        retrieval_method="graph",
        relation_path=[
            "{'source': '实体A', 'relation': '关系1', 'target': '实体B'}"
        ],
    )

    result = build_context("测试问题", [evidence])

    assert "实体A --[关系1]--> 实体B" in result

def test_same_evidence_id_keeps_different_relation_paths():
    evidences = [
        Evidence(
            evidence_id="graph_one_hop",
            content="项目属于传统舞蹈",
            retrieval_method="graph_retriever",
            score=0.7,
            source_id="graph_one_hop",
            relation_path=[
                {
                    "source": "InheritProject:001",
                    "relation": "BELONGS_TO",
                    "target": "Category:传统舞蹈",
                }
            ],
        ),
        Evidence(
            evidence_id="graph_one_hop",
            content="项目位于吉林延边朝鲜族自治州",
            retrieval_method="graph_retriever",
            score=0.7,
            source_id="graph_one_hop",
            relation_path=[
                {
                    "source": "InheritProject:001",
                    "relation": "LOCATED_IN",
                    "target": "Region:吉林延边朝鲜族自治州",
                }
            ],
        ),
    ]

    context = build_context(
        query="项目和吉林延边朝鲜族自治州是什么关系？",
        evidences=evidences,
    )

    assert "BELONGS_TO" in context
    assert "LOCATED_IN" in context