from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RetrievalRequest:
    query: str
    top_k: int = 5
    context: Optional[str] = None  # 新增context字段，对齐A的入参


@dataclass
class Evidence:
    evidence: str
    score: float
    path: Optional[List]
    retriever: str
    latency: float
    document_id: str
    chunk_id: str
    source_url: str
    source_name: str
    source_category: str
    source_region: str
    source_org: str
    retrieved_at: str
    source_batch: str


class BaseRetriever(ABC):
    def retrieve(self, query: str, context: Optional[str] = None) -> List[Evidence]:
        """对外统一接口：retrieve(query, context) -> List[Evidence]"""
        req = RetrievalRequest(query=query, context=context)
        return self._inner_retrieve(req)

    @abstractmethod
    def _inner_retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        pass
