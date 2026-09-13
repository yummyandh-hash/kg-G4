import re
from typing import Any, Iterable

from orchestration.models import Evidence, RetrievalContext


class AnalysisRouter:
    """Adapter from raw query text to the service Router contract."""

    def __init__(self):
        from orchestration.adaptive_router import AdaptiveRouter
        from orchestration.complexity_scorer import ComplexityScorer
        from orchestration.query_analyzer import QueryAnalyzer

        self.query_analyzer = QueryAnalyzer()
        self.complexity_scorer = ComplexityScorer()
        self.router = AdaptiveRouter()

    def route(self, query: str):
        query_type = self.query_analyzer.analyze(query)
        complexity_score = self.complexity_scorer.score(query)
        return self.router.route(query_type, complexity_score)


class RouteDispatchRetriever:
    """Dispatch retrieval to the retriever selected by the router."""

    def __init__(self, retrievers: dict[str, Any]):
        self.retrievers = retrievers

    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        selected_route = getattr(context, "selected_route", None)
        retriever = self.retrievers.get(selected_route)

        if retriever is None and selected_route == "hybrid":
            return self._retrieve_hybrid(query, context)

        if retriever is None:
            raise ValueError(
                f"No retriever registered for route: {selected_route}"
            )

        return retriever.retrieve(query, context)

    def _retrieve_hybrid(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        evidences: list[Evidence] = []

        for route in ("graph", "vector"):
            retriever = self.retrievers.get(route)
            if retriever is None:
                continue

            route_context = RetrievalContext(
                query_type=context.query_type,
                complexity_score=context.complexity_score,
                top_k=context.top_k,
                selected_route=route,
            )
            evidences.extend(retriever.retrieve(query, route_context))

        if not evidences:
            raise ValueError("No retriever registered for route: hybrid")

        with_path = [
            evidence
            for evidence in evidences
            if evidence.relation_path
        ]
        without_path = [
            evidence
            for evidence in evidences
            if not evidence.relation_path
        ]
        without_path.sort(
            key=lambda evidence: evidence.score or 0.0,
            reverse=True,
        )
        return (with_path + without_path)[: context.top_k]


class DRetrieverAdapter:
    """Adapt D retriever output into A's Evidence contract."""

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
        if hasattr(self.retriever, "retrieve"):
            return self.retriever.retrieve(
                query,
                context=context,
                top_k=context.top_k,
            )

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
        retriever_name = _first_present(raw, "retriever", default=None)
        evidence_id = (
            chunk_id
            or source_id
            or f"{self.retrieval_method}-{index:03d}"
        )
        relation_path = _relation_path(raw)

        return Evidence(
            evidence_id=str(evidence_id),
            content=str(content),
            retrieval_method=str(retriever_name or self.retrieval_method),
            score=_as_float(score),
            source_id=str(source_id) if source_id else None,
            source_url=source_url,
            entity_ids=_entity_ids(raw, relation_path),
            relation_path=relation_path,
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


def _relation_path(raw: Any) -> list[dict[str, str]]:
    path = _first_present(raw, "relation_path", default=None)
    if path:
        return _normalize_relation_path(path)

    d_path = _first_present(raw, "path", default=None)
    if d_path is None:
        return []

    return _normalize_relation_path(d_path)


def _normalize_relation_path(value: Any) -> list[dict[str, str]]:
    if isinstance(value, dict):
        relation = _relation_from_dict(value)
        return [relation] if relation else []

    if isinstance(value, str):
        return _parse_path_text(value)

    relations: list[dict[str, str]] = []
    flat_items: list[str] = []

    for item in value:
        if item is None:
            continue

        if isinstance(item, dict):
            relation = _relation_from_dict(item)
            if relation:
                relations.append(relation)
            continue

        if isinstance(item, str):
            parsed = _parse_path_text(item)
            if parsed:
                relations.extend(parsed)
            else:
                flat_items.append(item)
            continue

        flat_items.append(str(item))

    if relations:
        return relations

    return _flat_path_to_relations(flat_items)


def _relation_from_dict(value: dict[str, Any]) -> dict[str, str] | None:
    source = value.get("source")
    relation = value.get("relation")
    target = value.get("target")

    if not source or not relation or not target:
        return None

    return {
        "source": str(source),
        "relation": str(relation),
        "target": str(target),
    }


def _parse_path_text(path_text: str) -> list[dict[str, str]]:
    parts = re.split(r"\s*--\[(.*?)\]-->\s*", path_text.strip())
    parts = [part.strip() for part in parts if part.strip()]
    return _flat_path_to_relations(parts)


def _flat_path_to_relations(parts: list[str]) -> list[dict[str, str]]:
    if len(parts) < 3:
        return []

    relations = []
    for index in range(0, len(parts) - 2, 2):
        source = parts[index]
        relation = parts[index + 1]
        target = parts[index + 2]
        relations.append(
            {
                "source": source,
                "relation": relation,
                "target": target,
            }
        )

    return relations


def _entity_ids(raw: Any, relation_path: list[dict[str, str]]) -> list[str]:
    entity_ids = _first_present(raw, "entity_ids", default=None)
    if entity_ids:
        return [str(item) for item in entity_ids if item is not None]

    ids: list[str] = []

    for relation in relation_path:
        ids.extend(
            item
            for item in (
                relation.get("source"),
                relation.get("target"),
            )
            if item
        )

    source_name = _first_present(raw, "source_name", default=None)
    document_id = _first_present(raw, "document_id", default=None)
    ids.extend(item for item in (document_id, source_name) if item)

    return list(dict.fromkeys(str(item) for item in ids if item))
