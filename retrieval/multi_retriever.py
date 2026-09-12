from typing import List

from .base_retriever import BaseRetriever, RetrievalRequest, Evidence
from .vector_retriever import VectorRetriever
from .graph_retriever import GraphRetriever


class MultiRetriever(BaseRetriever):
    """
    混合检索器：同时调用向量检索 + 图检索，
    合并结果，对外统一 BaseRetriever 接口。
    """

    def __init__(
        self,
        chunks_file: str = "data/chunks/chunks.jsonl",
        enable_vector: bool = True,
        enable_graph: bool = True,
    ):
        self.enable_vector = enable_vector
        self.enable_graph = enable_graph

        if self.enable_vector:
            self.vector_retriever = VectorRetriever(
                chunks_file=chunks_file
            )

        if self.enable_graph:
            self.graph_retriever = GraphRetriever()

    def _inner_retrieve(
        self,
        request: RetrievalRequest,
    ) -> List[Evidence]:
        all_evidences: List[Evidence] = []

        # 1. 向量检索，传入 query、context、top_k
        if self.enable_vector:
            vec_res = self.vector_retriever.retrieve(
                request.query,
                context=request.context,
                top_k=request.top_k,
            )
            all_evidences.extend(vec_res)

        # 2. 图检索，传入 query、context、top_k
        if self.enable_graph:
            graph_res = self.graph_retriever.retrieve(
                request.query,
                context=request.context,
                top_k=request.top_k,
            )
            all_evidences.extend(graph_res)

        # 3. 优先保留带 relation_path 的图关系证据
        graph_with_path = [
            evidence
            for evidence in all_evidences
            if evidence.relation_path
        ]

        others = [
            evidence
            for evidence in all_evidences
            if not evidence.relation_path
        ]

        # 其他证据按照相关性分数降序排列
        others.sort(
            key=lambda evidence: evidence.score,
            reverse=True,
        )

        # 关系证据优先，剩余位置由高分证据补齐
        final_evidences = graph_with_path + others

        return final_evidences[: request.top_k]