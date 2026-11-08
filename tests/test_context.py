from orchestration.context import build_context
from orchestration.models import Evidence


def test_build_context_with_evidence():
    evidences = [
        Evidence(
            evidence_id="e1",
            content="蜀绣主要流传于四川地区。",
            retrieval_method="graph",
            score=0.95,
            source_id="s1",
            source_url="https://www.ihchina.cn/",
            relation_path=[
                {
                    "source": "蜀绣",
                    "relation": "分布于",
                    "target": "四川",
                }
            ],
        )
    ]

    context = build_context("什么是蜀绣？", evidences)

    assert "什么是蜀绣？" in context
    assert "蜀绣主要流传于四川地区。" in context
    assert "graph" in context
    assert "蜀绣 --[分布于]--> 四川" in context


def test_build_context_without_evidence():
    context = build_context("什么是蜀绣？", [])

    assert "什么是蜀绣？" in context
    assert "No retrieval evidence available." in context
