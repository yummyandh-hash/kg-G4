from dataclasses import asdict, is_dataclass
from time import perf_counter
from typing import Any, List, Optional, Protocol
import re

from orchestration.context import build_context
from orchestration.generation import LLMGenerator
from orchestration.models import (
    AnswerResponse,
    CitationValidation,
    Evidence,
    GraphEdge,
    GraphNode,
    RetrievalContext,
    RouteDecision,
)


class RouterProtocol(Protocol):
    def route(self, query: str) -> RouteDecision:
        ...


class RetrieverProtocol(Protocol):
    def retrieve(
        self,
        query: str,
        context: Optional[RetrievalContext] = None,
    ) -> List[Evidence]:
        ...


class CitationVerifier(Protocol):
    """Optional citation verification service provided by Task 2."""

    def verify_claim(
        self,
        claim: str,
        chunk_ids: List[str],
    ):
        ...


class MockRouter:
    """
    Stage 1 默认 Router。

    当前阶段固定使用 hybrid + relation，
    用于保证 GraphRetriever 能进入 relation 分支。
    """

    def route(self, query: str) -> RouteDecision:
        return RouteDecision(
            query_type="relation",
            complexity_score=0.3,
            selected_route="hybrid",
            reason="Stage 1：采用 Graph + Vector 混合检索",
        )


def normalize_evidence(evidence):
    """
    将 Retriever 返回的 Evidence 统一转换成
    orchestration.models.Evidence。

    兼容 D 当前 GraphRetriever 返回的字段：
    evidence
    score
    path
    retriever
    document_id
    chunk_id
    source_url
    source_name
    entity_ids
    relation_path
    """

    if hasattr(evidence, "content"):
        return evidence

    entity_ids = getattr(
        evidence,
        "entity_ids",
        None,
    ) or []

    relation_path = getattr(
        evidence,
        "relation_path",
        None,
    ) or []

    return Evidence(
        evidence_id=getattr(
            evidence,
            "chunk_id",
            "d-evidence",
        ),
        content=getattr(
            evidence,
            "evidence",
            "",
        ),
        retrieval_method=getattr(
            evidence,
            "retriever",
            "unknown",
        ),
        score=getattr(
            evidence,
            "score",
            0.0,
        ),
        source_id=getattr(
            evidence,
            "source_name",
            "",
        ),
        source_url=getattr(
            evidence,
            "source_url",
            "",
        ),
        entity_ids=list(
            dict.fromkeys(entity_ids)
        ),
        relation_path=relation_path,
    )


def _extract_path_names(path_text: str) -> List[str]:
    """从 one-hop path 文本中提取节点名称。"""

    if not path_text:
        return []

    pattern = r"(.+?)\s*--\[(.+?)\]-->\s*(.+)"

    match = re.match(
        pattern,
        path_text,
    )

    if not match:
        return []

    source = match.group(1).strip()
    target = match.group(3).strip()

    return [
        source,
        target,
    ]


def _extract_two_hop_path_names(
    path_text: str,
) -> List[str]:
    """从 two-hop path 文本中提取三个节点名称。"""

    if not path_text:
        return []

    pattern = (
        r"(.+?)\s*--\[(.+?)\]-->\s*"
        r"(.+?)\s*--\[(.+?)\]-->\s*(.+)"
    )

    match = re.match(
        pattern,
        path_text,
    )

    if not match:
        return []

    source = match.group(1).strip()
    middle = match.group(3).strip()
    target = match.group(5).strip()

    return [
        source,
        middle,
        target,
    ]


def _build_node_name_map(
    evidences: List[Evidence],
) -> dict:
    """
    构建 entity_id -> 中文节点名称映射。
    """

    node_name_map = {}

    for evidence in evidences:

        entity_ids = getattr(
            evidence,
            "entity_ids",
            None,
        ) or []

        source_name = getattr(
            evidence,
            "source_id",
            None,
        )

        if (
            source_name
            and len(entity_ids) == 1
            and entity_ids[0]
        ):
            node_name_map[
                entity_ids[0]
            ] = source_name

        retrieval_method = getattr(
            evidence,
            "retrieval_method",
            "",
        )

        if retrieval_method == "graph_retriever_one_hop":

            path_texts = []

            raw_path = getattr(
                evidence,
                "path",
                None,
            )

            if raw_path:
                path_texts.extend(raw_path)

            content = getattr(
                evidence,
                "content",
                "",
            )

            if content:
                path_texts.append(content)

            for path_text in path_texts:

                names = _extract_path_names(
                    path_text
                )

                if (
                    len(names) == 2
                    and len(entity_ids) >= 2
                ):
                    node_name_map[
                        entity_ids[0]
                    ] = names[0]

                    node_name_map[
                        entity_ids[1]
                    ] = names[1]

        elif retrieval_method == "graph_retriever_two_hop":

            path_texts = []

            raw_path = getattr(
                evidence,
                "path",
                None,
            )

            if raw_path:
                path_texts.extend(raw_path)

            content = getattr(
                evidence,
                "content",
                "",
            )

            if content:
                path_texts.append(content)

            for path_text in path_texts:

                names = _extract_two_hop_path_names(
                    path_text
                )

                if (
                    len(names) == 3
                    and len(entity_ids) >= 3
                ):
                    node_name_map[
                        entity_ids[0]
                    ] = names[0]

                    node_name_map[
                        entity_ids[1]
                    ] = names[1]

                    node_name_map[
                        entity_ids[2]
                    ] = names[2]

    return node_name_map


