from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable, Protocol

from orchestration.adaptive_router_v2 import (
    AdaptiveRouterV2,
    RoutingTrainingExample,
)
from orchestration.models import Evidence, RetrievalContext
from orchestration.retriever_adapters import AnalysisRouter


@dataclass(frozen=True)
class RoutingBenchmarkQuery:
    query: str
    query_type: str | None = None
    complexity_score: float | None = None
    expected_route: str | None = None


@dataclass(frozen=True)
class RetrieverTrial:
    route: str
    evidences: list[Evidence]
    elapsed: float
    error: str | None = None


@dataclass(frozen=True)
class RoutingBenchmarkRecord:
    query: str
    query_type: str
    complexity_score: float
    vector: RetrieverTrial
    graph: RetrieverTrial
    best_route: str
    label_source: str


@dataclass(frozen=True)
class RouterComparisonRecord:
    query: str
    best_route: str
    v1_route: str
    v2_route: str
    v1_correct: bool
    v2_correct: bool
    v2_confidence: float | None


class RetrieverLike(Protocol):
    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        ...


class RouterLike(Protocol):
    def route(self, query: str):
        ...


class DualRouteBenchmark:
    """Run the same query through vector and graph routes."""

    def __init__(
        self,
        retriever: RetrieverLike,
        *,
        router: AnalysisRouter | None = None,
        top_k: int = 5,
    ):
        self.retriever = retriever
        self.router = router or AnalysisRouter()
        self.top_k = top_k

    def run(
        self,
        queries: Iterable[str | RoutingBenchmarkQuery],
    ) -> list[RoutingBenchmarkRecord]:
        return [self.run_one(item) for item in queries]

    def run_one(
        self,
        item: str | RoutingBenchmarkQuery,
    ) -> RoutingBenchmarkRecord:
        benchmark_query = _normalize_query(item)
        decision = self.router.route(benchmark_query.query)
        query_type = benchmark_query.query_type or decision.query_type
        complexity_score = (
            benchmark_query.complexity_score
            if benchmark_query.complexity_score is not None
            else decision.complexity_score
        )

        vector = self._trial(
            "vector",
            benchmark_query.query,
            query_type,
            complexity_score,
        )
        graph = self._trial(
            "graph",
            benchmark_query.query,
            query_type,
            complexity_score,
        )

        if benchmark_query.expected_route:
            best_route = benchmark_query.expected_route
            label_source = "expected"
        else:
            best_route = choose_best_route(vector.evidences, graph.evidences)
            label_source = "heuristic"

        return RoutingBenchmarkRecord(
            query=benchmark_query.query,
            query_type=query_type,
            complexity_score=complexity_score,
            vector=vector,
            graph=graph,
            best_route=best_route,
            label_source=label_source,
        )

    def _trial(
        self,
        route: str,
        query: str,
        query_type: str,
        complexity_score: float,
    ) -> RetrieverTrial:
        context = RetrievalContext(
            query_type=query_type,
            complexity_score=complexity_score,
            top_k=self.top_k,
            selected_route=route,
        )
        start = perf_counter()
        try:
            evidences = self.retriever.retrieve(query, context)
            return RetrieverTrial(
                route=route,
                evidences=evidences,
                elapsed=perf_counter() - start,
            )
        except Exception as exc:
            return RetrieverTrial(
                route=route,
                evidences=[],
                elapsed=perf_counter() - start,
                error=str(exc),
            )


def choose_best_route(
    vector_evidences: list[Evidence],
    graph_evidences: list[Evidence],
) -> str:
    """A transparent starter labeler; manual labels should override it."""

    if graph_evidences and not vector_evidences:
        return "graph"
    if vector_evidences and not graph_evidences:
        return "vector"

    graph_has_path = any(evidence.relation_path for evidence in graph_evidences)
    vector_has_path = any(
        evidence.relation_path for evidence in vector_evidences
    )
    if graph_has_path and not vector_has_path:
        return "graph"

    graph_score = _max_score(graph_evidences)
    vector_score = _max_score(vector_evidences)
    if graph_score > vector_score + 0.05:
        return "graph"
    return "vector"


def compare_router_decisions(
    records: Iterable[RoutingBenchmarkRecord],
    v1_router: RouterLike,
    v2_router: AdaptiveRouterV2,
) -> list[RouterComparisonRecord]:
    comparisons = []
    for record in records:
        v1_decision = v1_router.route(record.query)
        v2_decision = v2_router.route(record.query)
        comparisons.append(
            RouterComparisonRecord(
                query=record.query,
                best_route=record.best_route,
                v1_route=v1_decision.selected_route,
                v2_route=v2_decision.selected_route,
                v1_correct=v1_decision.selected_route == record.best_route,
                v2_correct=v2_decision.selected_route == record.best_route,
                v2_confidence=v2_decision.confidence,
            )
        )
    return comparisons


