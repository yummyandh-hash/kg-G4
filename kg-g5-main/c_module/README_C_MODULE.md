# C 模块 Stage 1 完整说明

## 这部分做什么

C 负责把 B 提供的 `chunks.jsonl` 和 `clean/documents/*.json` 转成可用于 GraphRAG 的高质量 Neo4j 知识图谱。

Stage 1 的重点不是追求大而全，而是先做出一版稳定、可解释、可追溯、可给 D 联调的小规模 KG。

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

## 运行后怎么看

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

## 你答辩时的核心话术

> 我负责把非遗文本可靠地转化成高质量知识图谱，并解决实体重复、关系质量和来源追溯问题。

## 每个主要模块的三问

### Ontology

- 借鉴了什么前沿思路
- 比课堂示例先进在哪里
- 为非遗做了什么改造

### Schema-constrained Extraction

- 为什么不能让 LLM 自由抽
- 为什么要做验证和重试
- 为什么要保留 provenance

### Entity Resolution

- 为什么不能只靠字符串相等
- 为什么要用上下文和相似度
- 为什么要记录 merge log

### Neo4j Writer

- 为什么用 MERGE
- 为什么要加 constraint
- 为什么关系也要带 provenance

### Quality

- 原始抽取数和最终图谱数不是一回事
- 为什么要看去重后指标
- 为什么要同时看实体、关系、孤立点

## 非遗领域改造

- 适配中文地名、别名、旧称
- 适配非遗项目、类别、传承人、保护单位、技艺、文化元素
- 保留 `source_url / document_id / chunk_id / evidence_text`
- 抽取策略更保守，优先可解释和可追溯
