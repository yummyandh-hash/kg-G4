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
    build_experiment_summary,
    compare_router_decisions,
    load_benchmark_records,
    save_benchmark_records,
    save_router_comparisons,
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
                    query=data.get("query") or data["question"],
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
    comparisons_out: str | Path | None = None,
    model_out: str | Path | None = None,
    summary_out: str | Path | None = None,
    metadata: dict | None = None,
) -> RoutingExperimentResult:
    queries = list(queries)
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
    summary = build_experiment_summary(
        records,
        comparisons,
        metadata={
            "mode": "live_retriever",
            "queries_total": len(queries),
            "top_k": top_k,
            **(metadata or {}),
        },
    )

    if records_out:
        save_benchmark_records(records, records_out)

    if comparisons_out:
        save_router_comparisons(comparisons, comparisons_out)

    if model_out:
        router_v2.save(model_out)

    if summary_out:
        _save_summary(summary, summary_out)

    return RoutingExperimentResult(
        records=records,
        comparisons=comparisons,
        summary=summary,
    )


def run_routing_experiment_from_records(
    records: Iterable[RoutingBenchmarkRecord],
    *,
    comparisons_out: str | Path | None = None,
    model_out: str | Path | None = None,
    summary_out: str | Path | None = None,
    metadata: dict | None = None,
) -> RoutingExperimentResult:
    records = list(records)
    router_v2 = train_router_v2_from_records(records)
    comparisons = compare_router_decisions(
        records,
        AnalysisRouter(),
        router_v2,
    )
    summary = build_experiment_summary(
        records,
        comparisons,
        metadata={
            "mode": "saved_records",
            **(metadata or {}),
        },
    )

    if model_out:
        router_v2.save(model_out)

    if comparisons_out:
        save_router_comparisons(comparisons, comparisons_out)

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
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--queries")
    input_group.add_argument("--records-in")
    parser.add_argument("--records-out")
    parser.add_argument("--comparisons-out")
    parser.add_argument("--model-out")
    parser.add_argument("--summary-out")
    parser.add_argument("--chunks-file", default="data/chunks/chunks.jsonl")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args(argv)

    if args.records_in:
        result = run_routing_experiment_from_records(
            load_benchmark_records(args.records_in),
            comparisons_out=args.comparisons_out,
            model_out=args.model_out,
            summary_out=args.summary_out,
            metadata={"records_in": args.records_in},
        )
    else:
        from orchestration.stage1 import build_stage1_retriever

        result = run_routing_experiment(
            build_stage1_retriever(chunks_file=args.chunks_file),
            load_benchmark_queries(args.queries),
            top_k=args.top_k,
            records_out=args.records_out,
            comparisons_out=args.comparisons_out,
            model_out=args.model_out,
            summary_out=args.summary_out,
            metadata={
                "queries_file": args.queries,
                "chunks_file": args.chunks_file,
            },
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
