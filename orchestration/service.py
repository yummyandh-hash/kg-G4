from typing import List, Optional, Protocol

from orchestration.models import (
    AnswerResponse,
    Evidence,
    RetrievalContext,
    RouteDecision,
)


class Router(Protocol):
    """统一的路由器接口，后续接入 A"""

    def route(self, query: str) -> RouteDecision:
        ...


class AnswerGenerator(Protocol):
    """统一的答案生成接口，后续接入 LLM"""

    def generate(
        self,
        query: str,
        evidences: List[Evidence],
    ) -> str:
        ...


class QueryService:
    """E 模块的统一查询编排服务。"""

    def __init__(
        self,
        router: Optional[Router] = None,
        answer_generator: Optional[AnswerGenerator] = None,
    ):
        self.router = router
        self.answer_generator = answer_generator

    def query(self, question: str) -> AnswerResponse:
        """执行一次完整查询"""

        if self.router is not None:
            decision = self.router.route(question)
        else:
            decision = RouteDecision(
                query_type="unknown",
                complexity_score=0.0,
                selected_route="mock",
                reason="E-02 router not connected",
            )

        context = RetrievalContext(
            query_type=decision.query_type,
            complexity_score=decision.complexity_score,
        )

        # 当前 D 尚未合入 main，因此暂时使用空 evidence。
        evidences: List[Evidence] = []

        if self.answer_generator is not None:
            answer = self.answer_generator.generate(
                question,
                evidences,
            )
        else:
            answer = f"这是对问题“{question}”的测试回答。"

        return AnswerResponse(
            answer=answer,
            query_type=context.query_type,
            complexity_score=context.complexity_score,
            selected_route=decision.selected_route,
            route_reason=decision.reason,
            evidences=evidences,
            paths=[],
            sources=[],
            timing={},
        )