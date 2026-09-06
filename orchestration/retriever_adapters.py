from __future__ import annotations

from typing import Any, Iterable

from orchestration.models import Evidence, RetrievalContext


class DRetrieverAdapter:
    """Adapt D retriever output into A's Retriever contract."""

    def __init__(self, retriever: Any, retrieval_method: str):
        self.retriever = retriever
        self.retrieval_method = retrieval_method

    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        raw_evidences = self._call_retriever(query, context)
        return [
            self._to_a_evidence(raw, index)
            for index, raw in enumerate(raw_evidences, start=1)
        ]

    def _call_retriever(
        self,
        query: str,
        context: RetrievalContext,
    ) -> Iterable[Any]:
        # 优先使用 D Retriever 的公开接口。
        if hasattr(self.retriever, "retrieve"):
            return self.retriever.retrieve(
                query,
                context=context,
                top_k=context.top_k,
            )

        # 兼容只有 _inner_retrieve() 的测试替身。
        if hasattr(self.retriever, "_inner_retrieve"):
            from retrieval.base_retriever import RetrievalRequest

            request = RetrievalRequest(
                query=query,
                top_k=context.top_k,
                context=context,
            )
            return self.retriever._inner_retrieve(request)

        raise AttributeError(
            "Retriever must provide retrieve() or _inner_retrieve()."
        )
        
    def _to_a_evidence(self, raw: Any, index: int) -> Evidence:
        content = _first_present(raw, "evidence", "content", default="")
        score = _first_present(raw, "score", default=None)
        source_url = _first_present(raw, "source_url", default=None) or None
        source_id = (
            _first_present(raw, "document_id", "source_id", default=None)
            or _first_present(raw, "chunk_id", default=None)
            or _first_present(raw, "source_name", default=None)
        )
        chunk_id = _first_present(raw, "chunk_id", default=None)
        evidence_id = chunk_id or source_id or f"{self.retrieval_method}-{index:03d}"

        return Evidence(
            evidence_id=str(evidence_id),
            content=str(content),
            retrieval_method=self.retrieval_method,
            score=_as_float(score),
            source_id=str(source_id) if source_id else None,
            source_url=source_url,
            entity_ids=_entity_ids(raw),
            relation_path=_relation_path(raw),
        )


def _first_present(raw: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(raw, dict) and name in raw:
            return raw[name]
        if hasattr(raw, name):
            return getattr(raw, name)
    return default


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _relation_path(raw: Any) -> list[str]:
    path = _first_present(raw, "path", "relation_path", default=None)
    if path is None:
        return []
    if isinstance(path, str):
        return [path]
    return [str(item) for item in path if item is not None]


def _entity_ids(raw: Any) -> list[str]:
    entity_ids = _first_present(raw, "entity_ids", default=None)
    if entity_ids:
        return [str(item) for item in entity_ids]

    source_name = _first_present(raw, "source_name", default=None)
    document_id = _first_present(raw, "document_id", default=None)
    return [str(item) for item in (document_id, source_name) if item]
