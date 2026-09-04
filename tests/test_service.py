from orchestration.models import Evidence, RouteDecision
from orchestration.service import QueryService


class MockRouter:
    """测试用 Router。"""

    def route(self, query: str) -> RouteDecision:
        return RouteDecision(
            query_type="multi_hop",
            complexity_score=0.8,
            selected_route="graph",
            reason="测试路由",
        )


class MockAnswerGenerator:
    """测试用答案生成器。"""

    def generate(
        self,
        query: str,
        evidences: list[Evidence],
    ) -> str:
        return f"基于检索证据回答：{query}"


def test_query_service_without_dependencies():
    """测试没有接入 A / LLM 时的 Mock 行为。"""

    service = QueryService()

    response = service.query("什么是蜀绣？")

    assert response.answer == "这是对问题“什么是蜀绣？”的测试回答。"
    assert response.query_type == "unknown"
    assert response.complexity_score == 0.0
    assert response.selected_route == "mock"
    assert response.route_reason == "E-02 router not connected"
    assert response.evidences == []
    assert response.paths == []
    assert response.sources == []


def test_query_service_with_router_and_answer_generator():
    """测试接入 Router 和 AnswerGenerator 后的数据传递。"""

    service = QueryService(
        router=MockRouter(),
        answer_generator=MockAnswerGenerator(),
    )

    response = service.query("蜀绣和苏绣有什么关系？")

    assert response.answer == "基于检索证据回答：蜀绣和苏绣有什么关系？"
    assert response.query_type == "multi_hop"
    assert response.complexity_score == 0.8
    assert response.selected_route == "graph"
    assert response.route_reason == "测试路由"
    assert response.evidences == []