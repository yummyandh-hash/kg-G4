from time import perf_counter
from typing import List, Optional, Protocol
import re

from orchestration.models import (
    AnswerResponse,
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
            reason="Stage 1：采用 Graph + Vector 混合检索。",
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

    # 已经是 orchestration.models.Evidence
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
    """
    从 D GraphRetriever 的 path 文本中提取中文节点名称。

    例如：

    朝鲜族农乐舞（象帽舞） --[分布于]--> 吉林省延边朝鲜族自治州

    返回：

    [
        "朝鲜族农乐舞（象帽舞）",
        "吉林省延边朝鲜族自治州"
    ]
    """

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
    """
    从两跳 path 中提取三个中文节点名称。

    例如：

    A --[R1]--> B --[R2]--> C

    返回：

    [A, B, C]
    """

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
    构建：

        entity_id -> 中文节点名称

    映射。

    数据来源：

    1. GraphRetriever 节点证据：
       entity_ids=[eid]
       source_name=name

    2. GraphRetriever one-hop：
       entity_ids=[src_eid, target_eid]
       content/path 中包含：
       src中文名 --[relation]--> target中文名

    3. GraphRetriever two-hop：
       entity_ids=[src_eid, mid_eid, target_eid]
       path 中包含三个中文节点名。
    """

    node_name_map = {}

    for evidence in evidences:

        entity_ids = getattr(
            evidence,
            "entity_ids",
            None,
        ) or []

        # ======================================================
        # 1. 普通 Graph Node Evidence
        # ======================================================

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

        # ======================================================
        # 2. 根据 retriever 类型判断 path
        # ======================================================

        retrieval_method = getattr(
            evidence,
            "retrieval_method",
            "",
        )

        if retrieval_method == "graph_retriever_one_hop":

            path_texts = []

            # GraphRetriever 当前 path=[path_text]
            raw_path = getattr(
                evidence,
                "path",
                None,
            )

            if raw_path:
                path_texts.extend(
                    raw_path
                )

            # normalize 后 path 不再保留，
            # 所以也尝试从 content 中读取
            content = getattr(
                evidence,
                "content",
                "",
            )

            if content:
                path_texts.append(
                    content
                )

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
                path_texts.extend(
                    raw_path
                )

            content = getattr(
                evidence,
                "content",
                "",
            )

            if content:
                path_texts.append(
                    content
                )

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


def _path_entities(
    path,
) -> List[str]:
    """
    从 relation_path 中提取所有实体 ID。

    relation_path 当前结构：

    [
        {
            "source": "...",
            "target": "...",
            "relation": "..."
        }
    ]
    """

    entities = []

    if not path:
        return entities

    for item in path:

        if not isinstance(item, dict):
            continue

        source = item.get(
            "source"
        )

        target = item.get(
            "target"
        )

        if source:
            entities.append(
                source
            )

        if target:
            entities.append(
                target
            )

    return list(
        dict.fromkeys(entities)
    )


def _path_edges(
    path,
) -> List[tuple[str, str, str]]:
    """
    从 relation_path 中提取图谱边。
    """

    edges = []

    if not path:
        return edges

    for item in path:

        if not isinstance(item, dict):
            continue

        source = item.get(
            "source"
        )

        relation = item.get(
            "relation"
        )

        target = item.get(
            "target"
        )

        if (
            source
            and relation
            and target
        ):
            edges.append(
                (
                    source,
                    relation,
                    target,
                )
            )

    return edges


class QueryService:

    def __init__(
        self,
        router: RouterProtocol,
        retriever: RetrieverProtocol,
        top_k: int = 5,
    ):
        self.router = router
        self.retriever = retriever
        self.top_k = top_k

    def query(
        self,
        question: str,
    ) -> AnswerResponse:

        start_time = perf_counter()

        # ==========================================================
        # 1. Query Routing
        # ==========================================================

        decision = self.router.route(
            question
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
        # 3. MultiRetriever
        # ==========================================================

        evidences = self.retriever.retrieve(
            question,
            context,
        )

        # ==========================================================
        # 4. Debug：原始 Evidence
        # ==========================================================

        print(
            "========== RAW D EVIDENCES =========="
        )

        for evidence in evidences:

            print(
                "TYPE:",
                type(evidence),
            )

            print(
                "EVIDENCE:",
                evidence,
            )

            print(
                "PATH:",
                getattr(
                    evidence,
                    "path",
                    None,
                ),
            )

            print(
                "ENTITY_IDS:",
                getattr(
                    evidence,
                    "entity_ids",
                    None,
                ),
            )

            print(
                "RELATION_PATH:",
                getattr(
                    evidence,
                    "relation_path",
                    None,
                ),
            )

            print(
                "===================================="
            )

        # ==========================================================
        # 5. Normalize
        # ==========================================================

        evidences = [
            normalize_evidence(evidence)
            for evidence in evidences
        ]

        print(
            "========== NORMALIZED EVIDENCES =========="
        )

        for evidence in evidences:

            print(
                "EVIDENCE:",
                evidence,
            )

            print(
                "ENTITY_IDS:",
                getattr(
                    evidence,
                    "entity_ids",
                    None,
                ),
            )

            print(
                "RELATION_PATH:",
                getattr(
                    evidence,
                    "relation_path",
                    None,
                ),
            )

            print(
                "=========================================="
            )

        # ==========================================================
        # 6. 构建 entity_id -> 中文名称映射
        # ==========================================================

        node_name_map = _build_node_name_map(
            evidences
        )

        print(
            "========== NODE NAME MAP =========="
        )

        for entity_id, name in node_name_map.items():

            print(
                entity_id,
                "=>",
                name,
            )

        print(
            "==================================="
        )

        # ==========================================================
        # 7. 收集 relation paths
        # ==========================================================

        paths = [
            evidence.relation_path
            for evidence in evidences
            if evidence.relation_path
        ]

        # ==========================================================
        # 8. 构建 Graph Nodes
        # ==========================================================

        node_map = {}

        for evidence in evidences:

            entity_ids = getattr(
                evidence,
                "entity_ids",
                None,
            ) or []

            # ------------------------------------------------------
            # 8.1 entity_ids
            # ------------------------------------------------------

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

            # ------------------------------------------------------
            # 8.2 relation_path
            # ------------------------------------------------------

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
        # 9. 构建 Graph Edges
        # ==========================================================

        import ast

        edge_map = {}

        for evidence in evidences:

            relation_paths = evidence.relation_path or []

            for rel in relation_paths:

                # D 的 relation_path 在当前 normalize 后是字符串：
                # "{'source': '...', 'target': '...', 'relation': '...'}"
                if isinstance(rel, str):
                    try:
                        rel = ast.literal_eval(rel)
                    except (ValueError, SyntaxError):
                        print(
                            "[WARN] 无法解析 relation_path:",
                            rel
                        )
                        continue

                # 正常情况下应该是 dict
                if not isinstance(rel, dict):
                    print(
                        "[WARN] relation_path 类型异常:",
                        type(rel),
                        rel
                    )
                    continue

                source = rel.get("source")
                target = rel.get("target")
                relation = rel.get("relation")

                if not source or not target or not relation:
                    print(
                        "[WARN] relation_path 缺少字段:",
                        rel
                    )
                    continue

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

        graph_edges = list(edge_map.values())

        # ==========================================================
        # 10. Debug：最终图谱
        # ==========================================================

        print(
            "========== GRAPH NODES =========="
        )

        for node in graph_nodes:
            print(
                "NODE:",
                repr(node.node_id),
                "=>",
                repr(node.label),
            )

        print(
            "========== GRAPH EDGES =========="
        )

        for edge in graph_edges:
            print(
                "EDGE:",
                repr(edge.source),
                "--[",
                edge.relation,
                "]-->",
                repr(edge.target),
            )

        print(
            "========== GRAPH ID CHECK =========="
        )

        node_ids = {
            node.node_id
            for node in graph_nodes
        }

        for edge in graph_edges:

            print(
                "EDGE SOURCE:",
                repr(edge.source),
                "EXISTS:",
                edge.source in node_ids,
            )

            print(
                "EDGE TARGET:",
                repr(edge.target),
                "EXISTS:",
                edge.target in node_ids,
            )

        print(
            "================================="
        )

        # ==========================================================
        # 11. AnswerResponse
        # ==========================================================

        elapsed = (
            perf_counter()
            - start_time
        )

        return AnswerResponse(
            answer="",
            query_type=decision.query_type,
            complexity_score=decision.complexity_score,
            selected_route=decision.selected_route,
            route_reason=decision.reason,
            evidences=evidences,
            paths=paths,
            sources=[],
            timing={
                "total_ms": elapsed * 1000,
            },
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
        )