import pytest

from orchestration.adaptive_router import AdaptiveRouter
from orchestration.mock_retrievers import (
    MockGraphRetriever,
    MockVectorRetriever,
)
from orchestration.models import RetrievalContext


@pytest.mark.parametrize(
    ("query_type", "complexity_score", "expected_route"),
    [
        ("fact", 0.15, "vector"),
        ("relation", 0.30, "graph"),
        ("comparison", 0.40, "graph"),
        ("constraint", 0.35, "graph"),
        ("fact", 0.70, "graph"),
    ],
)
def test_router_routes(query_type, complexity_score, expected_route):
    router = AdaptiveRouter()

    decision = router.route(query_type, complexity_score)

    assert decision.selected_route == expected_route
    assert decision.reason


def test_mock_retrievers_return_evidence():
    context = RetrievalContext(
        query_type="fact",
        complexity_score=0.2,
    )

    vector_evidence = MockVectorRetriever().retrieve("什么是苏绣？", context)
    graph_evidence = MockGraphRetriever().retrieve("苏绣和苏州有什么关系？", context)

    assert vector_evidence[0].retrieval_method == "vector"
    assert graph_evidence[0].retrieval_method == "graph"
    assert graph_evidence[0].relation_path