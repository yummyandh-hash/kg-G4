from orchestration.models import Evidence, RetrievalContext


class MockVectorRetriever:
    """MOCK：仅用于 A 在真实 Vector Retriever 完成前联调。"""

    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        return [
            Evidence(
                evidence_id="mock-vector-001",
                content=f"[MOCK] Vector evidence for: {query}",
                retrieval_method="vector",
                score=0.90,
                source_id="mock-vector-source",
            )
        ]


class MockGraphRetriever:
    """MOCK：仅用于 A 在真实 Graph Retriever 完成前联调。"""

    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        return [
            Evidence(
                evidence_id="mock-graph-001",
                content=f"[MOCK] Graph evidence for: {query}",
                retrieval_method="graph",
                score=None,
                source_id="mock-graph-source",
                entity_ids=["mock_entity_a", "mock_entity_b"],
                relation_path=[
                    "mock_entity_a",
                    "mock_relation",
                    "mock_entity_b",
                ],
            )
        ]