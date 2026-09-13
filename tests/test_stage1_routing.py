from dataclasses import dataclass
import pytest

from orchestration.models import RetrievalContext
from orchestration.query_analyzer import QueryAnalyzer
from orchestration.retriever_adapters import (
    AnalysisRouter,
    DRetrieverAdapter,
    RouteDispatchRetriever,
)
from orchestration.service import QueryService


def test_relation_query_routes_to_graph_and_keeps_query_type():
    decision = AnalysisRouter().route(
        "朝鲜族农乐舞（象帽舞）和吉林省延边朝鲜族自治州有什么关系？"
    )

    assert decision.query_type == "relation"
    assert decision.selected_route == "graph"


def test_shi_relation_query_routes_to_graph():
    decision = AnalysisRouter().route(
        "朝鲜族农乐舞（象帽舞）和吉林省延边朝鲜族自治州是什么关系？"
    )

    assert decision.query_type == "relation"
    assert decision.selected_route == "graph"


@dataclass
class DOneHopEvidence:
    evidence: str
    score: float
    path: list[str]
    retriever: str
    document_id: str
    chunk_id: str
    source_url: str
    source_name: str
    entity_ids: list[str] | None = None
    relation_path: list[dict[str, str]] | None = None


class DOneHopRetriever:
    def __init__(self, use_relation_path=False):
        self.last_context = None
        self.use_relation_path = use_relation_path

    def retrieve(self, query, context=None, top_k=5):
        self.last_context = context
        relation_path = None
        if self.use_relation_path:
            relation_path = [
                {
                    "source": "朝鲜族农乐舞（象帽舞）",
                    "relation": "申报地区",
                    "target": "吉林省延边朝鲜族自治州",
                }
            ]

        return [
            DOneHopEvidence(
                evidence=(
                    "朝鲜族农乐舞（象帽舞） --[申报地区]--> "
                    "吉林省延边朝鲜族自治州"
                ),
                score=0.70,
                path=[
                    (
                        "朝鲜族农乐舞（象帽舞） --[申报地区]--> "
                        "吉林省延边朝鲜族自治州"
                    )
                ],
                retriever="graph_retriever_one_hop",
                document_id="",
                chunk_id="graph_one_hop",
                source_url="",
                source_name="朝鲜族农乐舞（象帽舞）",
                entity_ids=None,
                relation_path=relation_path,
            )
        ]


class RawListRetriever:
    def __init__(self, rows):
        self.rows = rows

    def retrieve(self, query, context=None, top_k=5):
        return self.rows[:top_k]


def test_d_adapter_passes_relation_context_and_normalizes_one_hop_path():
    d_retriever = DOneHopRetriever()
    adapter = DRetrieverAdapter(d_retriever, retrieval_method="graph")
    context = RetrievalContext(
        query_type="relation",
        complexity_score=0.35,
        top_k=5,
        selected_route="graph",
    )

    evidences = adapter.retrieve("关系查询", context)

    assert d_retriever.last_context.query_type == "relation"
    assert evidences[0].retrieval_method == "graph_retriever_one_hop"
    assert evidences[0].relation_path == [
        {
            "source": "朝鲜族农乐舞（象帽舞）",
            "relation": "申报地区",
            "target": "吉林省延边朝鲜族自治州",
        }
    ]


def test_d_adapter_keeps_d_relation_path_dict_array():
    d_retriever = DOneHopRetriever(use_relation_path=True)
    adapter = DRetrieverAdapter(d_retriever, retrieval_method="graph")
    context = RetrievalContext(
        query_type="relation",
        complexity_score=0.35,
        top_k=5,
        selected_route="graph",
    )

    evidences = adapter.retrieve("关系查询", context)

    assert evidences[0].relation_path == [
        {
            "source": "朝鲜族农乐舞（象帽舞）",
            "relation": "申报地区",
            "target": "吉林省延边朝鲜族自治州",
        }
    ]
    assert evidences[0].entity_ids == [
        "朝鲜族农乐舞（象帽舞）",
        "吉林省延边朝鲜族自治州",
    ]


