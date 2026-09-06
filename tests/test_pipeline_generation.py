from orchestration.answer_generator import GenerationResult
from orchestration.mock_retrievers import MockGraphRetriever, MockVectorRetriever
from orchestration.pipeline import OrchestrationPipeline


class FakeLLMGenerator:
    def generate(self, query, evidences):
        return GenerationResult(
            answer=f"generated from {len(evidences)} evidence(s)",
            provider="fake-llm",
            used_llm=True,
        )


def test_pipeline_generates_answer_and_records_llm_timing():
    pipeline = OrchestrationPipeline(
        retrievers={
            "vector": MockVectorRetriever(),
            "graph": MockGraphRetriever(),
        },
        answer_generator=FakeLLMGenerator(),
    )

    response = pipeline.run("fact query")

    assert response.answer == "generated from 1 evidence(s)"
    assert "generation" in response.timing


def test_pipeline_does_not_record_llm_timing_for_extractive_fallback():
    pipeline = OrchestrationPipeline(
        retrievers={
            "vector": MockVectorRetriever(),
            "graph": MockGraphRetriever(),
        }
    )

    response = pipeline.run("fact query")

    assert response.answer
    assert "generation" not in response.timing
