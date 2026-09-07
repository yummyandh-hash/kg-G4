import time
import re
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from .base_retriever import BaseRetriever, RetrievalRequest, Evidence


class VectorRetriever(BaseRetriever):
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.chunks: List[dict] = []

    def _preprocess_query(self, q: str) -> str:
        """剥离中文常见疑问后缀，仅用于embedding输入，原始request.query保持不变"""
        suffixes = ["是什么？", "是什么", "？", "介绍一下", "简述", "请介绍", "请问"]
        out = q.strip()
        for s in suffixes:
            if out.endswith(s):
                out = out[:-len(s)].strip()
        return out

    def retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        t0 = time.time()
        proc_q = self._preprocess_query(request.query)
        top_k = request.top_k

        if not self.chunks:
            return []

        q_emb = self.model.encode(proc_q, convert_to_numpy=True)
        score_list = []
        for chunk in self.chunks:
            emb = chunk["embedding"]
            sim = float(np.dot(q_emb, emb))
            score_list.append((sim, chunk))

        score_list.sort(key=lambda x: x[0], reverse=True)
        select = score_list[:top_k]

        evidences: List[Evidence] = []
        for score, chunk in select:
            ev = Evidence(
                evidence=chunk.get("content", ""),
                score=score,
                path=None,
                retriever="vector_retriever",
                latency=time.time() - t0,
                document_id=chunk.get("document_id", ""),
                chunk_id=chunk.get("chunk_id", ""),
                source_url=chunk.get("source_url", ""),
                source_name=chunk.get("source_name", ""),
                source_category=chunk.get("source_category", ""),
                source_region=chunk.get("source_region", ""),
                source_org=chunk.get("source_org", ""),
                retrieved_at=str(time.time()),
                source_batch=chunk.get("source_batch", "")
            )
            evidences.append(ev)
        return evidences


if __name__ == "__main__":
    vr = VectorRetriever()
    from .base_retriever import RetrievalRequest
    print("=====【测试预处理逻辑】=====")
    test_q1 = "朝鲜族农乐舞（象帽舞）"
    test_q2 = "朝鲜族农乐舞（象帽舞）是什么？"
    print(f"原始：{test_q2} -> 处理后：{vr._preprocess_query(test_q2)}")
    req = RetrievalRequest(query=test_q2, top_k=5)
    res = vr.retrieve(req)
    print(f"证据返回数量 {len(res)}")
