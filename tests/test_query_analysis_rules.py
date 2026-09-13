from orchestration.complexity_scorer import ComplexityScorer
from orchestration.query_analyzer import QueryAnalyzer


def test_summary_query_is_treated_as_constraint():
    assert QueryAnalyzer().analyze(
        "根据正文概括项目的主要内容和社会功能。"
    ) == "constraint"


def test_summary_query_gets_higher_complexity():
    score = ComplexityScorer().score(
        "根据正文概括项目的主要内容、社会功能和传承方式。"
    )

    assert score >= 0.45


def test_relation_query_still_routes_as_relation():
    assert QueryAnalyzer().analyze("甲和乙是什么关系？") == "relation"
