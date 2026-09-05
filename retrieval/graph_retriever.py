from typing import List
from neo4j import GraphDatabase
import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from .base_retriever import BaseRetriever, RetrievalRequest, Evidence

# 定位到项目根目录，加载根目录下的.env
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class GraphRetriever(BaseRetriever):
    def __init__(self):
        """从本地.env读取Neo4j连接信息，禁止硬编码凭证"""
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        self.driver = None
        if not uri or not user or not password:
            print("[WARN] Neo4j环境变量缺失，graph检索降级返回空结果")
            return
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
            print("[INFO] Neo4j连接验证成功")
        except Exception as e:
            print(f"[WARN] Neo4j连接验证失败: {e}，graph检索降级返回空结果")
            self.driver = None

    def close(self):
        """关闭数据库连接"""
        if self.driver is not None:
            self.driver.close()

    def _inner_retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        """
        图检索内部实现，Cypher查询，匹配InheritProject非遗节点，组装标准Evidence
        """
        res: List[Evidence] = []
        if self.driver is None:
            return res
        cypher = """
MATCH (h:InheritProject)
WHERE h.name CONTAINS $query_text OR h.canonical_name CONTAINS $query_text
RETURN h.name AS project, h.attributes_json AS content, h.entity_id AS entity_id
LIMIT $top_k
"""
        t0 = time.time()
        try:
            with self.driver.session() as session:
                records = session.run(
                    cypher,
                    query_text=request.query,
                    top_k=request.top_k
                )
                for record in records:
                    raw_json_str = record["content"]
                    try:
                        attr_dict = json.loads(raw_json_str)
                    except (json.JSONDecodeError, TypeError):
                        attr_dict = {}

                    ev = Evidence(
                        evidence=str(attr_dict),
                        score=0.8,
                        path=None,
                        retriever="graph_retriever",
                        latency=time.time() - t0,
                        document_id=record["entity_id"],
                        chunk_id=f"graph_{record['entity_id']}",
                        source_url="",
                        source_name=record["project"],
                        source_category="",
                        source_region="",
                        source_org="",
                        retrieved_at=datetime.now().isoformat(),
                        source_batch="neo4j_graph"
                    )
                    res.append(ev)
        except Exception as e:
            print(f"[WARN] graph查询发生异常 {e}，返回空证据列表")
        return res

    def _one_hop_retrieve(self, entity_name: str, top_k: int = 3) -> List[Evidence]:
        """一跳邻域检索：从InheritProject向外查询直接关联节点，返回路径证据"""
        res: List[Evidence] = []
        if self.driver is None:
            return res
        cypher_hop = """
MATCH (h:InheritProject {name:$entity_name})-[r]-(neighbor)
RETURN h.name AS src, type(r) AS rel, labels(neighbor)[0] AS neighbor_label, neighbor.name AS neighbor_name
LIMIT $top_k
"""
        t0 = time.time()
        try:
            with self.driver.session() as session:
                records = session.run(cypher_hop, entity_name=entity_name, top_k=top_k)
                for rec in records:
                    path_text = f"{rec['src']} --[{rec['rel']}]--> {rec['neighbor_label']}:{rec['neighbor_name']}"
                    ev = Evidence(
                        evidence=path_text,
                        score=0.7,
                        path=[path_text],
                        retriever="graph_retriever_one_hop",
                        latency=time.time() - t0,
                        document_id="",
                        chunk_id="graph_hop",
                        source_url="",
                        source_name=rec["src"],
                        source_category="",
                        source_region="",
                        source_org="",
                        retrieved_at=datetime.now().isoformat(),
                        source_batch="neo4j_hop"
                    )
                    res.append(ev)
        except Exception as e:
            print(f"[WARN] one‑hop查询异常:{e}")
        return res


if __name__ == "__main__":
    gr = GraphRetriever()
    if gr.driver is not None:
        try:
            with gr.driver.session() as s:
                cnt_rec = s.run("MATCH (h:InheritProject) RETURN count(h) AS cnt").single()
                print(f"库中InheritProject节点总数：{cnt_rec['cnt']}")
            out = gr.retrieve(query="哭嫁歌", context=None)
            print("graph检索结果：")
            for item in out:
                print(item)
            # 简单测试一跳检索
            hop_out = gr._one_hop_retrieve(entity_name="朝鲜族农乐舞（象帽舞）", top_k=3)
            print("\none‑hop一跳检索结果：")
            for h in hop_out:
                print(h)
        except Exception as err:
            print(f"[WARN] 执行查询异常：{err}")
    else:
        print("[INFO] graph驱动未初始化，跳过数据库测试")
    gr.close()
