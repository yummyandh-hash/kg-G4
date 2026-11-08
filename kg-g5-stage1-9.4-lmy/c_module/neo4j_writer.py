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


def entity_merge_cypher(entity: dict, include_provenance: bool = False) -> str:
    labels = ":" + entity["entity_type"]
    set_parts = [
        f"n.name = {_property_literal(entity['name'])}",
        f"n.canonical_name = {_property_literal(entity['canonical_name'])}",
        f"n.aliases = {_property_literal(entity['aliases'])}",
        f"n.attributes_json = {_property_literal(entity['attributes'])}",
    ]
    if include_provenance:
        set_parts.append(f"n.provenance_json = {_property_literal(entity['provenance'])}")
    return (
        f"MERGE (n{labels} {{entity_id: {_property_literal(entity['entity_id'])}}}) "
        f"SET {', '.join(set_parts)};"
    )


def relation_merge_cypher(relation: dict, include_provenance: bool = False) -> str:
    set_parts = [
        f"rel.confidence = {_property_literal(relation['confidence'])}",
        f"rel.attributes_json = {_property_literal(relation['attributes'])}",
    ]
    if include_provenance:
        set_parts.append(f"rel.provenance_json = {_property_literal(relation['provenance'])}")
    return (
        f"MATCH (s {{entity_id: {_property_literal(relation['source_entity_id'])}}}) "
        f"MATCH (t {{entity_id: {_property_literal(relation['target_entity_id'])}}}) "
        f"MERGE (s)-[rel:{relation['relation_type']}]->(t) "
        f"SET {', '.join(set_parts)};"
    )


def export_cypher(
    result: ExtractionResult,
    out_dir: str | Path,
    include_provenance: bool = False,
    filename: str = "kg_export.cypher",
) -> Path:
    # main previously accepted the filename as the third positional argument.
    if isinstance(include_provenance, str):
        filename, include_provenance = include_provenance, True
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    cypher_file = out_path / filename
    with cypher_file.open("w", encoding="utf-8") as f:
        for stmt in build_constraints_cypher():
            f.write(stmt.rstrip(";") + ";\n")
        f.write("\n")
        for entity in result.entities:
            f.write(entity_merge_cypher(asdict(entity), include_provenance=include_provenance).rstrip(";") + ";\n")
        f.write("\n")
        for relation in result.relations:
            f.write(relation_merge_cypher(asdict(relation), include_provenance=include_provenance).rstrip(";") + ";\n")
    return cypher_file


def export_json(
    result: ExtractionResult,
    out_dir: str | Path,
    filename: str = "kg_export.json",
) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_file = out_path / filename
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


def export_graph_data(
    result: ExtractionResult,
    out_dir: str | Path,
    filename: str = "graph_data_for_d.json",
) -> Path:
    """输出更适合 D 使用的轻量图结构。"""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    graph_file = out_path / filename
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


def _property_literal(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        if all(_is_property_value(item) for item in value):
            return "[" + ", ".join(_property_literal(item) for item in value) + "]"
        return json.dumps(json.dumps(value, ensure_ascii=False), ensure_ascii=False)
    if isinstance(value, tuple):
        if all(_is_property_value(item) for item in value):
            return "[" + ", ".join(_property_literal(item) for item in value) + "]"
        return json.dumps(json.dumps(list(value), ensure_ascii=False), ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(json.dumps(value, ensure_ascii=False), ensure_ascii=False)
    return json.dumps(str(value), ensure_ascii=False)


def _is_property_value(value: object) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None
