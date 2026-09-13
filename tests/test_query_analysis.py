import pytest

from orchestration.complexity_scorer import ComplexityScorer
from orchestration.query_analyzer import QueryAnalyzer


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("苏绣是什么？", "fact"),
        ("苏绣和苏州有什么关系？", "relation"),
        ("苏绣和南京云锦有什么不同？", "comparison"),
        ("江苏有哪些属于传统美术类的非遗？", "constraint"),
    ],
)
def test_query_types(query, expected):
    analyzer = QueryAnalyzer()
    assert analyzer.analyze(query) == expected


def test_complexity_order():
    scorer = ComplexityScorer()

    simple = scorer.score("苏绣是什么？")
    complex_query = scorer.score(
        "苏绣和南京云锦有什么不同，它们之间的传承方式如何关联？"
    )

    assert 0.0 <= simple <= 1.0
    assert 0.0 <= complex_query <= 1.0
    assert complex_query > simple