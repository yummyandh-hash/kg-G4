# 成员 C Stage 1 执行说明

## 你的职责

把 B 交付的 chunks 和 clean documents 变成一版能在第一次汇报前展示的、稳定的、可追溯的 Neo4j 知识图谱。

## Stage 1 交付目标

- Ontology V1
- schema-constrained 抽取
- 原始与去重后的图谱结果
- 给 D 的轻量图数据
- Neo4j Cypher 导出
- 质量统计

## 数据输入

- `data/chunks/chunks.jsonl`
- `data/clean/documents/*.json`

## 数据输出

- `outputs/c_module/raw_extraction_result.json`
- `outputs/c_module/extraction_result.json`
- `outputs/c_module/graph_data_for_d.json`
- `outputs/c_module/kg_export.json`
- `outputs/c_module/kg_export.cypher`
- `outputs/c_module/quality_report.json`

## 开发顺序

1. 先读 B 的字段
2. 冻结 Ontology V1
3. 抽取规则化实体与关系
4. 做实体消歧与去重
5. 导出 Neo4j 和 D 友好图数据
6. 做质量统计

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
