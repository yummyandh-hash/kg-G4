import time
import os
from datetime import datetime
from typing import List
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv
from .base_retriever import BaseRetriever, RetrievalRequest, Evidence

# 定位到项目根目录，加载根目录下的.env
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class GraphRetriever(BaseRetriever):
    def __init__(self):
        """从项目根目录.env读取Neo4j连接信息，禁止硬编码凭证"""
        self.uri = os.getenv("NEO4J_URI")
        self.user = os.getenv("NEO4J_USER")
        self.password = os.getenv("NEO4J_PASSWORD")
        if not self.uri or not self.user or not self.password:
            raise RuntimeError("请检查项目根目录的.env文件，Neo4j连接参数不能为空")
        self.driver: Driver | None = None
        self._connect()

    def _connect(self):
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()
            print("[INFO] Neo4j连接验证成功")
        except Exception as e:
            print(f"[ERROR] Neo4j连接失败: {e}")
            self.driver = None

    def _inner_retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        evidences: List[Evidence] = []
        if self.driver is None:
            return evidences

        # 1.双向contains：节点名包含query OR query包含节点名，解决长自然问句内嵌实体的场景
        cypher_node = """
        MATCH (n:InheritProject)
        WHERE toLower(n.name) CONTAINS toLower($q_str) OR toLower($q_str) CONTAINS toLower(n.name)
        RETURN n.name as name, n.attributes_json as attr, n.entity_id as eid
        LIMIT $top_k
        """
        t0 = time.time()
        node_hit_entities: List[str] = []
        hit_records = []
        try:
            with self.driver.session() as session:
                records = session.run(cypher_node, q_str=request.query, top_k=request.top_k)
                for rec in records:
                    hit_records.append({"name": rec["name"], "attr": rec["attr"], "eid": rec["eid"]})

            # Python侧：按实体name字符串长度降序，优先选择长实体，规避短实体误匹配
            hit_records.sort(key=lambda x: len(x["name"]), reverse=True)

            for rec in hit_records:
                name = rec["name"]
                attr = rec["attr"]
                eid = rec["eid"]
                content = f"项目名称：{name}，属性信息：{attr}"
                ev = Evidence(
                    evidence=content,
                    score=0.80,
                    path=[],
                    retriever="graph_retriever",
                    latency=time.time() - t0,
                    document_id=eid or "",
                    chunk_id="graph_node",
                    source_url="",
                    source_name=name,
                    source_category="",
                    source_region="",
                    source_org="",
                    retrieved_at=datetime.now().isoformat(),
                    source_batch="neo4j_node"
                )
                evidences.append(ev)
                node_hit_entities.append(name)

        except Exception as e:
            print(f"[WARN] graph node retrieve error: {e}")

        # 2. 根据context的query_type，决定是否追加一跳/两跳关系证据
        query_type = None
        if hasattr(request, "context") and request.context is not None:
            query_type = getattr(request.context, "query_type", None)

        if query_type in ("relation", "relation_2hop") and len(node_hit_entities) > 0:
            entity = node_hit_entities[0]  # 取排序后最长匹配实体做关系查询
            hop1_list = self._one_hop_retrieve(entity, top_k=4)
            evidences.extend(hop1_list)
            # 如果是relation_2hop，追加two‑hop
            if query_type == "relation_2hop":
                hop2_list = self._two_hop_retrieve(entity, top_k=4)
                evidences.extend(hop2_list)

        return evidences

    def _one_hop_retrieve(self, entity_name: str, top_k: int = 4) -> List[Evidence]:
        res: List[Evidence] = []
        if self.driver is None:
            return res
        cypher_onehop = """
        MATCH (h:InheritProject {name:$entity_name})-[r]-(neigh)
        RETURN h.name AS src, type(r) AS rel, neigh.name AS target
        LIMIT $top_k
        """
        t0 = time.time()
        try:
            with self.driver.session() as session:
                records = session.run(cypher_onehop, entity_name=entity_name, top_k=top_k)
                for rec in records:
                    path_text = f"{rec['src']} --[{rec['rel']}]--> {rec['target']}"
                    ev = Evidence(
                        evidence=path_text,
                        score=0.70,
                        path=[path_text],
                        retriever="graph_retriever_one_hop",
                        latency=time.time() - t0,
                        document_id="",
                        chunk_id="graph_one_hop",
                        source_url="",
                        source_name=rec["src"],
                        source_category="",
                        source_region="",
                        source_org="",
                        retrieved_at=datetime.now().isoformat(),
                        source_batch="neo4j_1hop"
                    )
                    res.append(ev)
        except Exception as e:
            print(f"[WARN] one‑hop query error: {e}")
        return res

    def _two_hop_retrieve(self, entity_name: str, top_k: int = 4) -> List[Evidence]:
        res: List[Evidence] = []
        if self.driver is None:
            return res
        cypher_twohop = """
        MATCH (h:InheritProject {name:$entity_name})-[r1]-(mid)-[r2]-(neigh2)
        RETURN h.name AS src, type(r1) AS rel1, mid.name AS mid_node, type(r2) AS rel2, neigh2.name AS target
        LIMIT $top_k
        """
        t0 = time.time()
        try:
            with self.driver.session() as session:
                records = session.run(cypher_twohop, entity_name=entity_name, top_k=top_k)
                for rec in records:
                    path_text = f"{rec['src']} --[{rec['rel1']}]--> {rec['mid_node']} --[{rec['rel2']}]--> {rec['target']}"
                    ev = Evidence(
                        evidence=path_text,
                        score=0.60,
                        path=[path_text],
                        retriever="graph_retriever_two_hop",
                        latency=time.time() - t0,
                        document_id="",
                        chunk_id="graph_two_hop",
                        source_url="",
                        source_name=rec["src"],
                        source_category="",
                        source_region="",
                        source_org="",
                        retrieved_at=datetime.now().isoformat(),
                        source_batch="neo4j_2hop"
                    )
                    res.append(ev)
        except Exception as e:
            print(f"[WARN] two‑hop query error: {e}")
        return res

    def close(self):
        if self.driver:
            self.driver.close()


if __name__ == "__main__":
    gr = GraphRetriever()
    query_text = "朝鲜族农乐舞（象帽舞）"

    # 测试普通查询（仅节点检索）
    print("=====【普通查询，无query_type】=====")
    node_res = gr.retrieve(query_text, context=None)
    for item in node_res:
        print(item)

    # 模拟A传入context.query_type="relation"，触发一跳
    from .base_retriever import RetrievalRequest

    class MockContext:
        query_type = "relation"

    req_rel = RetrievalRequest(query=query_text, top_k=4, context=MockContext())
    print("\n=====【query_type=relation，触发节点+one‑hop】=====")
    rel_res = gr.retrieve(req_rel.query, context=req_rel.context)
    for item in rel_res:
        print(item)

    # 模拟完整自然语言问句测试
    print("\n=====【长自然语言问句 + query_type=relation】 =====")
    req_long = RetrievalRequest(
        query="朝鲜族农乐舞（象帽舞）和吉林省延边朝鲜族自治州有什么关系？",
        top_k=4,
        context=MockContext()
    )
    long_res = gr.retrieve(req_long.query, context=req_long.context)
    for item in long_res:
        print(item)

    gr.close()
