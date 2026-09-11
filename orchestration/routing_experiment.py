from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from orchestration.retriever_adapters import AnalysisRouter
from orchestration.routing_benchmark import (
    DualRouteBenchmark,
    RouterComparisonRecord,
    RoutingBenchmarkQuery,
    RoutingBenchmarkRecord,
    compare_router_decisions,
    save_benchmark_records,
    summarize_router_comparison,
    summarize_router_comparison_by_type,
    train_router_v2_from_records,
)


@dataclass(frozen=True)
class RoutingExperimentResult:
    records: list[RoutingBenchmarkRecord]
    comparisons: list[RouterComparisonRecord]
    summary: dict


def load_benchmark_queries(path: str | Path) -> list[RoutingBenchmarkQuery]:
    """Read JSONL benchmark queries or plain-text query lines."""

    queries = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("{"):
            data = json.loads(stripped)
            queries.append(
                RoutingBenchmarkQuery(
                    query=data["query"],
                    query_type=data.get("query_type"),
                    complexity_score=data.get("complexity_score"),
                    expected_route=data.get("expected_route")
                    or data.get("best_route"),
                )
            )
        else:
            queries.append(RoutingBenchmarkQuery(query=stripped))

    return queries


def run_routing_experiment(
    retriever,
    queries: Iterable[RoutingBenchmarkQuery],
    *,
    top_k: int = 5,
    records_out: str | Path | None = None,
    model_out: str | Path | None = None,
    summary_out: str | Path | None = None,
) -> RoutingExperimentResult:
    benchmark = DualRouteBenchmark(
        retriever,
        router=AnalysisRouter(),
        top_k=top_k,
    )
    records = benchmark.run(queries)
    router_v2 = train_router_v2_from_records(records)
    comparisons = compare_router_decisions(
        records,
        AnalysisRouter(),
        router_v2,
    )
    summary = summarize_router_comparison(comparisons)
    summary["by_query_type"] = summarize_router_comparison_by_type(
        records,
        comparisons,
    )

    if records_out:
        save_benchmark_records(records, records_out)

    if model_out:
        router_v2.save(model_out)

    if summary_out:
        _save_summary(summary, summary_out)

    return RoutingExperimentResult(
        records=records,
        comparisons=comparisons,
        summary=summary,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Stage 2 Router V2 benchmark flow."
    )
    parser.add_argument("--queries", required=True)
    parser.add_argument("--records-out")
    parser.add_argument("--model-out")
    parser.add_argument("--summary-out")
    parser.add_argument("--chunks-file", default="data/chunks/chunks.jsonl")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args(argv)

    from orchestration.stage1 import build_stage1_retriever

    result = run_routing_experiment(
        build_stage1_retriever(chunks_file=args.chunks_file),
        load_benchmark_queries(args.queries),
        top_k=args.top_k,
        records_out=args.records_out,
        model_out=args.model_out,
        summary_out=args.summary_out,
    )
    print(json.dumps(result.summary, ensure_ascii=False, indent=2))
    return 0


def _save_summary(summary: dict, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
