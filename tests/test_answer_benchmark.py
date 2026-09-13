from orchestration.answer_benchmark import (
    load_answer_benchmark,
    run_answer_benchmark,
)
from orchestration.models import AnswerResponse, Evidence


class FakeQueryService:
    def query(self, question: str):
        return AnswerResponse(
            answer=f"answer: {question}",
            query_type="fact",
            complexity_score=0.2,
            selected_route="vector",
            route_reason="test",
            evidences=[
                Evidence(
                    evidence_id="ev-1",
                    content="evidence",
                    retrieval_method="vector",
                    source_id="chunk-1",
                ),
                Evidence(
                    evidence_id="ev-2",
                    content="evidence",
                    retrieval_method="vector",
                    source_id="chunk-x",
                ),
            ],
        )


class GraphOnlyQueryService:
    def query(self, question: str):
        return AnswerResponse(
            answer=f"answer: {question}",
            query_type="relation",
            complexity_score=0.7,
            selected_route="graph",
            route_reason="test",
            evidences=[
                Evidence(
                    evidence_id="graph_one_hop",
                    content="graph triple",
                    retrieval_method="graph_retriever_one_hop",
                    source_id="",
                    entity_ids=["entity-a", "entity-b"],
                    relation_path=[
                        {
                            "source": "entity-a",
                            "relation": "LOCATED_IN",
                            "target": "entity-b",
                        }
                    ],
                ),
                Evidence(
                    evidence_id="chunk-1",
                    content="vector-like evidence",
                    retrieval_method="vector",
                    source_id="chunk-1",
                ),
            ],
        )


def test_load_answer_benchmark_accepts_task3_schema(tmp_path):
    path = tmp_path / "benchmark.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"qid": "q1", "question": "单跳问题", "type": "single_hop", '
                '"gold_answer": "参考答案", "gold_evidence": ["chunk-1"], '
                '"details": {"source": "demo"}}',
                '{"qid": "q2", "query": "多跳问题", '
                '"query_type": "multi_hop", "gold_evidence": "chunk-2"}',
                '{"qid": "q3", "question": "归纳问题", '
                '"question_category": "summary", '
                '"gold_evidence": ["chunk-3"]}',
            ]
        ),
        encoding="utf-8",
    )

    items = load_answer_benchmark(path)

    assert len(items) == 3
    assert items[0].qid == "q1"
    assert items[0].question == "单跳问题"
    assert items[0].question_type == "single_hop"
    assert items[0].gold_answer == "参考答案"
    assert items[0].gold_evidence == ["chunk-1"]
    assert items[1].question == "多跳问题"
    assert items[1].question_type == "multi_hop"
    assert items[1].gold_evidence == ["chunk-2"]
    assert items[2].question_type == "summary"


def test_run_answer_benchmark_reports_evidence_recall(tmp_path):
    benchmark_path = tmp_path / "benchmark.jsonl"
    records_out = tmp_path / "records.jsonl"
    summary_out = tmp_path / "summary.json"
    benchmark_path.write_text(
        "\n".join(
            [
                '{"qid": "q1", "question": "单跳问题", "type": "single_hop", '
                '"gold_answer": "参考答案", "gold_evidence": ["chunk-1"]}',
                '{"qid": "q2", "question": "归纳问题", "type": "summary", '
                '"gold_answer": "参考答案", "gold_evidence": ["chunk-2"]}',
            ]
        ),
        encoding="utf-8",
    )

    result = run_answer_benchmark(
        FakeQueryService(),
        load_answer_benchmark(benchmark_path),
        records_out=records_out,
        summary_out=summary_out,
        metadata={"benchmark_file": str(benchmark_path)},
    )

    assert result.summary["total"] == 2
    assert result.summary["average_evidence_recall"] == 0.5
    assert result.summary["by_question_type"]["single_hop"][
        "average_evidence_recall"
    ] == 1.0
    assert result.summary["by_question_type"]["summary"][
        "average_evidence_recall"
    ] == 0.0
    assert records_out.exists()
    assert summary_out.exists()
    assert '"gold_answer": "参考答案"' in records_out.read_text(
        encoding="utf-8"
    )


def test_answer_benchmark_filters_graph_evidence_from_chunk_recall(tmp_path):
    benchmark_path = tmp_path / "benchmark.jsonl"
    benchmark_path.write_text(
        '{"qid": "q1", "question": "relation question", '
        '"question_category": "multi_hop", '
        '"gold_evidence": ["chunk-1"], '
        '"gold_relation_path": [{"source": "a", "relation": "r", '
        '"target": "b"}]}',
        encoding="utf-8",
    )

    result = run_answer_benchmark(
        GraphOnlyQueryService(),
        load_answer_benchmark(benchmark_path),
    )

    record = result.records[0]
    assert record.retrieved_evidence == ["chunk-1"]
    assert record.evidences == [
        {
            "source_id": "chunk-1",
            "evidence_id": "chunk-1",
            "retriever": "vector",
        }
    ]
    assert record.evidence_recall == 1.0
    assert record.graph_evidence_count == 1
    assert record.graph_relation_success is True
    assert record.retrieved_evidence_details[0]["source_id"] == ""
    assert result.summary["graph_relation_expected"] == {
        "total": 1,
        "success": 1,
        "success_rate": 1.0,
    }
