import os

from orchestration.retriever_adapters import (
    AnalysisRouter,
    DRetrieverAdapter,
    RouteDispatchRetriever,
)
from orchestration.service import QueryService


def build_stage1_retriever(
    chunks_file: str = "data/chunks/chunks.jsonl",
) -> RouteDispatchRetriever:
    """Build the real D retriever dispatch used by Stage 1 and Stage 2."""
    from retrieval.graph_retriever import GraphRetriever
    from retrieval.vector_retriever import VectorRetriever

    return RouteDispatchRetriever(
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


def build_stage1_query_service(
    chunks_file: str = "data/chunks/chunks.jsonl",
    top_k: int = 5,
    router_version: str | None = None,
    router_model_path: str | None = None,
) -> QueryService:
    """Build the real Stage 1 A-D-E query service."""
    retriever = build_stage1_retriever(chunks_file=chunks_file)
    selected_router_version = (
        router_version or os.getenv("KG_G5_ROUTER_VERSION", "v1")
    ).lower()
    if selected_router_version == "v2":
        from orchestration.adaptive_router_v2 import AdaptiveRouterV2

        model_path = router_model_path or os.getenv("KG_G5_ROUTER_V2_MODEL")
        router = (
            AdaptiveRouterV2.load(model_path)
            if model_path
            else AdaptiveRouterV2()
        )
    else:
        router = AnalysisRouter()

    return QueryService(
        router=router,
        retriever=retriever,
        top_k=top_k,
    )
