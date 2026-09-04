"""C 模块端到端流水线。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .extractor import extract_chunks, extract_chunks_deduped, load_chunks, result_to_json
from .graph_ops import deduplicate_result
from .neo4j_writer import export_cypher, export_graph_data, export_json
from .quality import compute_quality


def run_pipeline(chunks_path: str | Path, output_dir: str | Path) -> dict:
    chunks = load_chunks(chunks_path)
    raw_result = extract_chunks(chunks)
    result = extract_chunks_deduped(chunks)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "raw_extraction_result.json").write_text(
        json.dumps(result_to_json(raw_result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "extraction_result.json").write_text(
        json.dumps(result_to_json(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    export_json(result, out_dir)
    export_graph_data(result, out_dir)
    export_cypher(result, out_dir, include_provenance=False)
    quality = compute_quality(result)
    (out_dir / "quality_report.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return quality


def main() -> None:
    parser = argparse.ArgumentParser(description="C 模块：抽取、消歧、Neo4j 导出、质量统计")
    parser.add_argument(
        "--chunks",
        default="data/chunks/chunks.jsonl",
        help="输入 chunks.jsonl 路径",
    )
    parser.add_argument(
        "--output",
        default="outputs/c_module",
        help="输出目录",
    )
    args = parser.parse_args()

    quality = run_pipeline(args.chunks, args.output)
    print(json.dumps(quality, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
