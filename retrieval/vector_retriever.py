import time
import json
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer

from .base_retriever import BaseRetriever, RetrievalRequest, Evidence


class VectorRetriever(BaseRetriever):
    def __init__(self, chunks_file: str = "data/chunks/chunks.jsonl"):
        self.chunks_file = chunks_file
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.chunks = []
        self.embeddings = None
        self._load_chunks()
        self._build_index()

    def _load_chunks(self):
        with open(self.chunks_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                self.chunks.append(json.loads(line))

    def _build_index(self):
        texts = [item["content"] for item in self.chunks]
        self.embeddings = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=True)

    def retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        t0 = time.time()
        q_emb = self.model.encode(request.query, normalize_embeddings=True)
        scores = np.dot(self.embeddings, q_emb)
        top_idx = np.argsort(scores)[::-1][:request.top_k]
        latency = time.time() - t0

        res = []
        for idx in top_idx:
            item = self.chunks[idx]
            res.append(Evidence(
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
                source_batch=item["source_batch"]
            ))
        return res


if __name__ == "__main__":
    retriever = VectorRetriever()
    req = RetrievalRequest(query="苏绣 传承人", top_k=3)
    out = retriever.retrieve(req)
    print(f"共返回 {len(out)} 条结果\n")
    for i, ev in enumerate(out):
        print(f"---第{i+1}条 分数:{ev.score:.4f}---")
        print(f"文本:{ev.evidence[:80]}...")
        print(f"项目:{ev.source_name} | 地区:{ev.source_region}")
        print(f"来源:{ev.source_url}\n")
