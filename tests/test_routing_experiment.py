from orchestration.models import Evidence
from orchestration.routing_experiment import (
    load_benchmark_queries,
    main,
    run_routing_experiment,
    run_routing_experiment_from_records,
)
from orchestration.routing_benchmark import load_benchmark_records


class FakeExperimentRetriever:
    def retrieve(self, query, context):
        if context.selected_route == "graph":
            return [
                Evidence(
                    evidence_id="graph-1",
                    content="graph evidence",
                    retrieval_method="graph",
                    score=0.8,
                    relation_path=[
                        {
                            "source": "a",
                            "relation": "related_to",
                            "target": "b",
                        }
                    ],
                )
            ]

        return [
            Evidence(
                evidence_id="vector-1",
                content="vector evidence",
                retrieval_method="vector",
                score=0.7,
            )
        ]


def test_load_benchmark_queries_accepts_jsonl_and_plain_lines(tmp_path):
    path = tmp_path / "queries.jsonl"
    path.write_text(
        "\n".join(
            [
                "# comment",
                '{"query": "q1", "expected_route": "vector"}',
                "q2",
            ]
        ),
        encoding="utf-8",
    )

    queries = load_benchmark_queries(path)

    assert len(queries) == 2
    assert queries[0].query == "q1"
    assert queries[0].expected_route == "vector"
    assert queries[1].query == "q2"


def test_run_routing_experiment_saves_records_and_model(tmp_path):
    records_out = tmp_path / "records.jsonl"
    comparisons_out = tmp_path / "comparisons.jsonl"
    model_out = tmp_path / "router_v2.json"
    summary_out = tmp_path / "reports" / "summary.json"

    result = run_routing_experiment(
        FakeExperimentRetriever(),
        load_benchmark_queries_from_text(
            [
                '{"query": "simple fact", "query_type": "fact", '
                '"complexity_score": 0.15, "expected_route": "vector"}',
                '{"query": "relation query", "query_type": "relation", '
                '"complexity_score": 0.35, "expected_route": "graph"}',
            ],
            tmp_path,
        ),
        records_out=records_out,
        comparisons_out=comparisons_out,
        model_out=model_out,
        summary_out=summary_out,
    )

    assert result.summary["total"] == 2
    assert result.summary["run"]["mode"] == "live_retriever"
    assert result.summary["run"]["queries_total"] == 2
    assert result.summary["run"]["top_k"] == 5
    assert records_out.exists()
    assert comparisons_out.exists()
    assert model_out.exists()
    assert summary_out.exists()
    assert "by_query_type" in summary_out.read_text(encoding="utf-8")
    assert '"version": "adaptive-router-v2"' in model_out.read_text(
        encoding="utf-8"
    )


def test_run_routing_experiment_from_saved_records(tmp_path):
    records_out = tmp_path / "records.jsonl"
    model_out = tmp_path / "router_v2.json"
    comparisons_out = tmp_path / "comparisons.jsonl"
    summary_out = tmp_path / "summary.json"
    initial = run_routing_experiment(
        FakeExperimentRetriever(),
        load_benchmark_queries_from_text(
            [
                '{"query": "simple fact", "query_type": "fact", '
                '"complexity_score": 0.15, "expected_route": "vector"}',
                '{"query": "relation query", "query_type": "relation", '
                '"complexity_score": 0.35, "expected_route": "graph"}',
            ],
            tmp_path,
        ),
        records_out=records_out,
    )

    result = run_routing_experiment_from_records(
        load_benchmark_records(records_out),
        comparisons_out=comparisons_out,
        model_out=model_out,
        summary_out=summary_out,
    )

    assert result.summary["total"] == initial.summary["total"]
    assert result.summary["run"]["mode"] == "saved_records"
    assert result.summary["run"]["records_total"] == 2
    assert comparisons_out.exists()
    assert model_out.exists()
    assert summary_out.exists()


def test_main_can_reuse_records_without_retriever(tmp_path):
    records_out = tmp_path / "records.jsonl"
    model_out = tmp_path / "router_v2.json"
    comparisons_out = tmp_path / "comparisons.jsonl"
    summary_out = tmp_path / "summary.json"
    run_routing_experiment(
        FakeExperimentRetriever(),
        load_benchmark_queries_from_text(
            [
                '{"query": "simple fact", "query_type": "fact", '
                '"complexity_score": 0.15, "expected_route": "vector"}',
                '{"query": "relation query", "query_type": "relation", '
                '"complexity_score": 0.35, "expected_route": "graph"}',
            ],
            tmp_path,
        ),
        records_out=records_out,
    )

    exit_code = main(
        [
            "--records-in",
            str(records_out),
            "--model-out",
            str(model_out),
            "--comparisons-out",
            str(comparisons_out),
            "--summary-out",
            str(summary_out),
        ]
    )

    assert exit_code == 0
    assert comparisons_out.exists()
    assert model_out.exists()
    assert summary_out.exists()
    assert '"records_in"' in summary_out.read_text(encoding="utf-8")


def load_benchmark_queries_from_text(lines, tmp_path):
    path = tmp_path / "queries.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")
    return load_benchmark_queries(path)
