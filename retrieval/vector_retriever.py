import json
import time
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from .base_retriever import BaseRetriever, Evidence, RetrievalRequest, RetrievalContext


class VectorRetriever(BaseRetriever):
    def __init__(self, chunks_file: str = "data/chunks/chunks.jsonl"):
        self.chunks_file = chunks_file
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.chunks = []
        self.embeddings = None
        self._load_chunks()
        self._build_index()

    def _load_chunks(self):
        with open(self.chunks_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                self.chunks.append(json.loads(line))

    def _build_index(self):
        texts = [item["content"] for item in self.chunks]
        self.embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=True,
        )

    def _preprocess_query(self, query: str) -> str:
        """裁剪常见中文疑问后缀，仅用于生成查询向量。"""
        suffixes = (
            "是什么？",
            "是什么?",
            "是什么",
            "介绍一下",
            "简单介绍",
            "请介绍",
            "请问",
        )
        processed = query.strip()
        for suffix in suffixes:
            if processed.endswith(suffix):
                processed = processed[:-len(suffix)].strip()
                break
        return processed or query.strip()

    def _inner_retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        t0 = time.time()
        processed_query = self._preprocess_query(request.query)
        q_emb = self.model.encode(
            processed_query,
            normalize_embeddings=True,
        )
        scores = np.dot(self.embeddings, q_emb)
        top_idx = np.argsort(scores)[::-1][: request.top_k]
        latency = time.time() - t0
        res = []
        for idx in top_idx:
            item = self.chunks[idx]
            res.append(
                Evidence(
                    evidence=item["content"],
                    score=float(scores[idx]),
                    path=None,
                    retriever="vector",
                    latency=latency,
                    document_id=item["document_id"],
                    chunk_id=item["chunk_id"],
                    source_url=item["source_url"],
                    source_name=item["source_name"],
                    source_category=item["source_category"],
                    source_region=item["source_region"],
                    source_org=item["source_org"],
                    retrieved_at=item["retrieved_at"],
                    source_batch=item["source_batch"],
                    # =========新增：向量检索无图谱节点，赋值None=========
                    entity_ids=None,
                    relation_path=None
                )
            )
        return res


if __name__ == "__main__":
    retriever = VectorRetriever()
    query = "朝鲜族农乐舞（象帽舞）是什么？"
    print(f"原始查询：{query}")
    print(f"预处理后：{retriever._preprocess_query(query)}\n")
    out = retriever.retrieve(
        query=query,
        context=None,
        top_k=5,
    )
    print(f"共返回 {len(out)} 条结果\n")
    for i, ev in enumerate(out):
        print(f"--- 第 {i + 1} 条 分数: {ev.score:.4f} ---")
        print(f"文本: {ev.evidence[:200]}")
        print(f"项目: {ev.source_name} | 地区: {ev.source_region}")
        print(f"来源: {ev.source_url}\n")
