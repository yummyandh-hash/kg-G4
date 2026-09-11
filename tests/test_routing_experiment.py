from orchestration.models import Evidence
from orchestration.routing_experiment import (
    load_benchmark_queries,
    run_routing_experiment,
)


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
        model_out=model_out,
        summary_out=summary_out,
    )

    assert result.summary["total"] == 2
    assert records_out.exists()
    assert model_out.exists()
    assert summary_out.exists()
    assert "by_query_type" in summary_out.read_text(encoding="utf-8")
    assert '"version": "adaptive-router-v2"' in model_out.read_text(
        encoding="utf-8"
    )


def load_benchmark_queries_from_text(lines, tmp_path):
    path = tmp_path / "queries.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")
    return load_benchmark_queries(path)
