from dataclasses import dataclass, field
from typing import List, Optional, Protocol


@dataclass
class RetrievalContext:
    """A 传给 Retriever 的检索上下文。"""

    query_type: str
    complexity_score: float
    top_k: int = 5


@dataclass
class Evidence:
    """Retriever 返回给 A 的一条检索证据。"""

    evidence_id: str
    content: str
    retrieval_method: str

    score: Optional[float] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None

    entity_ids: List[str] = field(default_factory=list)
    relation_path: List[str] = field(default_factory=list)

class Retriever(Protocol):
    """所有 Retriever 需要遵守的统一接口。"""

    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> List[Evidence]:
        ...