from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from orchestration.models import AnswerResponse


@dataclass(frozen=True)
class AnswerBenchmarkItem:
    qid: str
    question: str
    question_type: str
    gold_answer: str | None = None
    gold_evidence: list[str] | None = None
    gold_relation_path: list[dict] | None = None
    details: object | None = None


@dataclass(frozen=True)
class AnswerBenchmarkRecord:
    qid: str
    question: str
    question_type: str
    answer: str
    selected_route: str
    retrieved_evidence: list[str]
    retrieved_evidence_details: list[dict]
    evidences: list[dict]
    gold_evidence: list[str]
    evidence_hits: list[str]
    evidence_recall: float
    graph_evidence_count: int = 0
    graph_relation_path_count: int = 0
    graph_relation_success: bool = False
    gold_relation_path_count: int = 0
    gold_answer: str | None = None
    citation_validation: dict | None = None


@dataclass(frozen=True)
class AnswerBenchmarkResult:
    records: list[AnswerBenchmarkRecord]
    summary: dict


def load_answer_benchmark(
    path: str | Path,
) -> list[AnswerBenchmarkItem]:
    items = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        data = json.loads(stripped)
        items.append(_benchmark_item_from_dict(data))

    return items


def run_answer_benchmark(
    query_service,
    items: Iterable[AnswerBenchmarkItem],
    *,
    records_out: str | Path | None = None,
    summary_out: str | Path | None = None,
    metadata: dict | None = None,
) -> AnswerBenchmarkResult:
    rows = [
        run_answer_benchmark_one(query_service, item)
        for item in items
    ]
    summary = summarize_answer_benchmark(
        rows,
        metadata=metadata,
    )

    if records_out:
        save_answer_benchmark_records(rows, records_out)

    if summary_out:
        _save_json(summary, summary_out)

    return AnswerBenchmarkResult(records=rows, summary=summary)


def run_answer_benchmark_one(
    query_service,
    item: AnswerBenchmarkItem,
) -> AnswerBenchmarkRecord:
    response = query_service.query(item.question)
    retrieved_evidence_details = _response_evidence_details(response)
    retrieved_evidence = _chunk_evidence_ids(retrieved_evidence_details)
    gold_evidence = item.gold_evidence or []
    evidence_hits = [
        evidence_id
        for evidence_id in retrieved_evidence
        if evidence_id in set(gold_evidence)
    ]
    graph_relation_path_count = sum(
        1
        for evidence in retrieved_evidence_details
        if evidence["relation_path"]
    )

    return AnswerBenchmarkRecord(
        qid=item.qid,
        question=item.question,
        question_type=item.question_type,
        answer=response.answer,
        selected_route=response.selected_route,
        retrieved_evidence=retrieved_evidence,
        retrieved_evidence_details=retrieved_evidence_details,
        evidences=_chunk_scoring_evidences(retrieved_evidence_details),
        gold_evidence=gold_evidence,
        evidence_hits=evidence_hits,
        evidence_recall=_evidence_recall(evidence_hits, gold_evidence),
        graph_evidence_count=sum(
            1
            for evidence in retrieved_evidence_details
            if evidence["is_graph_evidence"]
        ),
        graph_relation_path_count=graph_relation_path_count,
        graph_relation_success=graph_relation_path_count > 0,
        gold_relation_path_count=len(item.gold_relation_path or []),
        gold_answer=item.gold_answer,
        citation_validation=(
            asdict(response.citation_validation)
            if response.citation_validation
            else None
        ),
    )


def summarize_answer_benchmark(
    records: Iterable[AnswerBenchmarkRecord],
    *,
    metadata: dict | None = None,
) -> dict:
    rows = list(records)
    summary = {
        "total": len(rows),
        "average_evidence_recall": _average(
            row.evidence_recall for row in rows
        ),
        "average_graph_relation_success": _average(
            1.0 if row.graph_relation_success else 0.0
            for row in rows
        ),
        "graph_relation_expected": _summarize_graph_relation_expected(rows),
        "by_question_type": _summarize_by_question_type(rows),
        "run": metadata or {},
    }
    return summary


def save_answer_benchmark_records(
    records: Iterable[AnswerBenchmarkRecord],
    path: str | Path,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(asdict(record), ensure_ascii=False)
        for record in records
    ]
    target.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the answer quality and evidence recall benchmark."
    )
    parser.add_argument(
        "--benchmark",
        default="benchmark/benchmark.jsonl",
    )
    parser.add_argument(
        "--records-out",
        default="outputs/answer_benchmark_records.jsonl",
    )
    parser.add_argument(
        "--summary-out",
        default="outputs/answer_benchmark_summary.json",
    )
    parser.add_argument("--chunks-file", default="data/chunks/chunks.jsonl")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--router-version")
    parser.add_argument("--router-model-path")
    args = parser.parse_args(argv)

    from orchestration.stage1 import build_stage1_query_service

    result = run_answer_benchmark(
        build_stage1_query_service(
            chunks_file=args.chunks_file,
            top_k=args.top_k,
            router_version=args.router_version,
            router_model_path=args.router_model_path,
        ),
        load_answer_benchmark(args.benchmark),
        records_out=args.records_out,
        summary_out=args.summary_out,
        metadata={
            "benchmark_file": args.benchmark,
            "chunks_file": args.chunks_file,
            "top_k": args.top_k,
            "router_version": args.router_version,
            "router_model_path": args.router_model_path,
        },
    )
    print(json.dumps(result.summary, ensure_ascii=False, indent=2))
    return 0


