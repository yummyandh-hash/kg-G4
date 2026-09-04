from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RetrievalRequest:
    query: str
    top_k: int = 5


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
    @abstractmethod
    def retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        pass
