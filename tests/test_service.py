from orchestration.models import (
    AnswerResponse,
    Evidence,
    GraphEdge,
    GraphNode,
)
from orchestration.service import QueryService


class MockDefaultRouterForTest:
    def route(self, query: str):
        from orchestration.models import RouteDecision

        return RouteDecision(
            query_type="knowledge",
            complexity_score=0.3,
            selected_route="vector",
            reason="测试默认路由",
            confidence=0.9,
        )


class MockRouterForTest:
    def route(self, query: str):
        from orchestration.models import RouteDecision

        return RouteDecision(
            query_type="multi_hop",
            complexity_score=0.8,
            selected_route="graph",
            reason="复杂关系问题选择图检索",
            confidence=0.9,
        )


class MockDefaultRetrieverForTest:
    def retrieve(self, query, context=None, top_k=5):
        return [
            Evidence(
                evidence_id="mock-evidence-001",
                content="蜀绣是中国传统刺绣的重要代表。",
                retrieval_method="vector",
                score=0.95,
                source_id="mock-source-001",
                source_url="https://www.ihchina.cn/",
                entity_ids=["蜀绣"],
                relation_path=[],
            )
        ]


class MockRetrieverForTest:
    def retrieve(self, query, context=None, top_k=5):
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
                    "蜀绣",
                    "分布于",
                    "四川",
                ],
            )
        ]


class MockAnswerGeneratorForTest:
    def generate(
        self,
        question: str,
        context: str,
    ) -> str:
        return f"基于检索证据回答：{question}"


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
    """测试 QueryService 的基础 Vector 检索流程。"""

    service = QueryService(
        router=MockDefaultRouterForTest(),
        retriever=MockDefaultRetrieverForTest(),
        generator=MockAnswerGeneratorForTest(),
    )

    response = service.query("什么是蜀绣？")

    assert response.answer == "基于检索证据回答：什么是蜀绣？"

    # Router
    assert response.query_type == "knowledge"
    assert response.complexity_score == 0.3
    assert response.selected_route == "vector"

    # Evidence
    assert len(response.evidences) == 1
    assert response.evidences[0].retrieval_method == "vector"
    assert response.evidences[0].source_id == "mock-source-001"

    # Source
    assert response.sources == [
        "mock-source-001"
    ]

    # Graph
    assert len(response.graph_nodes) >= 0
    assert len(response.graph_edges) >= 0

    # Timing
    assert "total_ms" in response.timing or "total" in response.timing


def test_query_service_with_dependencies():
    """测试接入 Router / Retriever / Generator 后的数据传递。"""

    service = QueryService(
        router=MockRouterForTest(),
        retriever=MockRetrieverForTest(),
        generator=MockAnswerGeneratorForTest(),
    )

    response = service.query("蜀绣和四川有什么关系？")

    assert response.answer == (
        "基于检索证据回答：蜀绣和四川有什么关系？"
    )

    # Router
    assert response.query_type == "multi_hop"
    assert response.complexity_score == 0.8
    assert response.selected_route == "graph"

    # Evidence
    assert len(response.evidences) == 1
    assert response.evidences[0].retrieval_method == "graph"
    assert response.evidences[0].score == 0.9

    # Path
    assert response.paths == [
        [
            "蜀绣",
            "分布于",
            "四川",
        ]
    ]

    # Source
    assert response.sources == ["test-source-001"]

    # Graph Nodes
    assert len(response.graph_nodes) == 2

    node_ids = {
        node.node_id
        for node in response.graph_nodes
    }

    assert node_ids == {
        "蜀绣",
        "四川",
    }

    # Graph Edge
    assert len(response.graph_edges) == 1

    edge = response.graph_edges[0]

    assert edge.source == "蜀绣"
    assert edge.target == "四川"
    assert edge.relation == "分布于"

    # Timing
    assert "routing" in response.timing
    assert "retrieval" in response.timing
    assert "answer_generation" in response.timing
    assert "citation_verification" in response.timing
    assert "total" in response.timing

    # 未提供 citation service 时不进行验证
    assert response.citation_validation is None


def test_query_service_can_verify_citations():
    citation_service = MockCitationServiceForTest()

    service = QueryService(
        router=MockRouterForTest(),
        retriever=MockRetrieverForTest(),
        generator=MockAnswerGeneratorForTest(),
        citation_service=citation_service,
    )

    response = service.query("relation question")

    assert citation_service.calls == [
        (
            "基于检索证据回答：relation question",
            ["test-source-001"],
        )
    ]

    assert response.citation_validation is not None
    assert response.citation_validation.label == "SUPPORTED"
    assert response.citation_validation.confidence == 0.92
    assert response.citation_validation.evidences == [
        {"chunk_id": "test-source-001"}
    ]


def test_path_edges_supports_stringified_dict():
    from orchestration.service import _path_edges

    path = [
        "{'source': 'Project:A', "
        "'target': 'Region:B', "
        "'relation': 'LOCATED_IN'}"
    ]

    result = _path_edges(path)

    assert result == [
        (
            "Project:A",
            "LOCATED_IN",
            "Region:B",
        )
    ]


def test_path_entities_supports_stringified_dict():
    from orchestration.service import _path_entities

    path = [
        "{'source': 'Project:A', "
        "'target': 'Region:B', "
        "'relation': 'LOCATED_IN'}"
    ]

    result = _path_entities(path)

    assert result == [
        "Project:A",
        "Region:B",
    ]