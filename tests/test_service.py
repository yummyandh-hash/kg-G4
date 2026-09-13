from orchestration.models import Evidence, RouteDecision
from orchestration.service import QueryService


class MockRouterForTest:
    def route(self, query: str) -> RouteDecision:
        return RouteDecision(
            query_type="multi_hop",
            complexity_score=0.8,
            selected_route="graph",
            reason="test route",
        )


class MockRetrieverForTest:
    def retrieve(
        self,
        query: str,
        context,
    ) -> list[Evidence]:
        return [
            Evidence(
                evidence_id="test-evidence-001",
                content="蜀绣主要流传于四川地区。",
                retrieval_method="graph",
                score=0.9,
                source_id="test-source-001",
                source_url="https://www.ihchina.cn/",
                entity_ids=["蜀绣", "四川"],
                relation_path=[
                    {
                        "source": "蜀绣",
                        "relation": "分布于",
                        "target": "四川",
                    }
                ],
            )
        ]


class MockAnswerGeneratorForTest:
    def generate(
        self,
        query: str,
        evidences: list[Evidence],
    ) -> str:
        return f"answer from evidence: {query}"


class MockCitationServiceForTest:
    def __init__(self):
        self.calls = []

    def verify_claim(self, claim: str, chunk_ids: list[str]):
        self.calls.append((claim, chunk_ids))
        return {
            "label": "SUPPORTED",
            "confidence": 0.92,
            "reason": "answer is supported by retrieved chunks",
            "evidences": [{"chunk_id": chunk_ids[0]}],
        }


def test_query_service_default():
    service = QueryService()

    response = service.query("什么是蜀绣？")

    assert response.answer
    assert response.query_type == "knowledge"
    assert response.complexity_score == 0.3
    assert response.selected_route == "vector"

    assert len(response.evidences) > 0
    assert response.evidences[0].retrieval_method == "vector"
    assert response.evidences[0].source_id == "mock-source-001"

    assert len(response.paths) > 0
    assert response.paths[0] == [
        {
            "source": "蜀绣",
            "relation": "分布于",
            "target": "四川",
        }
    ]

    assert len(response.sources) > 0
    assert response.sources[0] == "mock-source-001"

    assert len(response.graph_nodes) > 0
    assert len(response.graph_edges) > 0

    assert "routing" in response.timing
    assert "retrieval" in response.timing
    assert "answer_generation" in response.timing
    assert "citation_verification" in response.timing
    assert "total" in response.timing
    assert response.citation_validation is None


def test_query_service_with_dependencies():
    service = QueryService(
        router=MockRouterForTest(),
        retriever=MockRetrieverForTest(),
        answer_generator=MockAnswerGeneratorForTest(),
    )

    response = service.query("蜀绣和四川有什么关系？")

    assert response.answer == "answer from evidence: 蜀绣和四川有什么关系？"
    assert response.query_type == "multi_hop"
    assert response.complexity_score == 0.8
    assert response.selected_route == "graph"
    assert response.route_reason == "test route"

    assert len(response.evidences) == 1
    assert response.evidences[0].evidence_id == "test-evidence-001"
    assert response.evidences[0].retrieval_method == "graph"
    assert response.evidences[0].score == 0.9

    assert response.paths == [
        [
            {
                "source": "蜀绣",
                "relation": "分布于",
                "target": "四川",
            }
        ]
    ]

    assert response.sources == ["test-source-001"]

    node_ids = {node.node_id for node in response.graph_nodes}
    assert node_ids == {"蜀绣", "四川"}

    assert len(response.graph_edges) == 1
    edge = response.graph_edges[0]
    assert edge.source == "蜀绣"
    assert edge.target == "四川"
    assert edge.relation == "分布于"


def test_query_service_can_verify_citations():
    citation_service = MockCitationServiceForTest()
    service = QueryService(
        router=MockRouterForTest(),
        retriever=MockRetrieverForTest(),
        answer_generator=MockAnswerGeneratorForTest(),
        citation_service=citation_service,
    )

    response = service.query("relation question")

    assert citation_service.calls == [
        (
            "answer from evidence: relation question",
            ["test-source-001"],
        )
    ]
    assert response.citation_validation is not None
    assert response.citation_validation.label == "SUPPORTED"
    assert response.citation_validation.confidence == 0.92
    assert response.citation_validation.evidences == [
        {"chunk_id": "test-source-001"}
    ]
