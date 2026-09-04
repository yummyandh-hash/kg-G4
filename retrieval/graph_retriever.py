from typing import List
from neo4j import GraphDatabase

from .base_retriever import BaseRetriever, RetrievalRequest, Evidence


class GraphRetriever(BaseRetriever):
    def __init__(self, uri: str, user: str, password: str):
        """
        neo4j数据库连接
        等待C提供真实uri/user/password填入
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """关闭数据库连接"""
        if self.driver is not None:
            self.driver.close()

    def retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        """
        图检索接口，对外输入输出和VectorRetriever完全对齐
        TODO：拿到数据库数据后实现cypher查询逻辑
        当前mock返回空占位
        """
        # 后续在这里写cypher查询代码
        res: List[Evidence] = []
        return res


if __name__ == "__main__":
    # 示例占位，C给参数后替换
    uri = "bolt://xxx"
    user = "xxx"
    password = "xxx"
    gr = GraphRetriever(uri, user, password)
    req = RetrievalRequest(query="测试查询", top_k=3)
    out = gr.retrieve(req)
    print(out)
    gr.close()
