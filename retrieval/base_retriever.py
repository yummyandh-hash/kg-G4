from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class RetrievalContext:
    query_type: Optional[str] = None          # normal / relation / relation_2hop / None
    selected_route: Optional[str] = None     # vector / graph / hybrid / None，A模块路由控制


@dataclass
class RetrievalRequest:
    query: str
    top_k: int = 5
    context: Optional[RetrievalContext] = None


@dataclass
class Evidence:
    evidence: str
    score: float
    path: Optional[List]
    retriever: str
    latency: float
    document_id: str
    chunk_id: str                                 # 改为str，不再允许None；图谱证据赋值 ""
    source_url: str
    source_name: str
    source_category: str
    source_region: str
    source_org: str
    retrieved_at: str
    source_batch: str
    # ↓↓↓ 新增：供E前端图谱渲染 ↓↓↓
    entity_ids: Optional[List[str]] = None
    relation_path: Optional[List[Dict]] = None


class BaseRetriever(ABC):
    def retrieve(self, query: str, context: Optional[RetrievalContext] = None, top_k: int = 5) -> List[Evidence]:
        """对外统一接口：retrieve(query, context=None, top_k=5) -> List[Evidence]"""
        # 全局兜底：外部传None，自动构造空上下文，子类无需重复处理context判空
        if context is None:
            context = RetrievalContext()
        req = RetrievalRequest(query=query, context=context, top_k=top_k)
        return self._inner_retrieve(req)

    @abstractmethod
    def _inner_retrieve(self, request: RetrievalRequest) -> List[Evidence]:
        pass
