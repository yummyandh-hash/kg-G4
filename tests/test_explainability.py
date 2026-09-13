from orchestration.explainability import build_explanation
from orchestration.models import (
    AnswerResponse,
    CitationValidation,
    Evidence,
    GraphEdge,
    GraphNode,
)


def test_build_explanation():
    response = AnswerResponse(
        answer="蜀绣是中国传统刺绣的重要代表。",
        query_type="knowledge",
        complexity_score=0.3,
        selected_route="vector",
        route_reason="测试路由",
        evidences=[
            Evidence(
                evidence_id="e1",
                content="蜀绣主要流传于四川地区。",
                retrieval_method="vector",
                score=0.95,
                source_id="s1",
                source_url="https://www.ihchina.cn/",
                relation_path=[
                    {
                        "source": "蜀绣",
                        "relation": "分布于",
                        "target": "四川",
                    }
                ],
            )
        ],
        paths=[
            [
                {
                    "source": "蜀绣",
                    "relation": "分布于",
                    "target": "四川",
                }
            ]
        ],
        sources=["s1"],
        graph_nodes=[
            GraphNode(
                node_id="蜀绣",
                label="蜀绣",
            ),
            GraphNode(
                node_id="四川",
                label="四川",
            ),
        ],
        graph_edges=[
            GraphEdge(
                source="蜀绣",
                target="四川",
                relation="分布于",
            )
        ],
    )

    explanation = build_explanation(response)

    assert explanation["selected_retriever"] == "vector"
    assert explanation["route_reason"] == "测试路由"

    assert len(explanation["evidence"]) == 1
    assert (
        explanation["evidence"][0]["evidence_id"]
        == "e1"
    )

    assert explanation["relation_paths"] == [
        [
            {
                "source": "蜀绣",
                "relation": "分布于",
                "target": "四川",
            }
        ]
    ]

    assert explanation["sources"] == ["s1"]

    assert len(explanation["graph"]["nodes"]) == 2
    assert len(explanation["graph"]["edges"]) == 1


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
