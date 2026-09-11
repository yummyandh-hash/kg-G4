from typing import List
from .base_retriever import BaseRetriever, RetrievalRequest, Evidence, RetrievalContext
from .vector_retriever import VectorRetriever
from .graph_retriever import GraphRetriever


class MultiRetriever(BaseRetriever):
    """
    混合检索器：同时调用向量检索 + 图检索，合并结果，对外统一BaseRetriever接口
    Stage2：支持 selected_route 强制分发 vector / graph / hybrid，对齐组内接口规范
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
        ctx = request.context
        # ==========调试打印==========
        print("[MultiRetriever DEBUG] request.context =", request.context)
        route = ctx.selected_route if ctx is not None else None
        if ctx is not None:
            print("[MultiRetriever DEBUG] query_type =", ctx.query_type)
            print("[MultiRetriever DEBUG] selected_route =", route)
        # ============================

        # Stage2 强制路由分发逻辑：vector / graph / hybrid(None)
        if route == "vector":
            # 仅向量检索
            if self.enable_vector:
                vec_res = self.vector_retriever.retrieve(
                    request.query,
                    context=ctx,
                    top_k=request.top_k
                )
                all_evidences.extend(vec_res)

        elif route == "graph":
            # 仅图谱检索
            if self.enable_graph:
                graph_res = self.graph_retriever.retrieve(
                    request.query,
                    context=ctx,
                    top_k=request.top_k
                )
                all_evidences.extend(graph_res)

        else:
            # hybrid / None：双路全部执行
            # 1.向量检索
            if self.enable_vector:
                vec_res = self.vector_retriever.retrieve(
                    request.query,
                    context=ctx,
                    top_k=request.top_k
                )
                all_evidences.extend(vec_res)
            # 2.图检索
            if self.enable_graph:
                graph_res = self.graph_retriever.retrieve(
                    request.query,
                    context=ctx,
                    top_k=request.top_k
                )
                all_evidences.extend(graph_res)

        # 💡 融合与截断：优先保证带有 relation_path 的图谱证据不被挤掉
        graph_with_path = [e for e in all_evidences if e.relation_path]
        others = [e for e in all_evidences if not e.relation_path]
        # 普通文本证据按分数降序
        others.sort(key=lambda x: x.score, reverse=True)
        # 图谱证据优先，再拼接高分向量证据
        final_evidences = graph_with_path + others
        return final_evidences[:request.top_k]


if __name__ == "__main__":
    retriever = MultiRetriever()
    test_query = "朝鲜族农乐舞（象帽舞）和吉林省延边朝鲜族自治州有什么关系？"

    print("==========【测试1 hybrid 默认双路】==========")
    test_ctx1 = RetrievalContext(query_type="relation", selected_route=None)
    results1 = retriever.retrieve(query=test_query, context=test_ctx1, top_k=5)
    print(f"\n混合检索共返回 {len(results1)} 条\n")
    for idx, ev in enumerate(results1):
        print(f"---{idx+1} | score:{ev.score:.4f} | retriever:{ev.retriever}---")
        print(f"entity_ids: {ev.entity_ids}")
        print(f"relation_path: {ev.relation_path}")
        print(f"evidence: {ev.evidence[:120]}\n")

    print("==========【测试2 强制仅graph】==========")
    test_ctx2 = RetrievalContext(query_type="relation", selected_route="graph")
    results2 = retriever.retrieve(query=test_query, context=test_ctx2, top_k=5)
    print(f"图谱检索共返回 {len(results2)} 条\n")
    for idx, ev in enumerate(results2):
        print(f"---{idx+1} | score:{ev.score:.4f} | retriever:{ev.retriever}---")
        print(f"entity_ids: {ev.entity_ids}")
        print(f"relation_path: {ev.relation_path}\n")

    print("==========【测试3 强制仅vector】==========")
    test_ctx3 = RetrievalContext(query_type="relation", selected_route="vector")
    results3 = retriever.retrieve(query=test_query, context=test_ctx3, top_k=5)
    print(f"向量检索共返回 {len(results3)} 条\n")
    for idx, ev in enumerate(results3):
        print(f"---{idx+1} | score:{ev.score:.4f} | retriever:{ev.retriever}---")
        print(f"entity_ids: {ev.entity_ids}")
        print(f"relation_path: {ev.relation_path}\n")
