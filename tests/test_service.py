from orchestration.models import Evidence, RouteDecision
from orchestration.service import QueryService


class MockDefaultRouterForTest:
    """测试 QueryService 的默认 Vector 路由场景。"""

    def route(self, query: str) -> RouteDecision:
        return RouteDecision(
            query_type="knowledge",
            complexity_score=0.3,
            selected_route="vector",
            reason="测试默认 Vector 路由",
        )


class MockDefaultRetrieverForTest:
    """测试 QueryService 的默认 Vector 检索场景。"""

    def retrieve(
        self,
        query: str,
        context,
    ) -> list[Evidence]:
        return [
            Evidence(
                evidence_id="mock-evidence-001",
                content="蜀绣主要流传于四川地区。",
                retrieval_method="vector",
                score=0.9,
                source_id="mock-source-001",
                source_url="https://www.ihchina.cn/",
                entity_ids=["蜀绣", "四川"],
                relation_path=[
                    "蜀绣",
                    "分布于",
                    "四川",
                ],
            )
        ]


class MockRouterForTest:
    def route(self, query: str) -> RouteDecision:
        return RouteDecision(
            query_type="multi_hop",
            complexity_score=0.8,
            selected_route="graph",
            reason="测试路由",
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


def test_query_service_default():
    """测试 QueryService 的基础 Vector 检索流程。"""

    service = QueryService(
        router=MockDefaultRouterForTest(),
        retriever=MockDefaultRetrieverForTest(),
        generator=MockAnswerGeneratorForTest(),
    )

    response = service.query("什么是蜀绣？")

    # Answer
    assert response.answer == "基于检索证据回答：什么是蜀绣？"

    # Router
    assert response.query_type == "knowledge"
    assert response.complexity_score == 0.3
    assert response.selected_route == "vector"

    # Evidence
    assert len(response.evidences) > 0
    assert response.evidences[0].retrieval_method == "vector"
    assert response.evidences[0].source_id == "mock-source-001"

    # Relation Path
    assert response.paths == [
        [
            "蜀绣",
            "分布于",
            "四川",
        ]
    ]

    # Source
    assert response.sources == [
        "mock-source-001"
    ]

    # Graph
    assert len(response.graph_nodes) > 0
    assert len(response.graph_edges) > 0

    # Timing
    assert "total_ms" in response.timing


def test_query_service_with_dependencies():
    """测试接入 Router / Retriever / Generator 后的数据传递。"""

    service = QueryService(
        router=MockRouterForTest(),
        retriever=MockRetrieverForTest(),
        generator=MockAnswerGeneratorForTest(),
    )

    response = service.query("蜀绣和苏绣有什么关系？")

    # Answer
    assert response.answer == (
        "基于检索证据回答：蜀绣和苏绣有什么关系？"
    )

    # Router
    assert response.query_type == "multi_hop"
    assert response.complexity_score == 0.8
    assert response.selected_route == "graph"
    assert response.route_reason == "测试路由"

    # Evidence
    assert len(response.evidences) == 1
    assert response.evidences[0].evidence_id == "test-evidence-001"
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
    assert response.sources == [
        "test-source-001"
    ]

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