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

    # LLM 最终答案
    assert data["answer"]

    # A Router 返回合法的查询类型
    assert data["query_type"] in {
        "fact",
        "knowledge",
        "relation",
        "multi_hop",
    }

    # 当前真实 Router 对该问题选择 vector
    assert data["selected_route"] == "vector"

    # 必须存在检索证据
    assert "evidences" in data
    assert len(data["evidences"]) > 0

    # paths / sources / graph 字段必须存在
    # Vector 检索不一定产生关系路径，因此 paths 可以为空
    assert "paths" in data
    assert "sources" in data
    assert "timing" in data

    # 当前检索结果应该能够提供来源
    assert len(data["sources"]) > 0

    # Graph 字段属于统一响应结构
    # Vector-only 查询允许为空
    assert "graph_nodes" in data
    assert "graph_edges" in data

    assert isinstance(data["graph_nodes"], list)
    assert isinstance(data["graph_edges"], list)


def test_graph():
    response = client.post("/graph")

    assert response.status_code == 200

    data = response.json()

    assert "nodes" in data
    assert "edges" in data

    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


def test_source():
    response = client.post(
        "/source",
        json={"question": "什么是蜀绣？"},
    )

    assert response.status_code == 200

    data = response.json()

    assert "sources" in data
    assert isinstance(data["sources"], list)
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
    assert data["context"]

    # Context Engineering 至少应该包含问题和检索证据结构
    assert "用户问题" in data["context"]
    assert "检索证据" in data["context"]


def test_graph():
    response = client.post(
        "/graph",
        json={"question": "什么是蜀绣？"},
    )

    assert response.status_code == 200

    data = response.json()

    assert "nodes" in data
    assert "edges" in data

    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)