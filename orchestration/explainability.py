from typing import Any, Dict, List

from orchestration.models import AnswerResponse, Evidence


def _format_relation_path(path: Any) -> List[str]:
    """统一关系路径格式，便于前端直接展示。"""
    if not path:
        return []

    if isinstance(path, (list, tuple)):
        return [str(item) for item in path]

    return [str(path)]


def _format_score(score: Any) -> float:
    """统一 Evidence 分数格式。"""
    try:
        return float(score)
    except (TypeError, ValueError):
        return 0.0


def _format_evidence(
    evidence: Evidence,
    index: int,
) -> Dict[str, object]:
    """将单条 Evidence 转换为前端可直接使用的结构。"""
    return {
        "index": index,
        "evidence_id": evidence.evidence_id,
        "content": evidence.content,
        "retrieval_method": evidence.retrieval_method,
        "score": _format_score(evidence.score),
        "source_id": evidence.source_id,
        "source_url": evidence.source_url,
        "entity_ids": list(evidence.entity_ids or []),
        "relation_path": _format_relation_path(
            evidence.relation_path
        ),
    }


def _format_graph(response: AnswerResponse) -> Dict[str, object]:
    """将知识图谱子图整理为前端可直接消费的 nodes / edges。"""
    nodes = [
        {
            "id": node.node_id,
            "label": node.label,
            "properties": node.properties,
        }
        for node in response.graph_nodes
    ]

    edges = [
        {
            "source": edge.source,
            "target": edge.target,
            "relation": edge.relation,
            "properties": edge.properties,
        }
        for edge in response.graph_edges
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def build_explanation(response: AnswerResponse) -> Dict[str, object]:
    """
    将 AnswerResponse 整理为统一的 Stage 2 可解释性结构。

    用于向 Web/API 层提供：
    - Adaptive Router 决策
    - 检索 Evidence
    - Relation Path
    - Source
    - Graph Subgraph
    - 查询性能信息
    """

    evidences = [
        _format_evidence(evidence, index)
        for index, evidence in enumerate(
            response.evidences,
            start=1,
        )
    ]

    relation_paths = [
        _format_relation_path(path)
        for path in response.paths
        if path
    ]

    graph = _format_graph(response)

    return {
        # ---------- Router ----------
        "query_type": response.query_type,
        "complexity_score": response.complexity_score,
        "selected_retriever": response.selected_route,
        "route_reason": response.route_reason,

        # ---------- Evidence ----------
        "evidence": evidences,
        "evidence_count": len(evidences),

        # ---------- Relation Path ----------
        "relation_paths": relation_paths,
        "path_count": len(relation_paths),

        # ---------- Sources ----------
        "sources": response.sources,
        "source_count": len(response.sources),

        # ---------- Graph ----------
        "graph": graph,

        # ---------- Performance ----------
        "timing": response.timing,
    }