def training_examples_from_records(
    records: Iterable[RoutingBenchmarkRecord],
) -> list[RoutingTrainingExample]:
    return [
        RoutingTrainingExample(
            query=record.query,
            best_route=record.best_route,
            query_type=record.query_type,
            complexity_score=record.complexity_score,
        )
        for record in records
    ]


def train_router_v2_from_records(
    records: Iterable[RoutingBenchmarkRecord],
    *,
    epochs: int = 300,
    learning_rate: float = 0.2,
) -> AdaptiveRouterV2:
    router = AdaptiveRouterV2(
        epochs=epochs,
        learning_rate=learning_rate,
    )
    return router.fit(training_examples_from_records(records))


def summarize_router_comparison(
    comparisons: Iterable[RouterComparisonRecord],
) -> dict[str, float | int]:
    rows = list(comparisons)
    total = len(rows)
    v1_correct = sum(1 for row in rows if row.v1_correct)
    v2_correct = sum(1 for row in rows if row.v2_correct)

    return {
        "total": total,
        "v1_correct": v1_correct,
        "v2_correct": v2_correct,
        "v1_accuracy": _accuracy(v1_correct, total),
        "v2_accuracy": _accuracy(v2_correct, total),
        "accuracy_delta": _accuracy(v2_correct, total)
        - _accuracy(v1_correct, total),
    }


def save_benchmark_records(
    records: Iterable[RoutingBenchmarkRecord],
    path: str | Path,
) -> None:
    lines = [
        json.dumps(_record_to_dict(record), ensure_ascii=False)
        for record in records
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def load_benchmark_records(path: str | Path) -> list[RoutingBenchmarkRecord]:
    text = Path(path).read_text(encoding="utf-8")
    return [
        _record_from_dict(json.loads(line))
        for line in text.splitlines()
        if line.strip()
    ]


def _normalize_query(
    item: str | RoutingBenchmarkQuery,
) -> RoutingBenchmarkQuery:
    if isinstance(item, RoutingBenchmarkQuery):
        return item
    return RoutingBenchmarkQuery(query=item)


def _max_score(evidences: list[Evidence]) -> float:
    scores = [
        evidence.score
        for evidence in evidences
        if evidence.score is not None
    ]
    return max(scores, default=0.0)


def _accuracy(correct: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(correct / total, 4)


def _record_to_dict(record: RoutingBenchmarkRecord) -> dict:
    return {
        "query": record.query,
        "query_type": record.query_type,
        "complexity_score": record.complexity_score,
        "vector": _trial_to_dict(record.vector),
        "graph": _trial_to_dict(record.graph),
        "best_route": record.best_route,
        "label_source": record.label_source,
    }


def _record_from_dict(data: dict) -> RoutingBenchmarkRecord:
    return RoutingBenchmarkRecord(
        query=data["query"],
        query_type=data["query_type"],
        complexity_score=float(data["complexity_score"]),
        vector=_trial_from_dict(data["vector"]),
        graph=_trial_from_dict(data["graph"]),
        best_route=data["best_route"],
        label_source=data["label_source"],
    )


def _trial_to_dict(trial: RetrieverTrial) -> dict:
    return {
        "route": trial.route,
        "evidences": [
            _evidence_to_dict(evidence)
            for evidence in trial.evidences
        ],
        "elapsed": trial.elapsed,
        "error": trial.error,
    }


def _trial_from_dict(data: dict) -> RetrieverTrial:
    return RetrieverTrial(
        route=data["route"],
        evidences=[
            _evidence_from_dict(item)
            for item in data.get("evidences", [])
        ],
        elapsed=float(data.get("elapsed", 0.0)),
        error=data.get("error"),
    )


def _evidence_to_dict(evidence: Evidence) -> dict:
    return {
        "evidence_id": evidence.evidence_id,
        "content": evidence.content,
        "retrieval_method": evidence.retrieval_method,
        "score": evidence.score,
        "source_id": evidence.source_id,
        "source_url": evidence.source_url,
        "entity_ids": evidence.entity_ids,
        "relation_path": evidence.relation_path,
    }


def _evidence_from_dict(data: dict) -> Evidence:
    return Evidence(
        evidence_id=data["evidence_id"],
        content=data["content"],
        retrieval_method=data["retrieval_method"],
        score=data.get("score"),
        source_id=data.get("source_id"),
        source_url=data.get("source_url"),
        entity_ids=data.get("entity_ids", []),
        relation_path=data.get("relation_path", []),
    )
