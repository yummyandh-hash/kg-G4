import pytest

from orchestration.mock_retrievers import (
    MockGraphRetriever,
    MockVectorRetriever,
)
from orchestration.pipeline import OrchestrationPipeline


def build_pipeline():
    return OrchestrationPipeline(
        retrievers={
            "vector": MockVectorRetriever(),
            "graph": MockGraphRetriever(),
        }
    )


@pytest.mark.parametrize(
    ("query", "expected_route"),
    [
        ("苏绣是什么？", "vector"),
        ("苏绣和苏州有什么关系？", "graph"),
    ],
)
def test_pipeline_routes_and_retrieves(query, expected_route):
    pipeline = build_pipeline()

    response = pipeline.run(query)

    assert response.selected_route == expected_route
    assert response.evidences
    assert response.evidences[0].retrieval_method == expected_route
    assert "retrieval" in response.timing
    assert "total" in response.timing


def test_pipeline_rejects_missing_retriever():
    pipeline = OrchestrationPipeline(
        retrievers={
            "vector": MockVectorRetriever(),
        }
    )

    with pytest.raises(ValueError, match="graph"):
        pipeline.run("苏绣和苏州有什么关系？")