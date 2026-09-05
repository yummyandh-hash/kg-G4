import logging
from time import perf_counter
from typing import Dict

from orchestration.adaptive_router import AdaptiveRouter
from orchestration.complexity_scorer import ComplexityScorer
from orchestration.models import (
    AnswerResponse,
    RetrievalContext,
    Retriever,
)
from orchestration.query_analyzer import QueryAnalyzer


logger = logging.getLogger(__name__)


class OrchestrationPipeline:
    """AP-ICH-GraphRAG 检索编排 Pipeline V0。"""

    def __init__(
        self,
        retrievers: Dict[str, Retriever],
        top_k: int = 5,
    ):
        self.retrievers = retrievers
        self.top_k = top_k

        self.query_analyzer = QueryAnalyzer()
        self.complexity_scorer = ComplexityScorer()
        self.router = AdaptiveRouter()

    def run(self, query: str) -> AnswerResponse:
        """执行查询分析、路由和检索。"""

        total_start = perf_counter()

        query_type = self.query_analyzer.analyze(query)
        complexity_score = self.complexity_scorer.score(query)

        decision = self.router.route(
            query_type=query_type,
            complexity_score=complexity_score,
        )

        logger.info(
            "route query_type=%s complexity=%.2f route=%s reason=%s",
            decision.query_type,
            decision.complexity_score,
            decision.selected_route,
            decision.reason,
        )

        retriever = self.retrievers.get(decision.selected_route)

        if retriever is None:
            raise ValueError(
                f"No retriever registered for route: "
                f"{decision.selected_route}"
            )

        context = RetrievalContext(
            query_type=query_type,
            complexity_score=complexity_score,
            top_k=self.top_k,
        )

        retrieval_start = perf_counter()
        evidences = retriever.retrieve(query, context)
        retrieval_time = perf_counter() - retrieval_start

        paths = [
            evidence.relation_path
            for evidence in evidences
            if evidence.relation_path
        ]

        sources = list(
            dict.fromkeys(
                evidence.source_url
                for evidence in evidences
                if evidence.source_url
            )
        )

        total_time = perf_counter() - total_start

        return AnswerResponse(
            answer="",
            query_type=query_type,
            complexity_score=complexity_score,
            selected_route=decision.selected_route,
            route_reason=decision.reason,
            evidences=evidences,
            paths=paths,
            sources=sources,
            timing={
                "retrieval": round(retrieval_time, 6),
                "total": round(total_time, 6),
            },
        )