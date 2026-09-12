from dataclasses import asdict, is_dataclass
from time import perf_counter
from typing import Any, List, Optional, Protocol

from orchestration.models import (
    AnswerResponse,
    CitationValidation,
    Evidence,
    GraphEdge,
    GraphNode,
    RetrievalContext,
    RouteDecision,
)


class Router(Protocol):
    """统一的路由器接口，后续接入 A 模块。"""

    def route(self, query: str) -> RouteDecision:
        ...


class Retriever(Protocol):
    """统一的 Retriever 接口，后续接入 D 模块。"""

    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> List[Evidence]:
        ...


class AnswerGenerator(Protocol):
    """统一的答案生成接口，后续接入 LLM。"""

    def generate(
        self,
        query: str,
        evidences: List[Evidence],
    ) -> str:
        ...


class CitationVerifier(Protocol):
    """Optional citation verification service provided by Task 2."""

    def verify_claim(
        self,
        claim: str,
        chunk_ids: List[str],
    ):
        ...


class MockRouter:
    """Stage 1 临时路由器。

    A 模块正式接入后，可以直接替换为 A 的 Router 实现。
    """

    def route(self, query: str) -> RouteDecision:
        return RouteDecision(
            query_type="knowledge",
            complexity_score=0.3,
            selected_route="vector",
            reason="Stage 1 Mock Router：当前默认采用向量检索。",
        )


class MockRetriever:
    """Stage 1 临时 Retriever。

    D 模块正式接入后，可以直接替换为 VectorRetriever
    或 GraphRetriever。
    """

    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> List[Evidence]:
        return [
            Evidence(
                evidence_id="mock-evidence-001",
                content=(
                    "蜀绣是中国传统刺绣的重要代表之一，"
                    "主要流传于四川地区，具有鲜明的地域文化特色。"
                ),
                retrieval_method="vector",
                score=0.95,
                source_id="mock-source-001",
                source_url="https://www.ihchina.cn/",
                entity_ids=["蜀绣", "四川"],
                relation_path=[
                    {
                        "source": "蜀绣",
                        "relation": "分布于",
                        "target": "四川",
                    }
                ],
            )
        ]


class MockAnswerGenerator:
    """Stage 1 临时答案生成器。

    后续接入实际 LLM 后，只需要替换这个组件。
    """

    def generate(
        self,
        query: str,
        evidences: List[Evidence],
    ) -> str:
        if not evidences:
            return f"暂未检索到与“{query}”相关的有效证据。"

        return (
            f"根据检索到的非遗资料，"
            f"问题“{query}”可以结合检索证据进行回答。"
        )


