import time
import os
from datetime import datetime
from typing import List, Dict
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv
from .base_retriever import BaseRetriever, RetrievalRequest, Evidence, RetrievalContext

# 定位到项目根目录，加载根目录下的.env
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class GraphRetriever(BaseRetriever):
    def __init__(self):
        """从项目根目录.env读取Neo4j连接信息，禁止硬编码凭证
        兼容环境变量 NEO4J_USERNAME(A侧) / NEO4J_USER(D侧)
        """
        self.uri = os.getenv("NEO4J_URI")
        self.user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
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
        node_evidences: List[Evidence] = []
        relation_evidences: List[Evidence] = []

        if self.driver is None:
            return []

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
                    chunk_id=None,
                    source_url="",
                    source_name=name,
                    source_category="",
                    source_region="",
                    source_org="",
                    retrieved_at=datetime.now().isoformat(),
                    source_batch="neo4j_node",
                    # 节点证据，entity_ids填当前节点id，relation_path为空
                    entity_ids=[eid] if eid else None,
                    relation_path=None
                )
                node_evidences.append(ev)
                node_hit_entities.append(name)
        except Exception as e:
            print(f"[WARN] graph node retrieve error: {e}")

        # 2. 决定是否追加一跳/两跳关系证据（兜底逻辑：如果不传 query_type 默认开启 relation）
        query_type = "relation"
        if request.context is not None and request.context.query_type:
            query_type = request.context.query_type

        # 只要命中了节点，默认均去查询关系，确保前端拿到 relation_path 绘制关系边
        if len(node_hit_entities) > 0:
            entity = node_hit_entities[0]  # 取排序后最长匹配实体做关系查询
            hop1_list = self._one_hop_retrieve(entity, top_k=request.top_k)
            relation_evidences.extend(hop1_list)
            # 如果显式指定了 relation_2hop，追加 two‑hop
            if query_type == "relation_2hop":
                hop2_list = self._two_hop_retrieve(entity, top_k=request.top_k)
                relation_evidences.extend(hop2_list)

        # 3. 结果融合与截断策略：优先保留关系边（带有 relation_path 的证据），后面补齐节点证据
        final_evidences = relation_evidences + node_evidences
        return final_evidences[:request.top_k]

    def _one_hop_retrieve(self, entity_name: str, top_k: int = 4) -> List[Evidence]:
        res: List[Evidence] = []
        if self.driver is None:
            return res

        cypher_onehop = """
        MATCH (h:InheritProject {name:$entity_name})-[r]-(neigh)
        RETURN h.name AS src, type(r) AS rel, neigh.name AS target, h.entity_id AS src_eid, neigh.entity_id AS target_eid
        LIMIT $top_k
        """
        t0 = time.time()
        try:
            with self.driver.session() as session:
                records = session.run(cypher_onehop, entity_name=entity_name, top_k=top_k)
                for rec in records:
                    src = rec["src"]
                    rel_type = rec["rel"]
                    target = rec["target"]
                    src_eid = rec["src_eid"]
                    target_eid = rec["target_eid"]
                    path_text = f"{src} --[{rel_type}]--> {target}"
                    # 构造图谱渲染字段
                    entity_ids = [src_eid, target_eid]
                    relation_path: List[Dict] = [
                        {
                            "source": src_eid,
                            "target": target_eid,
                            "relation": rel_type
                        }
                    ]
                    ev = Evidence(
                        evidence=path_text,
                        score=0.70,
                        path=[path_text],
                        retriever="graph_retriever_one_hop",
                        latency=time.time() - t0,
                        document_id="",
                        chunk_id=None,
                        source_url="",
                        source_name=src,
                        source_category="",
                        source_region="",
                        source_org="",
                        retrieved_at=datetime.now().isoformat(),
                        source_batch="neo4j_1hop",
                        entity_ids=entity_ids,
                        relation_path=relation_path
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
        RETURN h.name AS src, type(r1) AS rel1, mid.name AS mid_node, type(r2) AS rel2, neigh2.name AS target,
               h.entity_id AS src_eid, mid.entity_id AS mid_eid, neigh2.entity_id AS target_eid
        LIMIT $top_k
        """
        t0 = time.time()
        try:
            with self.driver.session() as session:
                records = session.run(cypher_twohop, entity_name=entity_name, top_k=top_k)
                for rec in records:
                    src = rec["src"]
                    rel1 = rec["rel1"]
                    mid_node = rec["mid_node"]
                    rel2 = rec["rel2"]
                    target = rec["target"]
                    src_eid = rec["src_eid"]
                    mid_eid = rec["mid_eid"]
                    target_eid = rec["target_eid"]
                    path_text = f"{src} --[{rel1}]--> {mid_node} --[{rel2}]--> {target}"
                    # 两跳：三个节点id，两条关系
                    entity_ids = [src_eid, mid_eid, target_eid]
                    relation_path: List[Dict] = [
                        {"source": src_eid, "target": mid_eid, "relation": rel1},
                        {"source": mid_eid, "target": target_eid, "relation": rel2}
                    ]
                    ev = Evidence(
                        evidence=path_text,
                        score=0.60,
                        path=[path_text],
                        retriever="graph_retriever_two_hop",
                        latency=time.time() - t0,
                        document_id="",
                        chunk_id=None,
                        source_url="",
                        source_name=src,
                        source_category="",
                        source_region="",
                        source_org="",
                        retrieved_at=datetime.now().isoformat(),
                        source_batch="neo4j_2hop",
                        entity_ids=entity_ids,
                        relation_path=relation_path
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
    # 测试 1：带 context (query_type="relation")
    ctx_long = RetrievalContext(query_type="relation")
    long_res = gr.retrieve(
        query="朝鲜族农乐舞（象帽舞）和吉林省延边朝鲜族自治州有什么关系？",
        context=ctx_long,
        top_k=4
    )
    print("=== 测试 1：带 context 的返回结果 ===")
    for item in long_res:
        print("retriever:", item.retriever)
        print("entity_ids:", item.entity_ids)
        print("relation_path:", item.relation_path)
        print("-" * 50)

    # 测试 2：不带 context (context=None)，验证兜底覆盖效果
    print("\n=== 测试 2：context=None 兜底测试 ===")
    none_ctx_res = gr.retrieve(
        query="朝鲜族农乐舞",
        context=None,
        top_k=4
    )
    for item in none_ctx_res:
        print("retriever:", item.retriever)
        print("entity_ids:", item.entity_ids)
        print("relation_path:", item.relation_path)
        print("-" * 50)
    gr.close()
