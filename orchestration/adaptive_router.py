from orchestration.models import RouteDecision


class AdaptiveRouter:
    """Choose vector or graph retrieval from query type and complexity."""

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
