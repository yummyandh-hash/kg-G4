from orchestration.models import RouteDecision


class AdaptiveRouter:
    """基于查询类型和复杂度的 Adaptive Router V0。"""

    COMPLEXITY_THRESHOLD = 0.5

    GRAPH_QUERY_TYPES = {
        "relation",
        "comparison",
        "constraint",
    }

    def route(
        self,
        query_type: str,
        complexity_score: float,
    ) -> RouteDecision:
        """选择 vector 或 graph 检索路线。"""

        if complexity_score >= self.COMPLEXITY_THRESHOLD:
            return RouteDecision(
                query_type=query_type,
                complexity_score=complexity_score,
                selected_route="graph",
                reason="high query complexity",
            )

        if query_type in self.GRAPH_QUERY_TYPES:
            return RouteDecision(
                query_type=query_type,
                complexity_score=complexity_score,
                selected_route="graph",
                reason=f"{query_type} query benefits from graph structure",
            )

        return RouteDecision(
            query_type=query_type,
            complexity_score=complexity_score,
            selected_route="vector",
            reason="simple factual query",
        )