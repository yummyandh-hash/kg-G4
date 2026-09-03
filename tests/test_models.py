from orchestration.models import Evidence, RetrievalContext, Retriever


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

class MockVectorRetriever:
    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        return [
            Evidence(
                evidence_id="mock_001",
                content="苏绣是传统刺绣技艺。",
                retrieval_method="vector",
                score=0.9,
            )
        ]


def test_retriever_contract():
    retriever: Retriever = MockVectorRetriever()

    context = RetrievalContext(
        query_type="fact",
        complexity_score=0.2,
    )

    evidences = retriever.retrieve("什么是苏绣？", context)

    assert len(evidences) == 1
    assert evidences[0].retrieval_method == "vector"