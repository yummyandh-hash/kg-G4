from orchestration.models import Evidence
from orchestration.routing_benchmark import (
    DualRouteBenchmark,
    RoutingBenchmarkQuery,
    choose_best_route,
    training_examples_from_records,
)


class FakeDualRouteRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(self, query, context):
        self.calls.append((query, context.selected_route, context.query_type))
        if context.selected_route == "graph":
            return [
                Evidence(
                    evidence_id="graph-1",
                    content="graph evidence",
                    retrieval_method="graph",
                    score=0.8,
                    entity_ids=["a", "b"],
                    relation_path=["a", "related_to", "b"],
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


def test_dual_route_benchmark_forces_vector_and_graph_routes():
    retriever = FakeDualRouteRetriever()
    benchmark = DualRouteBenchmark(retriever)

    record = benchmark.run_one(
        RoutingBenchmarkQuery(
            query="relation query",
            query_type="relation",
            complexity_score=0.35,
        )
    )

    assert [call[1] for call in retriever.calls] == ["vector", "graph"]
    assert [call[2] for call in retriever.calls] == ["relation", "relation"]
    assert record.best_route == "graph"
    assert record.label_source == "heuristic"


def test_expected_route_overrides_heuristic_label():
    retriever = FakeDualRouteRetriever()
    benchmark = DualRouteBenchmark(retriever)

    record = benchmark.run_one(
        RoutingBenchmarkQuery(
            query="manual label query",
            query_type="fact",
            complexity_score=0.20,
            expected_route="vector",
        )
    )

    assert record.best_route == "vector"
    assert record.label_source == "expected"


def test_choose_best_route_prefers_higher_vector_score_without_graph_path():
    best_route = choose_best_route(
        [
            Evidence(
                evidence_id="vector-1",
                content="vector evidence",
                retrieval_method="vector",
                score=0.9,
            )
        ],
        [
            Evidence(
                evidence_id="graph-1",
                content="graph evidence",
                retrieval_method="graph",
                score=0.6,
            )
        ],
    )

    assert best_route == "vector"


def test_training_examples_from_benchmark_records():
    retriever = FakeDualRouteRetriever()
    benchmark = DualRouteBenchmark(retriever)
    records = benchmark.run(
        [
            RoutingBenchmarkQuery(
                query="manual label query",
                query_type="fact",
                complexity_score=0.20,
                expected_route="vector",
            )
        ]
    )

    examples = training_examples_from_records(records)

    assert len(examples) == 1
    assert examples[0].query == "manual label query"
    assert examples[0].best_route == "vector"
    assert examples[0].query_type == "fact"
    assert examples[0].complexity_score == 0.20
