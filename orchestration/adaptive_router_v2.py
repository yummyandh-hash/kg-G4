from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from typing import Iterable

from orchestration.adaptive_router import AdaptiveRouter
from orchestration.complexity_scorer import ComplexityScorer
from orchestration.models import RouteDecision
from orchestration.query_analyzer import QueryAnalyzer


FEATURE_NAMES = (
    "complexity_score",
    "query_length",
    "type_fact",
    "type_relation",
    "type_comparison",
    "type_constraint",
    "graph_query_type",
    "comparison_cue",
    "relation_cue",
    "constraint_cue",
    "multi_entity_cue",
    "multi_hop_cue",
    "multi_condition_cue",
)


@dataclass(frozen=True)
class RoutingTrainingExample:
    """One benchmark row used to calibrate Router V2."""

    query: str
    best_route: str
    query_type: str | None = None
    complexity_score: float | None = None


class QueryFeatureExtractor:
    """Turn Stage 1 rule outputs into numeric features."""

    def __init__(
        self,
        analyzer: QueryAnalyzer | None = None,
        scorer: ComplexityScorer | None = None,
    ):
        self.analyzer = analyzer or QueryAnalyzer()
        self.scorer = scorer or ComplexityScorer()

    def analyze(self, query: str) -> tuple[str, float, dict[str, float]]:
        query_type = self.analyzer.analyze(query)
        complexity_score = self.scorer.score(query)
        return query_type, complexity_score, self.features(
            query,
            query_type,
            complexity_score,
        )

    def features(
        self,
        query: str,
        query_type: str,
        complexity_score: float,
    ) -> dict[str, float]:
        stripped = query.strip()
        return {
            "complexity_score": float(complexity_score),
            "query_length": min(len(stripped), 80) / 80.0,
            "type_fact": _one_hot(query_type, "fact"),
            "type_relation": _one_hot(query_type, "relation"),
            "type_comparison": _one_hot(query_type, "comparison"),
            "type_constraint": _one_hot(query_type, "constraint"),
            "graph_query_type": float(
                query_type in AdaptiveRouter.GRAPH_QUERY_TYPES
            ),
            "comparison_cue": _contains_any(
                stripped,
                QueryAnalyzer.COMPARISON_CUES,
            ),
            "relation_cue": _contains_any(
                stripped,
                QueryAnalyzer.RELATION_CUES,
            ),
            "constraint_cue": _contains_any(
                stripped,
                QueryAnalyzer.CONSTRAINT_CUES,
            ),
            "multi_entity_cue": _contains_any(
                stripped,
                ComplexityScorer.MULTI_ENTITY_CUES,
            ),
            "multi_hop_cue": _contains_any(
                stripped,
                ComplexityScorer.MULTI_HOP_CUES,
            ),
            "multi_condition_cue": _contains_any(
                stripped,
                ComplexityScorer.MULTI_CONDITION_CUES,
            ),
        }


class AdaptiveRouterV2:
    """Lightweight calibrated router trained from benchmark labels."""

    def __init__(
        self,
        *,
        threshold: float = 0.5,
        learning_rate: float = 0.2,
        epochs: int = 300,
        extractor: QueryFeatureExtractor | None = None,
        fallback_router: AdaptiveRouter | None = None,
    ):
        self.threshold = threshold
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.extractor = extractor or QueryFeatureExtractor()
        self.fallback_router = fallback_router or AdaptiveRouter()
        self.weights = {name: 0.0 for name in FEATURE_NAMES}
        self.bias = 0.0
        self.is_trained = False

    def fit(
        self,
        examples: Iterable[RoutingTrainingExample],
    ) -> AdaptiveRouterV2:
        rows = list(examples)
        if not rows:
            self.is_trained = False
            return self

        positives = sum(1 for row in rows if _label(row.best_route) == 1)
        negatives = len(rows) - positives
        self.bias = _safe_logit(positives, negatives)
        self.weights = {name: 0.0 for name in FEATURE_NAMES}

        for _ in range(self.epochs):
            gradients = {name: 0.0 for name in FEATURE_NAMES}
            bias_gradient = 0.0

            for row in rows:
                _, _, features = self._features_for(row)
                expected = _label(row.best_route)
                predicted = self._probability(features)
                error = predicted - expected

                bias_gradient += error
                for name in FEATURE_NAMES:
                    gradients[name] += error * features[name]

            row_count = float(len(rows))
            self.bias -= self.learning_rate * (bias_gradient / row_count)
            for name in FEATURE_NAMES:
                self.weights[name] -= (
                    self.learning_rate * gradients[name] / row_count
                )

        self.is_trained = True
        return self

    def route(self, query: str) -> RouteDecision:
        query_type, complexity_score, features = self.extractor.analyze(query)
        return self.route_from_features(
            query_type,
            complexity_score,
            features,
        )

    def route_from_features(
        self,
        query_type: str,
        complexity_score: float,
        features: dict[str, float],
    ) -> RouteDecision:
        if not self.is_trained:
            decision = self.fallback_router.route(query_type, complexity_score)
            return RouteDecision(
                query_type=decision.query_type,
                complexity_score=decision.complexity_score,
                selected_route=decision.selected_route,
                reason=f"Router V2 untrained; fallback to V1: {decision.reason}",
                confidence=0.5,
            )

        graph_probability = self._probability(features)
        selected_route = (
            "graph" if graph_probability >= self.threshold else "vector"
        )
        confidence = (
            graph_probability
            if selected_route == "graph"
            else 1.0 - graph_probability
        )

        return RouteDecision(
            query_type=query_type,
            complexity_score=complexity_score,
            selected_route=selected_route,
            reason=(
                f"calibrated graph_probability={graph_probability:.2f}; "
                f"strongest_signal={self._strongest_signal(features)}"
            ),
            confidence=round(confidence, 4),
        )

    def _features_for(
        self,
        row: RoutingTrainingExample,
    ) -> tuple[str, float, dict[str, float]]:
        query_type = row.query_type or self.extractor.analyzer.analyze(
            row.query
        )
        complexity_score = (
            row.complexity_score
            if row.complexity_score is not None
            else self.extractor.scorer.score(row.query)
        )
        features = self.extractor.features(
            row.query,
            query_type,
            complexity_score,
        )
        return query_type, complexity_score, features

    def _probability(self, features: dict[str, float]) -> float:
        score = self.bias
        for name in FEATURE_NAMES:
            score += self.weights[name] * features[name]
        return _sigmoid(score)

    def _strongest_signal(self, features: dict[str, float]) -> str:
        weighted = {
            name: abs(self.weights[name] * features[name])
            for name in FEATURE_NAMES
        }
        return max(weighted, key=weighted.get)


def _contains_any(query: str, cues: tuple[str, ...]) -> float:
    return float(any(cue in query for cue in cues))


def _label(route: str) -> int:
    normalized = route.strip().lower()
    if normalized == "graph":
        return 1
    if normalized == "vector":
        return 0
    raise ValueError(f"Unsupported best_route label: {route}")


def _one_hot(value: str, expected: str) -> float:
    return float(value == expected)


def _safe_logit(positives: int, negatives: int) -> float:
    positive_rate = (positives + 1.0) / (positives + negatives + 2.0)
    return log(positive_rate / (1.0 - positive_rate))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)
