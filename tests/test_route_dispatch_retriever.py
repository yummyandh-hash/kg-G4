from orchestration.models import Evidence, RetrievalContext
from orchestration.retriever_adapters import RouteDispatchRetriever


class FakeSingleRouteRetriever:
    def __init__(self, route, score, relation_path=None):
        self.route = route
        self.score = score
        self.relation_path = relation_path or []
        self.contexts = []

    def retrieve(self, query, context):
        self.contexts.append(context)
        return [
            Evidence(
                evidence_id=f"{self.route}-1",
                content=f"{self.route} evidence",
                retrieval_method=self.route,
                score=self.score,
                relation_path=self.relation_path,
            )
        ]


def test_route_dispatch_supports_hybrid_from_vector_and_graph():
    graph = FakeSingleRouteRetriever(
        "graph",
        0.7,
        relation_path=[
            {
                "source": "a",
                "relation": "related_to",
                "target": "b",
            }
        ],
    )
    vector = FakeSingleRouteRetriever("vector", 0.9)
    dispatcher = RouteDispatchRetriever(
        {
            "vector": vector,
            "graph": graph,
        }
    )

    evidences = dispatcher.retrieve(
        "query",
        RetrievalContext(
            query_type="relation",
            complexity_score=0.35,
            top_k=2,
            selected_route="hybrid",
        ),
    )

    assert [context.selected_route for context in graph.contexts] == ["graph"]
    assert [context.selected_route for context in vector.contexts] == ["vector"]
    assert [evidence.retrieval_method for evidence in evidences] == [
        "graph",
        "vector",
    ]
