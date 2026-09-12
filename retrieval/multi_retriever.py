from typing import List
from .base_retriever import BaseRetriever, RetrievalRequest, Evidence, RetrievalContext
from .vector_retriever import VectorRetriever
from .graph_retriever import GraphRetriever


class MultiRetriever(BaseRetriever):
    """
    混合检索器：接收上游A模块selected_route，支持 vector / graph / hybrid 三种调度模式
    对外统一 BaseRetriever 接口契约
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

    def retrieve(self, query: str, context: RetrievalContext | None, top_k: int) -> List[Evidence]:
        # 边界保护：context为None时构造空上下文
        if context is None:
            context = RetrievalContext()

        selected_route = context.selected_route
        print(f"[MultiRetriever][INFO] selected_route={selected_route}, query_type={context.query_type}")

        vector_res: List[Evidence] = []
        graph_res: List[Evidence] = []

        if selected_route == "vector":
            # 仅向量检索
            if self.enable_vector:
                vector_res = self.vector_retriever.retrieve(query, context, top_k)
            final = vector_res

        elif selected_route == "graph":
            # 仅图谱检索
            if self.enable_graph:
                graph_res = self.graph_retriever.retrieve(query, context, top_k)
            final = graph_res

        else:
            # hybrid 默认模式：两路召回，图谱证据优先
            if self.enable_vector:
                vector_res = self.vector_retriever.retrieve(query, context, top_k)
            if self.enable_graph:
                graph_res = self.graph_retriever.retrieve(query, context, top_k)
            # 图谱证据放前面，防止top‑k截断丢失关系边
            final = graph_res + vector_res

        # top‑k全局截断
        final = final[:top_k]
        return final
    def _inner_retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        return self.retrieve(request.query, request.context, request.top_k)


if __name__ == "__main__":
    mr = MultiRetriever()
    test_query = "朝鲜族农乐舞（象帽舞）和吉林省延边朝鲜族自治州有什么关系？"

    print("========== 测试1 hybrid（默认混合） ==========")
    ctx_hybrid = RetrievalContext(query_type="relation", selected_route="hybrid")
    res_hybrid = mr.retrieve(test_query, ctx_hybrid, top_k=4)
    for item in res_hybrid:
        print(f"retriever:{item.retriever}, chunk_id:{repr(item.chunk_id)}")

    print("\n========== 测试2 强制 graph 模式 ==========")
    ctx_graph = RetrievalContext(query_type="relation", selected_route="graph")
    res_graph = mr.retrieve(test_query, ctx_graph, top_k=4)
    for item in res_graph:
        print(f"retriever:{item.retriever}, chunk_id:{repr(item.chunk_id)}")
        if hasattr(item, "relation_path"):
            print(f"   relation_path: {item.relation_path}")

    print("\n========== 测试3 强制 vector 模式 ==========")
    ctx_vector = RetrievalContext(selected_route="vector")
    res_vector = mr.retrieve(test_query, ctx_vector, top_k=4)
    for item in res_vector:
        print(f"retriever:{item.retriever}, chunk_id:{repr(item.chunk_id)}")