def test_d_adapter_uses_chunk_id_as_source_id_not_document_id():
    adapter = DRetrieverAdapter(
        RawListRetriever([
            {
                "content": "chunk content",
                "score": 0.8,
                "chunk_id": "ihchina_0098187ad030_content_3",
                "document_id": "ihchina_0098187ad030",
                "source_name": "source title",
            }
        ]),
        retrieval_method="vector",
    )
    context = RetrievalContext(
        query_type="fact",
        complexity_score=0.2,
        top_k=5,
        selected_route="vector",
    )

    evidences = adapter.retrieve("query", context)

    assert evidences[0].source_id == "ihchina_0098187ad030_content_3"
    assert evidences[0].evidence_id == "ihchina_0098187ad030_content_3"


def test_d_adapter_does_not_use_document_id_as_source_id():
    adapter = DRetrieverAdapter(
        RawListRetriever([
            {
                "content": "graph node evidence",
                "score": 0.7,
                "document_id": "ihchina_0098187ad030",
                "source_name": "source title",
            }
        ]),
        retrieval_method="graph",
    )
    context = RetrievalContext(
        query_type="relation",
        complexity_score=0.35,
        top_k=5,
        selected_route="graph",
    )

    evidences = adapter.retrieve("query", context)

    assert evidences[0].source_id is None
    assert evidences[0].evidence_id == "graph-001"


def test_query_service_builds_graph_edges_from_d_one_hop_path():
    d_retriever = DOneHopRetriever(use_relation_path=True)
    graph_adapter = DRetrieverAdapter(d_retriever, retrieval_method="graph")
    service = QueryService(
        router=AnalysisRouter(),
        retriever=RouteDispatchRetriever({"graph": graph_adapter}),
    )

    response = service.query(
        "朝鲜族农乐舞（象帽舞）和吉林省延边朝鲜族自治州有什么关系？"
    )

    assert response.query_type == "relation"
    assert response.selected_route == "graph"
    assert len(response.graph_edges) == 1

    edge = response.graph_edges[0]
    assert edge.source == "朝鲜族农乐舞（象帽舞）"
    assert edge.relation == "申报地区"
    assert edge.target == "吉林省延边朝鲜族自治州"


@pytest.mark.parametrize("hops", [1, 2])
def test_d_structured_relation_path_produces_graph_edges(hops):
    edges = [
        {"source": "project-1", "relation": "申报地区", "target": "region-1"},
        {"source": "region-1", "relation": "位于", "target": "province-1"},
    ][:hops]

    class StructuredRetriever:
        def retrieve(self, query, context=None, top_k=5):
            return [{
                "evidence": "关系证据",
                "entity_ids": ["project-1", "region-1", "province-1"][:hops + 1],
                "relation_path": edges,
            }]

    service = QueryService(
        router=AnalysisRouter(),
        retriever=RouteDispatchRetriever({
            "graph": DRetrieverAdapter(StructuredRetriever(), "graph"),
        }),
    )
    response = service.query("项目与地区有什么关系？")
    assert [(edge.source, edge.relation, edge.target) for edge in response.graph_edges] == [
        (edge["source"], edge["relation"], edge["target"]) for edge in edges
    ]
def test_query_service_routes_shi_relation_query_to_graph():
    d_retriever = DOneHopRetriever(use_relation_path=True)
    graph_adapter = DRetrieverAdapter(d_retriever, retrieval_method="graph")
    service = QueryService(
        router=AnalysisRouter(),
        retriever=RouteDispatchRetriever({"graph": graph_adapter}),
    )

    response = service.query(
        "朝鲜族农乐舞（象帽舞）和吉林省延边朝鲜族自治州是什么关系？"
    )

    assert response.query_type == "relation"
    assert response.selected_route == "graph"
    assert len(response.graph_edges) == 1


def test_query_analyzer_relation_cue_smoke():
    assert QueryAnalyzer().analyze("甲和乙有什么关系？") == "relation"
