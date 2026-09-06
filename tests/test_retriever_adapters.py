from dataclasses import dataclass

from orchestration.models import RetrievalContext
from orchestration.retriever_adapters import DRetrieverAdapter
from retrieval.base_retriever import Evidence as DBaseEvidence
from retrieval.base_retriever import RetrievalRequest


@dataclass
class DStyleEvidence:
    evidence: str
    score: float
    path: list[str] | None
    retriever: str
    latency: float
    document_id: str
    chunk_id: str
    source_url: str
    source_name: str


class DStyleRetriever:
    def __init__(self):
        self.last_top_k = None

    def retrieve(self, query, context=None, top_k=5):
        self.last_top_k = top_k
        return [
            DStyleEvidence(
                evidence=f"real evidence for {query}",
                score=0.42,
                path=["A --[REL]--> B"],
                retriever="vector",
                latency=0.01,
                document_id="doc-1",
                chunk_id="chunk-1",
                source_url="https://example.test/source",
                source_name="source name",
            )
        ][:top_k]


def test_d_retriever_adapter_maps_contract_and_top_k():
    d_retriever = DStyleRetriever()
    adapter = DRetrieverAdapter(d_retriever, retrieval_method="vector")
    context = RetrievalContext(
        query_type="fact",
        complexity_score=0.15,
        top_k=1,
    )

    evidences = adapter.retrieve("query", context)

    assert d_retriever.last_top_k == 1
    assert len(evidences) == 1
    assert evidences[0].content == "real evidence for query"
    assert evidences[0].retrieval_method == "vector"
    assert evidences[0].score == 0.42
    assert evidences[0].source_id == "doc-1"
    assert evidences[0].source_url == "https://example.test/source"
    assert evidences[0].relation_path == ["A --[REL]--> B"]


class DInnerRetriever:
    def __init__(self):
        self.last_request = None

    def _inner_retrieve(self, request: RetrievalRequest):
        self.last_request = request
        return [
            DBaseEvidence(
                evidence="graph evidence",
                score=0.7,
                path=["project --[LOCATED_IN]--> region"],
                retriever="graph_retriever_one_hop",
                latency=0.01,
                document_id="project-1",
                chunk_id="graph_one_hop",
                source_url="",
                source_name="project name",
                source_category="",
                source_region="region",
                source_org="org",
                retrieved_at="2026-09-06T00:00:00",
                source_batch="neo4j_1hop",
            )
        ]


def test_d_retriever_adapter_passes_retrieval_request_to_inner_retrieve():
    d_retriever = DInnerRetriever()
    adapter = DRetrieverAdapter(d_retriever, retrieval_method="graph")
    context = RetrievalContext(
        query_type="relation",
        complexity_score=0.35,
        top_k=3,
    )

    evidences = adapter.retrieve("relation query", context)

    assert d_retriever.last_request.query == "relation query"
    assert d_retriever.last_request.context == context
    assert d_retriever.last_request.context.query_type == "relation"
    assert d_retriever.last_request.context.top_k == 3
    assert d_retriever.last_request.top_k == 3
    assert evidences[0].retrieval_method == "graph"
    assert evidences[0].relation_path == ["project --[LOCATED_IN]--> region"]
