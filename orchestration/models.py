from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol


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


@dataclass
class RouteDecision:
    """Adaptive Router 输出的路由决策结果。"""

    query_type: str
    complexity_score: float
    selected_route: str
    reason: str

@dataclass
class Document:
    """清洗后的统一文档结构。"""

    document_id: str
    title: str
    content: str
    source_url: str

class Retriever(Protocol):
    """所有 Retriever 需要遵守的统一接口。"""

    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> List[Evidence]:
        ...


@dataclass
class AnswerResponse:
    """A 最终返回给 Web/API 层的问答结果。"""

    answer: str
    query_type: str
    complexity_score: float
    selected_route: str
    route_reason: str

    evidences: List[Evidence] = field(default_factory=list)
    paths: List[List[str]] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    timing: Dict[str, float] = field(default_factory=dict)