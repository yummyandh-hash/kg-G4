import os
from pathlib import Path

from orchestration.retriever_adapters import (
    AnalysisRouter,
    ChunkLexicalRetriever,
    DRetrieverAdapter,
    RouteDispatchRetriever,
)
from orchestration.service import QueryService


def build_stage1_retriever(
    chunks_file: str = "data/chunks/chunks.jsonl",
    enable_graph_vector_support: bool = True,
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
            "lexical": ChunkLexicalRetriever(chunks_file),
        },
        enable_graph_vector_support=enable_graph_vector_support,
    )


def build_stage1_query_service(
    chunks_file: str = "data/chunks/chunks.jsonl",
    top_k: int = 5,
    router_version: str | None = None,
    router_model_path: str | None = None,
    citation_service=None,
) -> QueryService:
    """Build the real Stage 1 A-D-E query service."""
    retriever = build_stage1_retriever(chunks_file=chunks_file)
    selected_router_version = (
        router_version or os.getenv("KG_G5_ROUTER_VERSION", "v1")
    ).lower()
    if selected_router_version == "v2":
        from orchestration.adaptive_router_v2 import AdaptiveRouterV2

        model_path = _router_v2_model_path(router_model_path)
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
    )


def _router_v2_model_path(router_model_path: str | None) -> str | None:
    model_path = router_model_path or os.getenv("KG_G5_ROUTER_V2_MODEL")
    if model_path:
        return model_path

    default_model = Path("outputs/router_v2.json")
    if default_model.exists():
        return str(default_model)

    return None


def _build_citation_service(chunks_file: str):
    if os.getenv("KG_G5_CITATION_ENABLED") != "1":
        return None

    errors = []
    for module_name in (
        "orchestration.citation_service",
        "citation_service",
    ):
        try:
            module = __import__(module_name, fromlist=["CitationService"])
            return module.CitationService(chunks_file)
        except Exception as exc:
            errors.append(f"{module_name}: {exc}")

    print("[WARN] Citation service unavailable: " + " | ".join(errors))
    return None