def _path_entities(path) -> List[str]:
    """从 relation_path 中提取实体节点。"""

    if not path:
        return []

    entities = []

    if all(isinstance(item, str) for item in path):

        if len(path) >= 3 and len(path) % 2 == 1:
            return path[::2]

        import ast

        for item in path:
            try:
                parsed = ast.literal_eval(item)
            except (ValueError, SyntaxError):
                continue

            if not isinstance(parsed, dict):
                continue

            source = parsed.get("source")
            target = parsed.get("target")

            if source:
                entities.append(str(source))

            if target:
                entities.append(str(target))

        return list(dict.fromkeys(entities))

    for item in path:
        if not isinstance(item, dict):
            continue

        source = item.get("source")
        target = item.get("target")

        if source:
            entities.append(str(source))

        if target:
            entities.append(str(target))

    return list(dict.fromkeys(entities))


def _path_edges(path) -> List[tuple[str, str, str]]:
    """将 relation_path 解析成 (source, relation, target)。"""

    if not path:
        return []

    edges = []

    if all(isinstance(item, str) for item in path):

        if len(path) >= 3 and len(path) % 2 == 1:
            for i in range(0, len(path) - 2, 2):
                source = path[i]
                relation = path[i + 1]
                target = path[i + 2]

                if source and relation and target:
                    edges.append(
                        (source, relation, target)
                    )

            if edges:
                return edges

        import ast

        for item in path:
            try:
                parsed = ast.literal_eval(item)
            except (ValueError, SyntaxError):
                continue

            if not isinstance(parsed, dict):
                continue

            source = parsed.get("source")
            relation = parsed.get("relation")
            target = parsed.get("target")

            if source and relation and target:
                edges.append(
                    (
                        str(source),
                        str(relation),
                        str(target),
                    )
                )

        return edges

    for item in path:
        if not isinstance(item, dict):
            continue

        source = item.get("source")
        relation = item.get("relation")
        target = item.get("target")

        if source and relation and target:
            edges.append(
                (
                    str(source),
                    str(relation),
                    str(target),
                )
            )

    return edges


def _citation_chunk_ids(
    evidences: List[Evidence],
) -> List[str]:
    ids = [
        evidence.source_id or evidence.evidence_id
        for evidence in evidences
        if evidence.source_id or evidence.evidence_id
    ]

    return list(
        dict.fromkeys(
            str(item)
            for item in ids
            if item
        )
    )


def _to_citation_validation(
    result: Any,
) -> CitationValidation:

    if isinstance(result, CitationValidation):
        return result

    if is_dataclass(result):
        data = asdict(result)
    elif isinstance(result, dict):
        data = result
    else:
        data = {
            "label": getattr(result, "label"),
            "confidence": getattr(result, "confidence"),
            "reason": getattr(result, "reason"),
            "evidences": getattr(
                result,
                "evidences",
                [],
            ),
        }

    return CitationValidation(
        label=str(data["label"]),
        confidence=float(data["confidence"]),
        reason=str(data.get("reason", "")),
        evidences=list(
            data.get("evidences", [])
        ),
    )


