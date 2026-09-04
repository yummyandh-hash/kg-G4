"""Neo4j 写入层。

默认做法是先导出 Cypher/JSON，不强依赖本机 Neo4j 环境。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .schemas import ExtractionResult


def build_constraints_cypher() -> list[str]:
    return [
        "CREATE CONSTRAINT inherit_project_id IF NOT EXISTS FOR (n:InheritProject) REQUIRE n.entity_id IS UNIQUE;",
        "CREATE CONSTRAINT category_id IF NOT EXISTS FOR (n:Category) REQUIRE n.entity_id IS UNIQUE;",
        "CREATE CONSTRAINT bearer_id IF NOT EXISTS FOR (n:Bearer) REQUIRE n.entity_id IS UNIQUE;",
        "CREATE CONSTRAINT region_id IF NOT EXISTS FOR (n:Region) REQUIRE n.entity_id IS UNIQUE;",
        "CREATE CONSTRAINT protection_unit_id IF NOT EXISTS FOR (n:ProtectionUnit) REQUIRE n.entity_id IS UNIQUE;",
        "CREATE CONSTRAINT technique_id IF NOT EXISTS FOR (n:Technique) REQUIRE n.entity_id IS UNIQUE;",
        "CREATE CONSTRAINT cultural_element_id IF NOT EXISTS FOR (n:CulturalElement) REQUIRE n.entity_id IS UNIQUE;",
    ]


def entity_merge_cypher(entity: dict) -> str:
    props = _cypher_map(entity)
    labels = ":" + entity["entity_type"]
    return (
        f"MERGE (n{labels} {{entity_id: {props['entity_id']}}}) "
        f"SET n.name = {props['name']}, "
        f"n.canonical_name = {props['canonical_name']}, "
        f"n.aliases = {props['aliases']}, "
        f"n.attributes = {props['attributes']}, "
        f"n.provenance = {props['provenance']}"
    )


def relation_merge_cypher(relation: dict) -> str:
    props = _cypher_map(relation)
    return (
        f"MATCH (s {{entity_id: {props['source_entity_id']}}}) "
        f"MATCH (t {{entity_id: {props['target_entity_id']}}}) "
        f"MERGE (s)-[r:{relation['relation_type']}]->(t) "
        f"SET r.confidence = {props['confidence']}, "
        f"r.attributes = {props['attributes']}, "
        f"r.provenance = {props['provenance']}"
    )


def export_cypher(result: ExtractionResult, out_dir: str | Path) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    cypher_file = out_path / "kg_export.cypher"
    with cypher_file.open("w", encoding="utf-8") as f:
        for stmt in build_constraints_cypher():
            f.write(stmt + "\n")
        f.write("\n")
        for entity in result.entities:
            f.write(entity_merge_cypher(asdict(entity)) + "\n")
        f.write("\n")
        for relation in result.relations:
            f.write(relation_merge_cypher(asdict(relation)) + "\n")
    return cypher_file


def export_json(result: ExtractionResult, out_dir: str | Path) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_file = out_path / "kg_export.json"
    json_file.write_text(
        json.dumps(
            {
                "entities": [asdict(e) for e in result.entities],
                "relations": [asdict(r) for r in result.relations],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return json_file


def export_graph_data(result: ExtractionResult, out_dir: str | Path) -> Path:
    """输出更适合 D 使用的轻量图结构。"""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    graph_file = out_path / "graph_data_for_d.json"
    payload = {
        "nodes": [
            {
                "entity_id": e.entity_id,
                "entity_type": e.entity_type,
                "name": e.name,
                "canonical_name": e.canonical_name,
                "aliases": e.aliases,
                "attributes": e.attributes,
                "provenance": [asdict(p) for p in e.provenance],
            }
            for e in result.entities
        ],
        "edges": [
            {
                "relation_type": r.relation_type,
                "source_entity_id": r.source_entity_id,
                "target_entity_id": r.target_entity_id,
                "confidence": r.confidence,
                "attributes": r.attributes,
                "provenance": [asdict(p) for p in r.provenance],
            }
            for r in result.relations
        ],
    }
    graph_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return graph_file


def _cypher_map(obj: dict) -> dict[str, str]:
    def q(value: object) -> str:
        return json.dumps(value, ensure_ascii=False)

    return {k: q(v) for k, v in obj.items()}
