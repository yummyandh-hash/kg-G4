import time
import os
from datetime import datetime
from typing import List
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv

from .base_retriever import BaseRetriever, RetrievalRequest, Evidence

load_dotenv()


class GraphRetriever(BaseRetriever):
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI")
        self.user = os.getenv("NEO4J_USER")
        self.password = os.getenv("NEO4J_PASSWORD")
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
        """基础节点文本检索，根据query匹配InheritProject节点名称"""
        evidences: List[Evidence] = []
        if self.driver is None:
            return evidences

        cypher = """
        MATCH (n:InheritProject)
        WHERE toLower(n.name) CONTAINS toLower($q_str)
        RETURN n.name as name, n.attributes_json as attr, n.entity_id as eid
        LIMIT $top_k
        """
        t0 = time.time()
        try:
            with self.driver.session() as session:
                records = session.run(cypher, q_str=request.query, top_k=request.top_k)
                for rec in records:
                    content = f"项目名称：{rec['name']}，属性信息：{rec['attr']}"
                    ev = Evidence(
                        evidence=content,
                        score=0.80,
                        path=[],
                        retriever="graph_retriever",
                        latency=time.time() - t0,
                        document_id=rec["eid"] or "",
                        chunk_id="graph_node",
                        source_url="",
                        source_name=rec["name"],
                        source_category="",
                        source_region="",
                        source_org="",
                        retrieved_at=datetime.now().isoformat(),
                        source_batch="neo4j_node"
                    )
                    evidences.append(ev)
        except Exception as e:
            print(f"[WARN] graph node retrieve error: {e}")
        return evidences

    def _one_hop_retrieve(self, entity_name: str, top_k: int = 4) -> List[Evidence]:
        """一跳关系检索"""
        res: List[Evidence] = []
        if self.driver is None:
            return res
        cypher_one_hop = """
        MATCH (h:InheritProject {name:$entity_name})-[r]-(neigh)
        RETURN h.name AS src, type(r) AS rel, neigh.name AS target
        LIMIT $top_k
        """
        t0 = time.time()
        try:
            with self.driver.session() as session:
                records = session.run(cypher_one_hop, entity_name=entity_name, top_k=top_k)
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
            print(f"[WARN] one‑hop查询异常:{e}")
        return res

    def _two_hop_retrieve(self, entity_name: str, top_k: int = 4) -> List[Evidence]:
        """两跳路径检索原型 Stage1，输出标准Evidence"""
        res: List[Evidence] = []
        if self.driver is None:
            return res
        cypher_two_hop = """
        MATCH (h:InheritProject {name:$entity_name})-[r1]-(mid)-[r2]-(neigh2)
        RETURN h.name AS src, type(r1) AS rel1, mid.name AS mid_node, type(r2) AS rel2, neigh2.name AS target_node
        LIMIT $top_k
        """
        t0 = time.time()
        try:
            with self.driver.session() as session:
                records = session.run(cypher_two_hop, entity_name=entity_name, top_k=top_k)
                for rec in records:
                    path_text = f"{rec['src']} --[{rec['rel1']}]--> {rec['mid_node']} --[{rec['rel2']}]--> {rec['target_node']}"
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
            print(f"[WARN] two‑hop查询异常:{e}")
        return res

    def close(self):
        if self.driver:
            self.driver.close()

if __name__ == "__main__":
    gr = GraphRetriever()
    query_text = "朝鲜族农乐舞（象帽舞）"
    # ✔对外API：retrieve(字符串query, context)，基类内部自己构造RetrievalRequest
    node_res = gr.retrieve(query_text, context=None)
    print("\n==== 节点检索结果 ====")
    for item in node_res:
        print(item)

    one_hop_out = gr._one_hop_retrieve(entity_name="朝鲜族农乐舞（象帽舞）", top_k=4)
    print("\n==== one‑hop一跳检索结果 ====")
    for item in one_hop_out:
        print(item)

    two_hop_out = gr._two_hop_retrieve(entity_name="朝鲜族农乐舞（象帽舞）", top_k=4)
    print("\n==== two‑hop两跳检索结果 ====")
    for item in two_hop_out:
        print(item)

    gr.close()
