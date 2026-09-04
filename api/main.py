from dataclasses import asdict

from fastapi import FastAPI
from pydantic import BaseModel

from orchestration.service import QueryService


app = FastAPI(
    title="AP-ICH-GraphRAG",
    description="非遗智谱：AP-ICH-GraphRAG API",
    version="0.2.0",
)


class QueryRequest(BaseModel):
    question: str


query_service = QueryService()


@app.get("/")
def root():
    """Health check."""
    return {
        "status": "ok",
        "service": "AP-ICH-GraphRAG",
        "version": "0.2.0",
    }


@app.post("/query")
def query(request: QueryRequest):
    """执行一次知识图谱问答查询。"""
    response = query_service.query(request.question)
    return asdict(response)