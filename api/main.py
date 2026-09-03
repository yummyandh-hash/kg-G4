from dataclasses import asdict

from fastapi import FastAPI
from pydantic import BaseModel

from orchestration.models import AnswerResponse


app = FastAPI(
    title="AP-ICH-GraphRAG",
    description="非遗智谱：AP-ICH-GraphRAG API",
    version="0.1.0",
)


class QueryRequest(BaseModel):
    question: str


@app.get("/")
def root():
    """Health check."""
    return {
        "status": "ok",
        "service": "AP-ICH-GraphRAG",
        "version": "0.1.0",
    }


@app.post("/query")
def query(request: QueryRequest):
    """
    Stage 1 API skeleton.

    当前使用 Mock 数据验证 API 层与
    orchestration.AnswerResponse 的接口是否正常。
    后续接入 Adaptive Router、Retriever 和 LLM。
    """
    response = AnswerResponse(
        answer=f"这是对问题“{request.question}”的测试回答。",
        query_type="unknown",
        complexity_score=0.0,
        selected_route="mock",
        route_reason="E-01 API skeleton mock",
        evidences=[],
        paths=[],
        sources=[],
        timing={},
    )

    return asdict(response)