"""最小Retriever冒烟测试，PR配套，不需要外部大模型"""
from .base_retriever import RetrievalRequest
from .graph_retriever import GraphRetriever
from .vector_retriever import VectorRetriever
from .multi_retriever import MultiRetriever

def test_graph_basic():
    ret = GraphRetriever()
    req = RetrievalRequest(query="朝鲜族农乐舞", top_k=3)
    res = ret.retrieve(req.query, context=req.context, top_k=req.top_k)
    assert isinstance(res, list)
    assert len(res) <= 3

def test_vector_basic():
    ret = VectorRetriever(chunks_file="data/chunks/chunks.jsonl")
    req = RetrievalRequest(query="皮影戏", top_k=2)
    res = ret.retrieve(req.query, context=req.context, top_k=req.top_k)
    assert isinstance(res, list)
    assert len(res) <= 2

def test_multi_basic():
    ret = MultiRetriever(chunks_file="data/chunks/chunks.jsonl", enable_graph=False)
    req = RetrievalRequest(query="苏绣", top_k=2)
    res = ret.retrieve(req.query, context=req.context, top_k=req.top_k)
    assert isinstance(res, list)

if __name__ == "__main__":
    test_graph_basic()
    print("graph test ok")
    test_vector_basic()
    print("vector test ok")
    test_multi_basic()
    print("multi retriever all smoke test passed")
