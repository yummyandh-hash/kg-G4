import json

from orchestration.models import Evidence, RetrievalContext
from orchestration.retriever_adapters import (
    ChunkLexicalRetriever,
    RouteDispatchRetriever,
)


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


class FakeVectorCandidateRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(self, query, context):
        self.calls.append((query, context.top_k, context.selected_route))
        return [
            Evidence(
                evidence_id="weak",
                content="unrelated evidence",
                retrieval_method="vector",
                score=0.65,
                source_id="weak",
            ),
            Evidence(
                evidence_id="target",
                content="target relation evidence with anchor special term",
                retrieval_method="vector",
                score=0.50,
                source_id="target",
            ),
        ][: context.top_k]


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
    assert {context.selected_route for context in vector.contexts} == {
        "vector",
    }
    assert [evidence.retrieval_method for evidence in evidences] == [
        "graph",
        "vector",
    ]


def test_vector_route_rewrites_query_expands_candidates_and_reranks():
    vector = FakeVectorCandidateRetriever()
    dispatcher = RouteDispatchRetriever(
        {"vector": vector},
        vector_candidate_k=20,
    )

    evidences = dispatcher.retrieve(
        "Use anchor project text: what is the special term?",
        RetrievalContext(
            query_type="fact",
            complexity_score=0.2,
            top_k=1,
            selected_route="vector",
        ),
    )

    assert vector.calls
    assert vector.calls[0][1] == 20
    assert evidences[0].evidence_id == "target"


def test_graph_route_adds_vector_chunk_support_without_changing_route():
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
    vector = FakeVectorCandidateRetriever()
    dispatcher = RouteDispatchRetriever(
        {
            "vector": vector,
            "graph": graph,
        },
        vector_candidate_k=10,
    )

    evidences = dispatcher.retrieve(
        "what is the relation between a and b?",
        RetrievalContext(
            query_type="relation",
            complexity_score=0.35,
            top_k=1,
            selected_route="graph",
        ),
    )

    assert [context.selected_route for context in graph.contexts] == ["graph"]
    assert vector.calls
    assert vector.calls[0][2] == "vector"
    assert [evidence.retrieval_method for evidence in evidences] == [
        "graph",
        "vector",
    ]


def test_graph_route_adds_vector_support_even_for_fact_queries():
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
    vector = FakeVectorCandidateRetriever()
    dispatcher = RouteDispatchRetriever(
        {
            "vector": vector,
            "graph": graph,
        },
        vector_candidate_k=10,
    )

    evidences = dispatcher.retrieve(
        "fact-like question routed to graph",
        RetrievalContext(
            query_type="fact",
            complexity_score=0.1,
            top_k=1,
            selected_route="graph",
        ),
    )

    assert vector.calls
    assert [evidence.retrieval_method for evidence in evidences] == [
        "graph",
        "vector",
    ]


def test_complex_query_expands_neighbor_chunks(tmp_path):
    chunks_file = tmp_path / "chunks.jsonl"
    rows = [
        {
            "chunk_id": "doc_a_content_1",
            "content": "opening context",
            "source_name": "doc a",
            "source_url": "",
            "chunk_type": "detail_content",
        },
        {
            "chunk_id": "doc_a_content_2",
            "content": "matched summary anchor",
            "source_name": "doc a",
            "source_url": "",
            "chunk_type": "detail_content",
        },
        {
            "chunk_id": "doc_a_content_3",
            "content": "neighbor evidence that completes the answer",
            "source_name": "doc a",
            "source_url": "",
            "chunk_type": "detail_content",
        },
    ]
    chunks_file.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )

    vector = FakeSingleRouteRetriever("vector", 0.95)
    vector.retrieve = lambda query, context: [
        Evidence(
            evidence_id="doc_a_content_2",
            content="matched summary anchor",
            retrieval_method="vector",
            score=0.95,
            source_id="doc_a_content_2",
        )
    ]
    dispatcher = RouteDispatchRetriever(
        {
            "vector": vector,
            "lexical": ChunkLexicalRetriever(chunks_file),
        },
        vector_candidate_k=5,
        neighbor_window=1,
    )

    evidences = dispatcher.retrieve(
        "summary question with main content",
        RetrievalContext(
            query_type="constraint",
            complexity_score=0.55,
            top_k=3,
            selected_route="vector",
        ),
    )

    assert {"doc_a_content_1", "doc_a_content_3"} & {
        evidence.source_id for evidence in evidences
    }
    assert any(
        evidence.retrieval_method == "neighbor_expansion"
        for evidence in evidences
    )