def _benchmark_item_from_dict(data: dict) -> AnswerBenchmarkItem:
    return AnswerBenchmarkItem(
        qid=str(data["qid"]),
        question=str(_first_present(data, "question", "query")),
        question_type=str(
            _first_present(
                data,
                "question_type",
                "query_type",
                "question_category",
                "type",
                "category",
                default="unknown",
            )
        ),
        gold_answer=_optional_str(data.get("gold_answer")),
        gold_evidence=_as_str_list(data.get("gold_evidence", [])),
        gold_relation_path=_as_dict_list(
            data.get("gold_relation_path", [])
        ),
        details=data.get("details"),
    )


def _response_evidence_details(response: AnswerResponse) -> list[dict]:
    details = []
    for rank, evidence in enumerate(response.evidences, start=1):
        source_id = str(evidence.source_id) if evidence.source_id else ""
        evidence_id = (
            str(evidence.evidence_id)
            if evidence.evidence_id
            else ""
        )
        retrieval_method = str(evidence.retrieval_method or "")
        details.append(
            {
                "rank": rank,
                "retriever": retrieval_method,
                "retrieval_method": retrieval_method,
                "source_id": source_id,
                "evidence_id": evidence_id,
                "score": evidence.score,
                "source_url": evidence.source_url,
                "entity_ids": evidence.entity_ids,
                "relation_path": evidence.relation_path,
                "is_graph_evidence": _is_graph_evidence(
                    retrieval_method
                ),
            }
        )
    return details


def _chunk_evidence_ids(evidence_details: list[dict]) -> list[str]:
    ids = []
    seen = set()
    for evidence in evidence_details:
        if evidence["is_graph_evidence"]:
            continue
        evidence_id = str(evidence.get("source_id") or "")
        if evidence_id and evidence_id not in seen:
            ids.append(evidence_id)
            seen.add(evidence_id)
    return ids


def _chunk_scoring_evidences(
    evidence_details: list[dict],
) -> list[dict[str, str]]:
    rows = []
    for evidence in evidence_details:
        if evidence["is_graph_evidence"]:
            continue
        source_id = str(evidence.get("source_id") or "")
        evidence_id = str(evidence.get("evidence_id") or "")
        rows.append(
            {
                "source_id": source_id,
                "evidence_id": evidence_id,
                "retriever": str(evidence.get("retriever") or ""),
            }
        )
    return rows


def _is_graph_evidence(retrieval_method: str) -> bool:
    normalized = retrieval_method.lower()
    return (
        normalized == "graph"
        or normalized.startswith("graph_retriever")
    )


def _response_evidence_ids(response: AnswerResponse) -> list[str]:
    ids = []
    for evidence in response.evidences:
        if (
            evidence.source_id
            and not _is_graph_evidence(evidence.retrieval_method)
        ):
            ids.append(str(evidence.source_id))
    return list(dict.fromkeys(ids))


def _summarize_by_question_type(
    records: list[AnswerBenchmarkRecord],
) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[AnswerBenchmarkRecord]] = {}
    for row in records:
        grouped.setdefault(row.question_type, []).append(row)

    return {
        question_type: {
            "total": len(rows),
            "average_evidence_recall": _average(
                row.evidence_recall for row in rows
            ),
            "average_graph_relation_success": _average(
                1.0 if row.graph_relation_success else 0.0
                for row in rows
            ),
        }
        for question_type, rows in grouped.items()
    }


def _summarize_graph_relation_expected(
    records: list[AnswerBenchmarkRecord],
) -> dict[str, float | int]:
    expected = [
        row
        for row in records
        if row.gold_relation_path_count > 0
    ]
    return {
        "total": len(expected),
        "success": sum(
            1
            for row in expected
            if row.graph_relation_success
        ),
        "success_rate": _average(
            1.0 if row.graph_relation_success else 0.0
            for row in expected
        ),
    }


def _evidence_recall(
    evidence_hits: list[str],
    gold_evidence: list[str],
) -> float:
    if not gold_evidence:
        return 0.0
    return round(len(set(evidence_hits)) / len(set(gold_evidence)), 4)


def _average(values: Iterable[float]) -> float:
    rows = list(values)
    if not rows:
        return 0.0
    return round(sum(rows) / len(rows), 4)


def _first_present(data: dict, *names: str, default=None):
    for name in names:
        if name in data:
            return data[name]
    return default


def _optional_str(value) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_str_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value if item is not None]


def _as_dict_list(value) -> list[dict]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _save_json(data: dict, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
