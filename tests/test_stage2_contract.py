from dataclasses import asdict

from fastapi.testclient import TestClient

from api.main import app
from orchestration.explainability import build_explanation
from orchestration.models import AnswerResponse, RouteDecision


def test_route_decision_confidence_defaults_to_none():
    decision = RouteDecision(
        query_type="fact",
        complexity_score=0.2,
        selected_route="vector",
        reason="simple factual query",
    )

    assert decision.confidence is None


def test_answer_response_exposes_optional_route_confidence():
    response = AnswerResponse(
        answer="ok",
        query_type="fact",
        complexity_score=0.2,
        selected_route="vector",
        route_reason="test",
        route_confidence=0.76,
    )

    assert asdict(response)["route_confidence"] == 0.76
    assert "citation_validation" in asdict(response)
    assert build_explanation(response)["route_confidence"] == 0.76


def test_query_api_keeps_route_confidence_field():
    client = TestClient(app)

    response = client.post(
        "/query",
        json={"question": "什么是蜀绣？"},
    )

    assert response.status_code == 200
    assert "route_confidence" in response.json()
    assert "citation_validation" in response.json()
