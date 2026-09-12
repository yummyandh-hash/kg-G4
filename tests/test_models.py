from orchestration.models import (
    AnswerResponse,
    CitationValidation,
    Evidence,
    RetrievalContext,
    Retriever,
    RouteDecision,
    Document,
)

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

def test_route_decision():
    decision = RouteDecision(
        query_type="fact",
        complexity_score=0.2,
        selected_route="vector",
        reason="simple factual query",
    )

    assert decision.query_type == "fact"
    assert decision.complexity_score == 0.2
    assert decision.selected_route == "vector"
    assert decision.reason == "simple factual query"

def test_answer_response_defaults():
    response = AnswerResponse(
        answer="苏绣是中国传统刺绣技艺之一。",
        query_type="fact",
        complexity_score=0.2,
        selected_route="vector",
        route_reason="simple factual query",
    )

    assert response.answer == "苏绣是中国传统刺绣技艺之一。"
    assert response.selected_route == "vector"
    assert response.evidences == []
    assert response.paths == []
    assert response.sources == []
    assert response.timing == {}
    assert response.citation_validation is None

def test_citation_validation_model():
    validation = CitationValidation(
        label="SUPPORTED",
        confidence=0.91,
        reason="claim is supported by cited chunks",
        evidences=[{"chunk_id": "chunk-1"}],
    )

    assert validation.label == "SUPPORTED"
    assert validation.confidence == 0.91
    assert validation.evidences == [{"chunk_id": "chunk-1"}]

def test_document():
    document = Document(
        document_id="doc_001",
        title="苏绣",
        content="苏绣是中国传统刺绣技艺之一。",
        source_url="https://www.ihchina.cn/example",
    )

    assert document.document_id == "doc_001"
    assert document.title == "苏绣"
    assert document.source_url == "https://www.ihchina.cn/example"
