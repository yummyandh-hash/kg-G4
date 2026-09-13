import json

from orchestration.citation_service import CitationService
from orchestration.stage1 import _build_citation_service


def test_citation_service_uses_chunk_id_index(tmp_path):
    chunks_file = tmp_path / "chunks.jsonl"
    chunks_file.write_text(
        json.dumps(
            {
                "chunk_id": "chunk-1",
                "chunk_type": "detail_content",
                "content": "板头曲传播中心在南阳市。",
                "source_name": "板头曲",
                "source_url": "https://example.com",
                "retrieved_at": "2026-09-12",
                "document_id": "doc-1",
                "source_category": "",
                "source_region": "",
                "source_org": "",
                "source_batch": "",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    service = CitationService(str(chunks_file))

    evidence = service.get_evidence("chunk-1")
    result = service.verify_claim(
        "板头曲传播中心在南阳市。",
        ["chunk-1"],
    )

    assert evidence["chunk_id"] == "chunk-1"
    assert result["label"] == "SUPPORTED"
    assert result["evidences"][0]["chunk_id"] == "chunk-1"


def test_stage1_can_build_optional_citation_service(tmp_path, monkeypatch):
    chunks_file = tmp_path / "chunks.jsonl"
    chunks_file.write_text(
        json.dumps(
            {
                "chunk_id": "chunk-1",
                "chunk_type": "detail_content",
                "content": "证据文本",
                "source_name": "标题",
                "source_url": "https://example.com",
                "retrieved_at": "2026-09-12",
                "document_id": "doc-1",
                "source_category": "",
                "source_region": "",
                "source_org": "",
                "source_batch": "",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KG_G5_CITATION_ENABLED", "1")

    service = _build_citation_service(str(chunks_file))

    assert service is not None
    assert service.get_evidence("chunk-1")["chunk_id"] == "chunk-1"
