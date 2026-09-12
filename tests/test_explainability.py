from orchestration.explainability import build_explanation
from orchestration.models import (
    AnswerResponse,
    CitationValidation,
    Evidence,
    GraphEdge,
    GraphNode,
)


def make_evidence(
    evidence_id="e1",
    content="测试证据",
    score=0.9,
    retrieval_method="graph",
    source_id="source-1",
    source_url="https://example.com",
    entity_ids=None,
    relation_path=None,
):
    return Evidence(
        evidence_id=evidence_id,
        content=content,
        retrieval_method=retrieval_method,
        score=score,
        source_id=source_id,
        source_url=source_url,
        entity_ids=entity_ids or [],
        relation_path=relation_path or [],
    )


def make_response(
    evidences=None,
    paths=None,
    sources=None,
    graph_nodes=None,
    graph_edges=None,
):
    return AnswerResponse(
        answer="测试答案",
        query_type="relation",
        complexity_score=0.65,
        selected_route="graph",
        route_reason="高复杂度问题选择图检索",
        evidences=evidences or [],
        paths=paths or [],
        sources=sources or [],
        timing={"retrieval": 0.12, "generation": 0.8},
        graph_nodes=graph_nodes or [],
        graph_edges=graph_edges or [],
    )


def test_build_explanation_contains_router_decision():
    response = make_response()

    result = build_explanation(response)

    assert result["query_type"] == "relation"
    assert result["complexity_score"] == 0.65
    assert result["selected_retriever"] == "graph"
    assert result["route_reason"] == "高复杂度问题选择图检索"


def test_build_explanation_formats_evidence():
    evidence = make_evidence(
        evidence_id="e1",
        content="朝鲜族农乐舞流传于吉林地区",
        score=0.95,
        retrieval_method="graph",
        source_id="source-1",
        source_url="https://example.com/1",
        entity_ids=["entity-a", "entity-b"],
        relation_path=[
            "实体A",
            "关系1",
            "实体B",
        ],
    )

    result = build_explanation(
        make_response(evidences=[evidence])
    )

    assert result["evidence_count"] == 1

    item = result["evidence"][0]

    assert item["index"] == 1
    assert item["evidence_id"] == "e1"
    assert item["content"] == "朝鲜族农乐舞流传于吉林地区"
    assert item["retrieval_method"] == "graph"
    assert item["score"] == 0.95
    assert item["source_id"] == "source-1"
    assert item["source_url"] == "https://example.com/1"
    assert item["entity_ids"] == ["entity-a", "entity-b"]
    assert item["relation_path"] == [
        "实体A",
        "关系1",
        "实体B",
    ]


def test_build_explanation_collects_relation_paths():
    response = make_response(
        paths=[
            [
                "实体A",
                "关系1",
                "实体B",
            ],
            [
                "实体B",
                "关系2",
                "实体C",
            ],
        ]
    )

    result = build_explanation(response)

    assert result["path_count"] == 2
    assert result["relation_paths"][0] == [
        "实体A",
        "关系1",
        "实体B",
    ]
    assert result["relation_paths"][1] == [
        "实体B",
        "关系2",
        "实体C",
    ]


def test_build_explanation_collects_sources():
    response = make_response(
        sources=[
            "source-1",
            "source-2",
        ]
    )

    result = build_explanation(response)

    assert result["source_count"] == 2
    assert result["sources"] == [
        "source-1",
        "source-2",
    ]


def test_build_explanation_formats_graph():
    nodes = [
        GraphNode(
            node_id="entity-a",
            label="CulturalElement",
            properties={"name": "实体A"},
        ),
        GraphNode(
            node_id="entity-b",
            label="Region",
            properties={"name": "实体B"},
        ),
    ]

    edges = [
        GraphEdge(
            source="entity-a",
            target="entity-b",
            relation="LOCATED_IN",
            properties={},
        )
    ]

    response = make_response(
        graph_nodes=nodes,
        graph_edges=edges,
    )

    result = build_explanation(response)

    graph = result["graph"]

    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1

    assert graph["nodes"][0]["id"] == "entity-a"
    assert graph["nodes"][0]["label"] == "CulturalElement"
    assert graph["nodes"][0]["properties"]["name"] == "实体A"

    assert graph["edges"][0]["source"] == "entity-a"
    assert graph["edges"][0]["target"] == "entity-b"
    assert graph["edges"][0]["relation"] == "LOCATED_IN"


def test_build_explanation_collects_timing():
    response = make_response()

    result = build_explanation(response)

    assert result["timing"]["retrieval"] == 0.12
    assert result["timing"]["generation"] == 0.8


def test_build_explanation_handles_empty_response():
    response = make_response()

    result = build_explanation(response)

    assert result["evidence"] == []
    assert result["evidence_count"] == 0
    assert result["relation_paths"] == []
    assert result["path_count"] == 0
    assert result["sources"] == []
    assert result["source_count"] == 0
    assert result["graph"]["nodes"] == []
    assert result["graph"]["edges"] == []
    assert result["graph"]["node_count"] == 0
    assert result["graph"]["edge_count"] == 0


def test_build_explanation_includes_citation_validation():
    response = AnswerResponse(
        answer="ok",
        query_type="fact",
        complexity_score=0.2,
        selected_route="vector",
        route_reason="test",
        citation_validation=CitationValidation(
            label="SUPPORTED",
            confidence=0.9,
            reason="supported",
            evidences=[{"chunk_id": "chunk-1"}],
        ),
    )

    explanation = build_explanation(response)

    assert explanation["citation_validation"] == {
        "label": "SUPPORTED",
        "confidence": 0.9,
        "reason": "supported",
        "evidences": [{"chunk_id": "chunk-1"}],
    }