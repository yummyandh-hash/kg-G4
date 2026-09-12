import os

from orchestration.generation import LLMGenerator
from orchestration.retriever_adapters import (
    AnalysisRouter,
    RouteDispatchRetriever,
)
from orchestration.service import QueryService


def build_stage1_retriever(
    chunks_file="data/chunks/chunks.jsonl",
) -> RouteDispatchRetriever:
    from retrieval.graph_retriever import GraphRetriever
    from retrieval.vector_retriever import VectorRetriever

    vector_retriever = VectorRetriever(chunks_file=chunks_file)
    graph_retriever = GraphRetriever()

    return RouteDispatchRetriever(
        retrievers={
            "vector": vector_retriever,
            "graph": graph_retriever,
        }
    )


def build_stage1_query_service(
    chunks_file="data/chunks/chunks.jsonl",
    top_k=5,
    router_version: str | None = None,
    router_model_path: str | None = None,
    citation_service=None,
) -> QueryService:
    retriever = build_stage1_retriever(
        chunks_file=chunks_file
    )

    selected_router_version = (
        router_version
        or os.getenv("KG_G5_ROUTER_VERSION", "v1")
    ).lower()

    if selected_router_version == "v2":
        from orchestration.adaptive_router_v2 import AdaptiveRouterV2

        model_path = (
            router_model_path
            or os.getenv("KG_G5_ROUTER_V2_MODEL")
        )

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
        citation_service=(
            citation_service
            if citation_service is not None
            else _build_citation_service(chunks_file)
        ),
        top_k=top_k,
        generator=LLMGenerator(),
    )


def _build_citation_service(chunks_file: str):
    if os.getenv("KG_G5_CITATION_ENABLED") != "1":
        return None

    try:
        from citation_service import CitationService

        return CitationService(chunks_file)
    except Exception as exc:
        print(f"[WARN] Citation service unavailable: {exc}")
        return None