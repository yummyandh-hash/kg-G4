from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_root():
    response = client.get("/")

    assert response.status_code == 200
    assert "AP-ICH-GraphRAG" in response.text


def test_query():
    response = client.post(
        "/query",
        json={"question": "什么是蜀绣？"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"]
    assert data["query_type"] == "fact"
    assert data["selected_route"] == "vector"

    assert len(data["evidences"]) > 0
    assert "paths" in data
    assert len(data["sources"]) > 0

    assert "graph_nodes" in data
    assert "graph_edges" in data


def test_graph():
    response = client.post(
        "/graph",
        json={"question": "什么是蜀绣？"},
    )

    assert response.status_code == 200

    data = response.json()

    assert "nodes" in data
    assert "edges" in data

    assert len(data["nodes"]) > 0


def test_source():
    response = client.post(
        "/source",
        json={"question": "什么是蜀绣？"},
    )

    assert response.status_code == 200

    data = response.json()

    assert "sources" in data
    assert len(data["sources"]) > 0

def test_context():
    response = client.post(
        "/context",
        json={"question": "什么是蜀绣？"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["query"] == "什么是蜀绣？"
    assert "context" in data
    assert "蜀绣" in data["context"]


def test_explanation():
    response = client.post(
        "/explanation",
        json={"question": "什么是蜀绣？"},
    )

    assert response.status_code == 200

    data = response.json()

    assert "selected_retriever" in data
    assert "route_reason" in data
    assert "evidence" in data
    assert "relation_paths" in data
    assert "sources" in data
    assert "graph" in data