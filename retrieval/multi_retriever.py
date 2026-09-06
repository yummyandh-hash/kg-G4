from typing import List
from .base_retriever import BaseRetriever, RetrievalRequest, Evidence
from .vector_retriever import VectorRetriever
from .graph_retriever import GraphRetriever


class MultiRetriever(BaseRetriever):
    """
    混合检索器：同时调用向量检索 + 图检索，合并结果，对外统一BaseRetriever接口
    """
    def __init__(
        self,
        chunks_file: str = "data/chunks/chunks.jsonl",
        enable_vector: bool = True,
        enable_graph: bool = True
    ):
        self.enable_vector = enable_vector
        self.enable_graph = enable_graph

        if self.enable_vector:
            self.vector_retriever = VectorRetriever(chunks_file=chunks_file)
        if self.enable_graph:
            self.graph_retriever = GraphRetriever()

    def _inner_retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        all_evidences: List[Evidence] = []

        # 1.向量检索
        if self.enable_vector:
            vec_res = self.vector_retriever.retrieve(request.query, request.context)
            all_evidences.extend(vec_res)

        # 2.图节点文本检索
        if self.enable_graph:
            graph_res = self.graph_retriever.retrieve(request.query, request.context)
            all_evidences.extend(graph_res)

        # 简单按分数降序排序，分数越高越靠前
        all_evidences.sort(key=lambda x: x.score, reverse=True)

        # 截断到top_k
        return all_evidences[:request.top_k]


if __name__ == "__main__":
    # 自测demo
    retriever = MultiRetriever()
    results = retriever.retrieve(query="苏绣", context=None)
    print(f"混合检索共返回 {len(results)} 条\n")
    for idx, ev in enumerate(results):
        print(f"---{idx+1} | score:{ev.score:.4f} | retriever:{ev.retriever}---")
        print(f"evidence: {ev.evidence[:120]}\n")
