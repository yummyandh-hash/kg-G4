from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol


@dataclass
class RetrievalContext:
    """A 传给 Retriever 的检索上下文。"""

    query_type: str
    complexity_score: float
    top_k: int = 5
    selected_route: Optional[str] = None


@dataclass
class Evidence:
    """Retriever 返回的一条检索证据。"""

    evidence_id: str
    content: str
    retrieval_method: str

    score: Optional[float] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None

    entity_ids: List[str] = field(default_factory=list)
    relation_path: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class GraphNode:
    """知识图谱节点。"""

    node_id: str
    label: str
    properties: Dict[str, object] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """知识图谱关系。"""

    source: str
    target: str
    relation: str
    properties: Dict[str, object] = field(default_factory=dict)


@dataclass
class Source:
    """原始证据来源。"""

    source_id: str
    title: str
    url: str
    content: str


@dataclass
class RouteDecision:
    """Adaptive Router 输出的路由决策结果。"""

    query_type: str
    complexity_score: float
    selected_route: str
    reason: str
    confidence: Optional[float] = None


@dataclass
class CitationValidation:
    """Result returned by the optional citation verification service."""

    label: str
    confidence: float
    reason: str
    evidences: List[Dict[str, object]] = field(default_factory=list)


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
    route_confidence: Optional[float] = None
    citation_validation: Optional[CitationValidation] = None

    evidences: List[Evidence] = field(default_factory=list)
    paths: List[List[Dict[str, str]]] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    timing: Dict[str, float] = field(default_factory=dict)

    # Stage 1 可解释性信息
    graph_nodes: List[GraphNode] = field(default_factory=list)
    graph_edges: List[GraphEdge] = field(default_factory=list)
