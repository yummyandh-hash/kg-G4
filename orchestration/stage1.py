from __future__ import annotations

from orchestration.answer_generator import (
    EvidenceAnswerGenerator,
    OpenAICompatibleAnswerGenerator,
)
from orchestration.pipeline import OrchestrationPipeline
from orchestration.retriever_adapters import DRetrieverAdapter


def build_stage1_pipeline(
    chunks_file: str = "data/chunks/chunks.jsonl",
    top_k: int = 5,
    enable_llm: bool = True,
) -> OrchestrationPipeline:
    """Build Stage 1 with D real retrievers behind A adapters."""
    from retrieval.graph_retriever import GraphRetriever
    from retrieval.vector_retriever import VectorRetriever

    answer_generator = None
    if enable_llm:
        answer_generator = OpenAICompatibleAnswerGenerator.from_env()
    if answer_generator is None:
        answer_generator = EvidenceAnswerGenerator()

    return OrchestrationPipeline(
        retrievers={
            "vector": DRetrieverAdapter(
                VectorRetriever(chunks_file=chunks_file),
                retrieval_method="vector",
            ),
            "graph": DRetrieverAdapter(
                GraphRetriever(),
                retrieval_method="graph",
            ),
        },
        top_k=top_k,
        answer_generator=answer_generator,
    )