class QueryService:
    """E 模块统一查询编排服务。

    负责串联：
        Router → Retriever → AnswerGenerator
    并将结果整理为统一 AnswerResponse。
    """

    def __init__(
        self,
        router: Optional[Router] = None,
        retriever: Optional[Retriever] = None,
        answer_generator: Optional[AnswerGenerator] = None,
        citation_service: Optional[CitationVerifier] = None,
        top_k: int = 5,
    ):
        self.router = router or MockRouter()
        self.retriever = retriever or MockRetriever()
        self.answer_generator = (
            answer_generator or MockAnswerGenerator()
        )
        self.citation_service = citation_service
        self.top_k = top_k

    def query(self, question: str) -> AnswerResponse:
        """执行一次完整查询。"""

        start = perf_counter()

        # 1. 路由判断
        route_start = perf_counter()
        decision = self.router.route(question)
        route_time = perf_counter() - route_start

        # 2. 构造检索上下文
        context = RetrievalContext(
            query_type=decision.query_type,
            complexity_score=decision.complexity_score,
            top_k=self.top_k,
            selected_route=decision.selected_route,
        )

        # 3. 检索
        retrieval_start = perf_counter()
        evidences = self.retriever.retrieve(
            question,
            context,
        )
        retrieval_time = perf_counter() - retrieval_start

        # 4. 答案生成
        answer_start = perf_counter()
        answer = self.answer_generator.generate(
            question,
            evidences,
        )
        answer_time = perf_counter() - answer_start

        citation_start = perf_counter()
        citation_validation = self._verify_citation(answer, evidences)
        citation_time = perf_counter() - citation_start

        # 5. 整理关系路径
        paths = [
            evidence.relation_path
            for evidence in evidences
            if evidence.relation_path
        ]

        # 6. 整理来源
        sources = list(dict.fromkeys(
            evidence.source_id or evidence.source_url
            for evidence in evidences
            if evidence.source_id or evidence.source_url
        ))

        # 7. 构造图谱节点
        node_map = {}

        for evidence in evidences:
            for entity_id in evidence.entity_ids:
                if entity_id not in node_map:
                    node_map[entity_id] = GraphNode(
                        node_id=entity_id,
                        label=entity_id,
                    )

            for entity_id in _path_entities(evidence.relation_path):
                if entity_id not in node_map:
                    node_map[entity_id] = GraphNode(
                        node_id=entity_id,
                        label=entity_id,
                    )

        graph_nodes = list(node_map.values())

        # 8. 构造图谱边
        edge_map = {}

        for path in paths:
            for source, relation, target in _path_edges(path):
                edge_key = (source, relation, target)

                if edge_key not in edge_map:
                    edge_map[edge_key] = GraphEdge(
                        source=source,
                        target=target,
                        relation=relation,
                    )

        graph_edges = list(edge_map.values())

        # 9. 总耗时
        total_time = perf_counter() - start

        return AnswerResponse(
            answer=answer,
            query_type=context.query_type,
            complexity_score=context.complexity_score,
            selected_route=decision.selected_route,
            route_reason=decision.reason,
            route_confidence=decision.confidence,
            citation_validation=citation_validation,
            evidences=evidences,
            paths=paths,
            sources=sources,
            timing={
                "routing": route_time,
                "retrieval": retrieval_time,
                "answer_generation": answer_time,
                "citation_verification": citation_time,
                "total": total_time,
            },
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
        )

    def _verify_citation(
        self,
        answer: str,
        evidences: List[Evidence],
    ) -> CitationValidation | None:
        if self.citation_service is None or not evidences:
            return None

        chunk_ids = _citation_chunk_ids(evidences)
        if not chunk_ids:
            return None

        result = self.citation_service.verify_claim(answer, chunk_ids)
        return _to_citation_validation(result)


def _path_entities(path) -> List[str]:
    if not path:
        return []

    if all(isinstance(item, dict) for item in path):
        entities = []
        for item in path:
            entities.extend(
                value
                for value in (item.get("source"), item.get("target"))
                if value
            )
        return list(dict.fromkeys(entities))

    if len(path) < 3:
        return []

    return [
        value
        for index, value in enumerate(path)
        if index % 2 == 0
    ]


def _path_edges(path) -> List[tuple[str, str, str]]:
    if not path:
        return []

    edges = []

    if all(isinstance(item, dict) for item in path):
        for item in path:
            source = item.get("source")
            relation = item.get("relation")
            target = item.get("target")
            if source and relation and target:
                edges.append((source, relation, target))
        return edges

    if len(path) < 3:
        return []

    for index in range(0, len(path) - 2, 2):
        source = path[index]
        relation = path[index + 1]
        target = path[index + 2]
        edges.append((source, relation, target))

    return edges


def _citation_chunk_ids(evidences: List[Evidence]) -> List[str]:
    ids = [
        evidence.source_id or evidence.evidence_id
        for evidence in evidences
        if evidence.source_id or evidence.evidence_id
    ]
    return list(dict.fromkeys(str(item) for item in ids if item))


def _to_citation_validation(result: Any) -> CitationValidation:
    if isinstance(result, CitationValidation):
        return result

    if is_dataclass(result):
        data = asdict(result)
    elif isinstance(result, dict):
        data = result
    else:
        data = {
            "label": getattr(result, "label"),
            "confidence": getattr(result, "confidence"),
            "reason": getattr(result, "reason"),
            "evidences": getattr(result, "evidences", []),
        }

    return CitationValidation(
        label=str(data["label"]),
        confidence=float(data["confidence"]),
        reason=str(data.get("reason", "")),
        evidences=list(data.get("evidences", [])),
    )
