from dataclasses import dataclass

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
