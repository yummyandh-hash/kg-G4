"""Isolated API contract tests without external services or credentials."""

import importlib

import pytest
from fastapi.testclient import TestClient

from orchestration.models import Evidence
from orchestration.retriever_adapters import AnalysisRouter
from orchestration.service import QueryService


class _Retriever:
    def retrieve(self, query, context):
        return [Evidence(
            evidence_id="api-test-evidence",
            content="蜀绣是中国传统刺绣的重要代表。",
            retrieval_method="vector",
            score=0.95,
            source_id="api-test-source",
            entity_ids=["蜀绣"],
        )]


class _Generator:
    def generate(self, question, context):
        return f"根据证据回答：{question}"


@pytest.fixture
def api_client(monkeypatch):
    import orchestration.stage1 as stage1

    service = QueryService(
        router=AnalysisRouter(), retriever=_Retriever(), generator=_Generator(),
    )
    monkeypatch.setattr(stage1, "build_stage1_query_service", lambda: service)
    api = importlib.import_module("api.main")
    monkeypatch.setattr(api, "query_service", service)
    with TestClient(api.app) as client:
        yield client
