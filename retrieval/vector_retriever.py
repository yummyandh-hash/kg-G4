import time
import json
import os
from datetime import datetime
from typing import List
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from .base_retriever import BaseRetriever, RetrievalRequest, Evidence


class VectorRetriever(BaseRetriever):
    def __init__(self, index_path: str = "data/vector.index", chunk_jsonl_path: str = "data/chunks/chunks.jsonl"):
        self.index_path = index_path
        self.chunk_jsonl_path = chunk_jsonl_path
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.index: faiss.Index | None = None
        self.chunks: list[dict] = []
        self._load_index_and_chunks()

    def _preprocess_query(self, q: str) -> str:
        """剥离中文常见疑问后缀，仅用于送入embedding，不修改原始request.query"""
        suffixes = ["是什么？", "是什么", "？", "介绍一下", "简述", "请介绍", "请问"]
        out = q.strip()
        for s in suffixes:
            if out.endswith(s):
                out = out[:-len(s)].strip()
        return out

    def _load_index_and_chunks(self):
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
        else:
            raise FileNotFoundError(f"faiss索引不存在：{self.index_path}，请先执行建索引")

        self.chunks = []
        with open(self.chunk_jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                self.chunks.append(json.loads(line))

    def _inner_retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        evidences: List[Evidence] = []
        if self.index is None or len(self.chunks) == 0:
            return evidences

        t0 = time.time()
        # 使用预处理后的文本做embedding，原始request.query保持不变
        proc_q = self._preprocess_query(request.query)
        query_embedding = self.model.encode(proc_q, convert_to_numpy=True)
        query_embedding = np.expand_dims(query_embedding, axis=0).astype(np.float32)

        scores, indices = self.index.search(query_embedding, k=request.top_k)
        scores = scores[0]
        indices = indices[0]

        for score, idx in zip(scores, indices):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]
            ev = Evidence(
                evidence=chunk.get("content", ""),
                score=float(score),
                path=[],
                retriever="vector_retriever",
                latency=time.time() - t0,
                document_id=chunk.get("chunk_id", ""),
                chunk_id=chunk.get("chunk_id", ""),
                source_url=chunk.get("source_url", ""),
                source_name=chunk.get("source_name", ""),
                source_category="",
                source_region="",
                source_org="",
                retrieved_at=datetime.now().isoformat(),
                source_batch="vector_chunk"
            )
            evidences.append(ev)
        return evidences


if __name__ == "__main__":
    vr = VectorRetriever()

    # 测试1：实体短名称
    print("=====【测试1：实体短名称】=====")
    from .base_retriever import RetrievalRequest
    req1 = RetrievalRequest(query="朝鲜族农乐舞（象帽舞）", top_k=5, context=None)
    res1 = vr.retrieve(req1.query, context=req1.context)
    for item in res1:
        print(f"score={item.score:.4f} | {item.evidence[:100]}")

    # 测试2：带中文问句后缀（本次重点验证）
    print("\n=====【测试2：带问句后缀：朝鲜族农乐舞（象帽舞）是什么？】=====")
    req2 = RetrievalRequest(query="朝鲜族农乐舞（象帽舞）是什么？", top_k=5, context=None)
    res2 = vr.retrieve(req2.query, context=req2.context)
    for item in res2:
        print(f"score={item.score:.4f} | {item.evidence[:100]}")