class QueryService:

    def __init__(
        self,
        router: RouterProtocol,
        retriever: RetrieverProtocol,
        top_k: int = 5,
        generator: Optional[LLMGenerator] = None,
        citation_service: Optional[CitationVerifier] = None,
    ):
        self.router = router
        self.retriever = retriever
        self.top_k = top_k
        self.generator = generator
        self.citation_service = citation_service

    def query(
        self,
        question: str,
    ) -> AnswerResponse:

        start_time = perf_counter()

        # ==========================================================
        # 1. Query Routing
        # ==========================================================

        route_start = perf_counter()

        decision = self.router.route(
            question
        )

        route_time = (
            perf_counter() - route_start
        )

        print(
            "========== ROUTE DECISION =========="
        )
        print(
            "QUERY:",
            question,
        )
        print(
            "QUERY TYPE:",
            decision.query_type,
        )
        print(
            "COMPLEXITY:",
            decision.complexity_score,
        )
        print(
            "ROUTE:",
            decision.selected_route,
        )
        print(
            "REASON:",
            decision.reason,
        )
        print(
            "===================================="
        )

        # ==========================================================
        # 2. RetrievalContext
        # ==========================================================

        context = RetrievalContext(
            query_type=decision.query_type,
            complexity_score=decision.complexity_score,
            top_k=self.top_k,
            selected_route=decision.selected_route,
        )

        # ==========================================================
        # 3. Retrieval
        # ==========================================================

        retrieval_start = perf_counter()

        evidences = self.retriever.retrieve(
            question,
            context,
        )

        retrieval_time = (
            perf_counter() - retrieval_start
        )

        # ==========================================================
        # 4. Normalize Evidence
        # ==========================================================

        evidences = [
            normalize_evidence(evidence)
            for evidence in evidences
        ]

        # ==========================================================
        # 5. Context Engineering
        # ==========================================================

        llm_context = build_context(
            query=question,
            evidences=evidences,
            max_evidence=self.top_k,
        )

        print(
            "========== LLM CONTEXT =========="
        )
        print(llm_context)
        print(
            "================================="
        )

        # ==========================================================
        # 6. LLM Generation
        # ==========================================================

        answer_start = perf_counter()

        if self.generator is not None:
            answer = self.generator.generate(
                question=question,
                context=llm_context,
            )
        else:
            answer = ""

        answer_time = (
            perf_counter() - answer_start
        )

        # ==========================================================
        # 7. Citation Verification
        # ==========================================================

        citation_start = perf_counter()

        citation_validation = (
            self._verify_citation(
                answer,
                evidences,
            )
        )

        citation_time = (
            perf_counter() - citation_start
        )

        # ==========================================================
        # 8. Relation Paths
        # ==========================================================

        paths = [
            evidence.relation_path
            for evidence in evidences
            if evidence.relation_path
        ]

        # ==========================================================
        # 9. Sources
        # ==========================================================

        sources = list(
            dict.fromkeys(
                evidence.source_id
                for evidence in evidences
                if evidence.source_id
            )
        )

        # ==========================================================
        # 10. Entity Name Mapping
        # ==========================================================

        node_name_map = _build_node_name_map(
            evidences
        )

        # ==========================================================
        # 11. Graph Nodes
        # ==========================================================

        node_map = {}

        for evidence in evidences:

            entity_ids = getattr(
                evidence,
                "entity_ids",
                None,
            ) or []

            for entity_id in entity_ids:

                if not entity_id:
                    continue

                if entity_id in node_map:
                    continue

                label = node_name_map.get(
                    entity_id
                )

                if not label:
                    label = entity_id.split(":")[-1]

                node_map[entity_id] = GraphNode(
                    node_id=entity_id,
                    label=label,
                )

            for entity_id in _path_entities(
                evidence.relation_path
            ):

                if not entity_id:
                    continue

                if entity_id in node_map:
                    continue

                label = node_name_map.get(
                    entity_id
                )

                if not label:
                    label = entity_id.split(":")[-1]

                node_map[entity_id] = GraphNode(
                    node_id=entity_id,
                    label=label,
                )

        graph_nodes = list(
            node_map.values()
        )

        # ==========================================================
        # 12. Graph Edges
        # ==========================================================

        edge_map = {}

        for evidence in evidences:

            edges = _path_edges(
                evidence.relation_path
            )

            for source, relation, target in edges:

                edge_key = (
                    source,
                    relation,
                    target,
                )

                if edge_key not in edge_map:
                    edge_map[edge_key] = GraphEdge(
                        source=source,
                        target=target,
                        relation=relation,
                    )

        graph_edges = list(
            edge_map.values()
        )

        # ==========================================================
        # 13. Timing
        # ==========================================================

        total_time = (
            perf_counter() - start_time
        )

        # ==========================================================
        # 14. AnswerResponse
        # ==========================================================

        return AnswerResponse(
            answer=answer,
            query_type=decision.query_type,
            complexity_score=decision.complexity_score,
            selected_route=decision.selected_route,
            route_reason=decision.reason,
            route_confidence=decision.confidence,
            citation_validation=citation_validation,
            evidences=evidences,
            paths=paths,
            sources=sources,
            timing={
                "routing": route_time,
                "retrieval": retrieval_time,
                "answer_generation": answer_time,
                "citation_verification": citation_time,
                "total": total_time,
            },
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
        )

    def _verify_citation(
        self,
        answer: str,
        evidences: List[Evidence],
    ) -> Optional[CitationValidation]:

        if (
            self.citation_service is None
            or not evidences
        ):
            return None

        chunk_ids = _citation_chunk_ids(
            evidences
        )

        if not chunk_ids:
            return None

        result = self.citation_service.verify_claim(
            answer,
            chunk_ids,
        )

        return _to_citation_validation(
            result
        )