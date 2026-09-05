from typing import List
from neo4j import GraphDatabase
import os
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

        if not uri or not user or not password:
            raise RuntimeError("请检查项目根目录的.env文件，Neo4j连接参数不能为空")

        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """关闭数据库连接"""
        if self.driver is not None:
            self.driver.close()

    def _inner_retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        """
        图检索内部实现，子类实现的抽象方法
        TODO：补充Cypher查询逻辑，把查询结果组装为Evidence
        当前mock返回空占位
        """
        res: List[Evidence] = []
        # cypher = """MATCH ... WHERE ... RETURN ... LIMIT $top_k"""
        # with self.driver.session() as session:
        #     records = session.run(cypher, q=request.query, top_k=request.top_k)
        # 遍历records构造Evidence加入res
        return res


if __name__ == "__main__":
    gr = GraphRetriever()
    out = gr.retrieve(query="测试查询", context=None)
    print(out)
    gr.close()
