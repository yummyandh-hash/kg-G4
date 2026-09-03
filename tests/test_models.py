from orchestration.models import Evidence, RetrievalContext


def test_retrieval_context_defaults():
    context = RetrievalContext(
        query_type="fact",
        complexity_score=0.2,
    )

    assert context.query_type == "fact"
    assert context.complexity_score == 0.2
    assert context.top_k == 5


def test_evidence_defaults():
    evidence = Evidence(
        evidence_id="ev_001",
        content="苏绣是传统刺绣技艺。",
        retrieval_method="vector",
    )

    assert evidence.score is None
    assert evidence.source_url is None
    assert evidence.entity_ids == []
    assert evidence.relation_path == []