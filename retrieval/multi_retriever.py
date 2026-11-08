from typing import List
from .base_retriever import BaseRetriever, RetrievalRequest, Evidence, RetrievalContext
from .vector_retriever import VectorRetriever
from .graph_retriever import GraphRetriever


class MultiRetriever(BaseRetriever):
    """
    混合检索器：接收上游A模块selected_route，支持 vector / graph / hybrid 三种调度模式
    对外统一 BaseRetriever 接口契约
    新增可选PPR重排序，默认关闭，enable_ppr=True开启
    """
    def __init__(
        self,
        chunks_file: str = "data/chunks/chunks.jsonl",
        enable_vector: bool = True,
        enable_graph: bool = True,
        enable_ppr: bool = False
    ):
        self.enable_vector = enable_vector
        self.enable_graph = enable_graph
        self.enable_ppr = enable_ppr

        if self.enable_vector:
            self.vector_retriever = VectorRetriever(chunks_file=chunks_file)
        if self.enable_graph:
            self.graph_retriever = GraphRetriever()

    def _ppr_rerank(self, graph_evidences: List[Evidence]) -> List[Evidence]:
        """
        基于Neo4j GDS PageRank对图谱证据重打分重排
        只修改score，不改动Evidence输出字段；异常自动降级返回原顺序
        依赖：预先执行 CALL gds.graph.project('kg_graph','*','*')
        AuraDB免费版不支持GDS投影，会自动降级
        """
        if not graph_evidences:
            return graph_evidences

        # 从第一条证据的relation_path取源实体作为PPR种子
        first_path_list = graph_evidences[0].relation_path
        if not first_path_list or len(first_path_list) == 0:
            return graph_evidences
        seed_source = first_path_list[0]["source"]
        seed_nodes = [seed_source]

        try:
            driver = self.graph_retriever.driver
            cypher = """
            CALL gds.pageRank.stream('kg_graph', {
                sourceNodes: $seedNodes,
                dampingFactor:0.85
            })
            YIELD nodeId, score
            RETURN gds.util.asNode(nodeId).id AS eid, score
            """
            records, _, _ = driver.execute_query(cypher, seedNodes=seed_nodes)
            ppr_map = {r["eid"]: r["score"] for r in records}

            # 使用relation_path的target实体获取ppr分数
            for ev in graph_evidences:
                if ev.relation_path and len(ev.relation_path) > 0:
                    target_eid = ev.relation_path[0]["target"]
                    ev.score = ppr_map.get(target_eid, ev.score)

            graph_evidences.sort(key=lambda x: x.score, reverse=True)
            return graph_evidences

        except Exception as e:
            print(f"[PPR WARN] ppr执行失败，退回原有顺序: {e}")
            return graph_evidences

    def retrieve(self, query: str, context: RetrievalContext | None = None, top_k: int = 5) -> List[Evidence]:
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

        # ========== 新增PPR逻辑 ==========
        if self.enable_ppr and len(graph_res) > 0:
            graph_res = self._ppr_rerank(graph_res)
            # 重新合并，重排后的图谱在前
            final = graph_res + vector_res
        # =================================

        # top‑k全局截断
        final = final[:top_k]
        return final

    def _inner_retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        return self.retrieve(request.query, request.context, request.top_k)


if __name__ == "__main__":
    test_query = "朝鲜族农乐舞（象帽舞）和吉林省延边朝鲜族自治州有什么关系？"

    print("========== 测试1 hybrid（默认混合，PPR关闭） ==========")
    mr = MultiRetriever()
    ctx_hybrid = RetrievalContext(query_type="relation", selected_route="hybrid")
    res_hybrid = mr.retrieve(test_query, ctx_hybrid, top_k=4)
    for item in res_hybrid:
        print(f"retriever:{item.retriever}, chunk_id:{repr(item.chunk_id)}")

    print("\n========== 测试2 强制 graph 模式（PPR关闭） ==========")
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

    print("\n========== 测试4 graph模式【开启PPR对比演示】 ==========")
    mr_ppr = MultiRetriever(enable_ppr=True)
    res_ppr = mr_ppr.retrieve(test_query, ctx_graph, top_k=4)
    for item in res_ppr:
        print(f"score:{item.score:.4f}, retriever:{item.retriever}")
        if hasattr(item, "relation_path"):
            print(f"   relation_path: {item.relation_path}")
