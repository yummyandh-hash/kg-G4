# C 模块 Stage 1 完整说明

C 负责把 B 提供的 `chunks.jsonl` 和 `clean/documents/*.json` 转成可用于 GraphRAG 的高质量 Neo4j 知识图谱。

## Stage 1 交付物

- `outputs/c_module/raw_extraction_result.json`
- `outputs/c_module/extraction_result.json`
- `outputs/c_module/graph_data_for_d.json`
- `outputs/c_module/kg_export.json`
- `outputs/c_module/kg_export.cypher`
- `outputs/c_module/quality_report.json`

## 目录

- `ontology.py`：本体与关系约束
- `schemas.py`：实体、关系、溯源的数据结构
- `extractor.py`：从 chunk 中抽取节点和边
- `graph_ops.py`：去重和合并 provenance
- `resolver.py`：实体消歧与融合
- `neo4j_writer.py`：导出 Cypher / JSON / D 友好图数据
- `quality.py`：统计原始与去重后的质量
- `pipeline.py`：一键跑通

## 运行

```bash
python -m c_module.pipeline --chunks data/chunks/chunks.jsonl --output outputs/c_module
```

- `raw_extraction_result.json`
  - 原始抽取结果
- `extraction_result.json`
  - 去重后的最终图谱结果
- `graph_data_for_d.json`
  - 给 D 做检索的轻量图数据
- `kg_export.cypher`
  - 可直接导入 Neo4j 的 Cypher
- `quality_report.json`
  - 原始与去重后的统计

## Stage 1 的设计重点

1. 先定 Ontology V1
2. 再做 schema-constrained extraction
3. 再做实体融合
4. 再导出 Neo4j
5. 最后做质量统计
