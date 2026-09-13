import base64
import json
import sys
import urllib.request
from pathlib import Path


USER = "neo4j"
PASSWORD = "12345678"
URL = "http://localhost:7474/db/neo4j/tx/commit"
DEFAULT_JSON = Path("kg-g5-stage1-9.4-lmy/outputs/c_module_stage2_b_sync/kg_v2.json")

NODE_TYPES = {
    "InheritProject",
    "Category",
    "Bearer",
    "Region",
    "ProtectionUnit",
    "Technique",
    "CulturalElement",
}

RELATION_TYPES = {
    "BELONGS_TO",
    "LOCATED_IN",
    "HAS_BEARER",
    "PROTECTED_BY",
    "USES_TECHNIQUE",
    "RELATED_TO",
    "ALIAS_OF",
    "SAME_AS",
}


def post(statement, parameters=None):
    auth = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    payload = json.dumps(
        {"statements": [{"statement": statement, "parameters": parameters or {}}]},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Basic " + auth},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("errors"):
        raise RuntimeError(result["errors"][0])
    return result


def chunks(items, size):
    for offset in range(0, len(items), size):
        yield items[offset : offset + size]


def entity_row(entity):
    return {
        "entity_id": entity["entity_id"],
        "name": entity.get("name"),
        "canonical_name": entity.get("canonical_name"),
        "aliases": entity.get("aliases") or [],
        "attributes_json": json.dumps(entity.get("attributes") or {}, ensure_ascii=False),
        "provenance_json": json.dumps(entity.get("provenance") or [], ensure_ascii=False),
    }


def relation_row(relation):
    return {
        "source_entity_id": relation["source_entity_id"],
        "target_entity_id": relation["target_entity_id"],
        "confidence": float(relation.get("confidence") or 0.0),
        "attributes_json": json.dumps(relation.get("attributes") or {}, ensure_ascii=False),
        "provenance_json": json.dumps(relation.get("provenance") or [], ensure_ascii=False),
    }


def main():
    json_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_JSON
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    entities = payload.get("entities") or []
    relations = payload.get("relations") or []

    post("CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.entity_id IS UNIQUE")
    print("schema done")

    batch_size = 300
    imported_entities = 0
    for entity_type in sorted({item["entity_type"] for item in entities}):
        if entity_type not in NODE_TYPES:
            raise ValueError(f"unsupported entity type: {entity_type}")
        rows = [entity_row(item) for item in entities if item["entity_type"] == entity_type]
        statement = f"""
        UNWIND $rows AS row
        MERGE (n:Entity:{entity_type} {{entity_id: row.entity_id}})
        SET n.name = row.name,
            n.canonical_name = row.canonical_name,
            n.aliases = row.aliases,
            n.attributes_json = row.attributes_json,
            n.provenance_json = row.provenance_json
        """
        for batch in chunks(rows, batch_size):
            post(statement, {"rows": batch})
            imported_entities += len(batch)
            print(f"entities done {imported_entities}/{len(entities)}")

    imported_relations = 0
    for relation_type in sorted({item["relation_type"] for item in relations}):
        if relation_type not in RELATION_TYPES:
            raise ValueError(f"unsupported relation type: {relation_type}")
        rows = [relation_row(item) for item in relations if item["relation_type"] == relation_type]
        statement = f"""
        UNWIND $rows AS row
        MATCH (source:Entity {{entity_id: row.source_entity_id}})
        MATCH (target:Entity {{entity_id: row.target_entity_id}})
        MERGE (source)-[r:{relation_type}]->(target)
        SET r.confidence = row.confidence,
            r.attributes_json = row.attributes_json,
            r.provenance_json = row.provenance_json
        """
        for batch in chunks(rows, batch_size):
            post(statement, {"rows": batch})
            imported_relations += len(batch)
            print(f"relations done {imported_relations}/{len(relations)}")

    print("import ok")


if __name__ == "__main__":
    main()
