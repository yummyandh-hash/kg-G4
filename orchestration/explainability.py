from typing import Dict, List

from orchestration.models import AnswerResponse


def build_explanation(response: AnswerResponse) -> Dict[str, object]:
    """
    将问答结果整理成前端可直接展示的解释信息。
    """

    return {
        "selected_retriever": response.selected_route,
        "route_reason": response.route_reason,
        "route_confidence": response.route_confidence,
        "evidence": [
            {
                "evidence_id": evidence.evidence_id,
                "content": evidence.content,
                "retrieval_method": evidence.retrieval_method,
                "score": evidence.score,
                "source_id": evidence.source_id,
                "source_url": evidence.source_url,
                "relation_path": evidence.relation_path,
            }
            for evidence in response.evidences
        ],
        "relation_paths": response.paths,
        "sources": response.sources,
        "graph": {
            "nodes": [
                {
                    "id": node.node_id,
                    "label": node.label,
                    "properties": node.properties,
                }
                for node in response.graph_nodes
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                    "properties": edge.properties,
                }
                for edge in response.graph_edges
            ],
        },
    }
