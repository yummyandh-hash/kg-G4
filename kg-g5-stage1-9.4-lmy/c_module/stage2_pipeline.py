"""C 模块 Stage 2：实体消歧、KG V2 导出与质量审计。"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .entity_resolution import (
    load_kg_json,
    resolve_entities,
    write_merge_log,
    write_review_candidates,
)
from .extractor import extract_chunks, load_chunks, result_to_json
from .graph_ops import deduplicate_result
from .neo4j_writer import export_cypher, export_graph_data, export_json
from .quality import compute_quality


def _load_input(input_path: str | Path | None, chunks_path: str | Path | None):
    if input_path:
        return load_kg_json(input_path)
    if not chunks_path:
        raise ValueError("必须提供 --input 或 --chunks")
    return deduplicate_result(extract_chunks(load_chunks(chunks_path)))


def run_stage2(
    output_dir: str | Path,
    *,
    input_path: str | Path | None = None,
    chunks_path: str | Path | None = None,
    candidates_path: str | Path | None = None,
) -> dict:
    source = _load_input(input_path, chunks_path)
    resolved, candidates, resolution_report = resolve_entities(source, candidates_path)
    resolved = deduplicate_result(resolved)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    export_json(resolved, out_dir, "kg_v2.json")
    export_graph_data(resolved, out_dir, "graph_data_for_d_v2.json")
    export_cypher(resolved, out_dir, include_provenance=True, filename="kg_v2.cypher")
    (out_dir / "extraction_result_v2.json").write_text(
        json.dumps(result_to_json(resolved), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_merge_log(candidates, out_dir / "entity_merge_log.jsonl")
    write_review_candidates(candidates, out_dir / "review_candidates.jsonl")

    quality = compute_quality(resolved)
    (out_dir / "entity_resolution_report.json").write_text(
        json.dumps(resolution_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "kg_quality_report_v2.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "entity_resolution": resolution_report,
        "kg_quality": quality,
        "output_dir": str(out_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="C Stage 2: Entity Resolution + KG V2")
    parser.add_argument("--input", default="outputs/c_module/kg_export.json")
    parser.add_argument("--chunks", default=None)
    parser.add_argument("--candidates", default=None)
    parser.add_argument("--output", default="outputs/c_module_stage2")
    args = parser.parse_args()
    summary = run_stage2(
        args.output,
        input_path=args.input,
        chunks_path=args.chunks,
        candidates_path=args.candidates,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
