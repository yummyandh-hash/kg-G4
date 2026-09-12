from typing import List
from .base_retriever import BaseRetriever, RetrievalRequest, Evidence, RetrievalContext
from .vector_retriever import VectorRetriever
from .graph_retriever import GraphRetriever


class MultiRetriever(BaseRetriever):
    """
    混合检索器：同时调用向量检索 + 图检索，对外统一BaseRetriever接口
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
        # ==========调试打印==========
        print("[MultiRetriever DEBUG] request.context =", request.context)
        if request.context is not None:
            print("[MultiRetriever DEBUG] query_type =", request.context.query_type)
        # ============================

        # 1.向量检索
        if self.enable_vector:
            vec_res = self.vector_retriever.retrieve(
                request.query,
                context=request.context,
                top_k=request.top_k
            )
            all_evidences.extend(vec_res)
        # 2.图检索
        if self.enable_graph:
            graph_res = self.graph_retriever.retrieve(
                request.query,
                context=request.context,
                top_k=request.top_k
            )
            all_evidences.extend(graph_res)

        # 💡 优化融合与截断逻辑：优先保证带有 relation_path 的图关系边不被向量结果挤掉
        graph_with_path = [e for e in all_evidences if e.relation_path]
        others = [e for e in all_evidences if not e.relation_path]
        # 其他纯文本证据按 score 降序排列
        others.sort(key=lambda x: x.score, reverse=True)
        # 优先输出图谱关系，剩余配额给高分文本证据
        final_evidences = graph_with_path + others
        return final_evidences[:request.top_k]


if __name__ == "__main__":
    retriever = MultiRetriever()
    test_query = "朝鲜族农乐舞（象帽舞）和吉林省延边朝鲜族自治州有什么关系？"
    print("==========【测试 hybrid 默认双路】==========")
    test_ctx1 = RetrievalContext(query_type="relation")
    results1 = retriever.retrieve(query=test_query, context=test_ctx1, top_k=5)
    print(f"\n混合检索共返回 {len(results1)} 条\n")
    for idx, ev in enumerate(results1):
        print(f"---{idx+1} | score:{ev.score:.4f} | retriever:{ev.retriever}---")
        print(f"entity_ids: {ev.entity_ids}")
        print(f"relation_path: {ev.relation_path}")
        print(f"evidence: {ev.evidence[:120]}\n")
