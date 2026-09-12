from time import perf_counter
from typing import List, Optional, Protocol
from orchestration.context import build_context
from orchestration.generation import LLMGenerator
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


def _path_entities(path) -> List[str]:
    """
    从 relation_path 中提取实体节点。

    兼容：
    1. ["A", "REL", "B"]
    2. [{"source": "A", "relation": "REL", "target": "B"}]
    3. ["{'source': 'A', 'relation': 'REL', 'target': 'B'}"]
    """
    if not path:
        return []

    entities = []

    # --------------------------------------------------
    # 字符串列表
    # --------------------------------------------------
    if all(isinstance(item, str) for item in path):

        # 传统路径：
        # ["A", "REL", "B", "REL2", "C"]
        if len(path) >= 3 and len(path) % 2 == 1:
            return path[::2]

        # --------------------------------------------------
        # dict 被转换成字符串
        # --------------------------------------------------
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

    # --------------------------------------------------
    # 原生 dict 列表
    # --------------------------------------------------
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
    """
    将 relation_path 解析为
    (source, relation, target) 三元组。

    同时兼容：
    1. ["A", "REL", "B"]
    2. [{"source": "A", "relation": "REL", "target": "B"}]
    3. ["{'source': 'A', 'relation': 'REL', 'target': 'B'}"]
    """
    if not path:
        return []

    edges = []

    # --------------------------------------------------
    # 字符串列表
    # --------------------------------------------------
    if all(isinstance(item, str) for item in path):

        # 兼容：
        # ["A", "REL", "B", "REL2", "C"]
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

        # --------------------------------------------------
        # 兼容 dict 被转换成字符串
        # --------------------------------------------------
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

    # --------------------------------------------------
    # 原生 dict 列表
    # --------------------------------------------------
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


class QueryService:

    def __init__(
        self,
        router: RouterProtocol,
        retriever: RetrieverProtocol,
        top_k: int = 5,
        generator: Optional[LLMGenerator] = None,
    ):
        self.router = router
        self.retriever = retriever
        self.top_k = top_k
        self.generator = generator 

    def query(
        self,
        question: str,
    ) -> AnswerResponse:

        start_time = perf_counter()

        # ==========================================================
        # Query Routing
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
        # RetrievalContext
        # ==========================================================

        context = RetrievalContext(
            query_type=decision.query_type,
            complexity_score=decision.complexity_score,
            top_k=self.top_k,
            selected_route=decision.selected_route,
        )

        # ==========================================================
        # MultiRetriever
        # ==========================================================

        evidences = self.retriever.retrieve(
            question,
            context,
        )

        # ==========================================================
        # Debug：原始 Evidence
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
        # Normalize
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

        context = build_context(
            query=question,
            evidences=evidences,
            max_evidence=self.top_k,
        )

        print("========== LLM CONTEXT ==========")
        print(context)
        print("=================================")

        if self.generator is not None:
            answer = self.generator.generate(
                question=question,
                context=context,
            )
        else:
            answer = ""

        # ==========================================================
        # 构建 entity_id -> 中文名称映射
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
        # 收集 relation paths
        # ==========================================================

        paths = [
            evidence.relation_path
            for evidence in evidences
            if evidence.relation_path
        ]

        # ==========================================================
        # 构建 Graph Nodes
        # ==========================================================

        node_map = {}

        for evidence in evidences:

            entity_ids = getattr(
                evidence,
                "entity_ids",
                None,
            ) or []

            # ------------------------------------------------------
            # entity_ids
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
            # relation_path
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
        # 构建 Graph Edges
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
        # Debug：最终图谱
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
        # AnswerResponse
        # ==========================================================

        elapsed = (
            perf_counter()
            - start_time
        )

        return AnswerResponse(
            answer=answer,
            query_type=decision.query_type,
            complexity_score=decision.complexity_score,
            selected_route=decision.selected_route,
            route_reason=decision.reason,
            evidences=evidences,
            paths=paths,
            sources=list(
                dict.fromkeys(
                    evidence.source_id
                    for evidence in evidences
                    if evidence.source_id
                )
            ),
            timing={"total_ms": elapsed * 1000},
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
        )