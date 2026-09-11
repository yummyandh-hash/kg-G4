from orchestration.retriever_adapters import (
    AnalysisRouter,
    DRetrieverAdapter,
    RouteDispatchRetriever,
)
from orchestration.service import QueryService
from orchestration.generation import LLMGenerator


def build_stage1_query_service(
    chunks_file: str = "data/chunks/chunks.jsonl",
    top_k: int = 5,
) -> QueryService:
    """Build the real Stage 1 A-D-E query service."""
    from retrieval.graph_retriever import GraphRetriever
    from retrieval.vector_retriever import VectorRetriever

    retriever = RouteDispatchRetriever(
        {
            "vector": DRetrieverAdapter(
                VectorRetriever(chunks_file=chunks_file),
                retrieval_method="vector",
            ),
            "graph": DRetrieverAdapter(
                GraphRetriever(),
                retrieval_method="graph",
            ),
        }
    )

    return QueryService(
        router=AnalysisRouter(),
        retriever=retriever,
        top_k=top_k,
        generator=LLMGenerator(),
    )