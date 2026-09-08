# 成员 C 模块完成报告（Stage 1）

## 1. 任务目标

C 负责把 B 提供的 `chunks.jsonl` 和清洗后的原始文档，转成一版稳定、可解释、可追溯、可供 D 联调的 Neo4j 知识图谱。

Stage 1 的核心不是追求“规模最大”，而是先做出一版能跑通、能讲清、能验证的 baseline。具体目标包括：

- 冻结非遗领域 `Ontology V1`
- 完成结构化实体/关系抽取
- 做实体纠偏、去重和 provenance 合并
- 导出 Neo4j 可导入的 Cypher
- 输出给 D 使用的轻量图数据
- 生成质量统计报告

---

## 2. 输入与输出

### 输入

- `data/chunks/chunks.jsonl`
- `data/raw/**/manifest.jsonl`
- B 交付的清洗文档与分块数据

### 输出

- `outputs/c_module/raw_extraction_result.json`
- `outputs/c_module/extraction_result.json`
- `outputs/c_module/graph_data_for_d.json`
- `outputs/c_module/kg_export.json`
- `outputs/c_module/kg_export.cypher`
- `outputs/c_module/quality_report.json`

---

## 3. 完成步骤

### 第一步：冻结本体 Ontology V1

在 `c_module/ontology.py` 中先固定系统允许的节点和关系类型。

节点类型包括：

- `InheritProject`
- `Category`
- `Bearer`
- `Region`
- `ProtectionUnit`
- `Technique`
- `CulturalElement`

关系类型包括：

- `BELONGS_TO`
- `LOCATED_IN`
- `HAS_BEARER`
- `PROTECTED_BY`
- `USES_TECHNIQUE`
- `RELATED_TO`
- `ALIAS_OF`
- `SAME_AS`

这一步的意义是：先把“能抽什么、能连什么”限制住，避免抽取器自由发挥，降低幻觉和类型漂移。

---

### 第二步：定义统一数据结构

在 `c_module/schemas.py` 中，把所有抽取结果封成可验证的数据结构：

- `Provenance`：记录来源、chunk、URL、抓取时间和证据文本
- `EntityRecord`：节点记录
- `RelationRecord`：边记录
- `ExtractionResult`：整批抽取结果

这样做的底层好处是：抽取结果不是松散字典，而是固定结构，后面无论是去重、导出还是统计，都有统一接口。

---

### 第三步：构建源上下文与来源追踪

在 `c_module/extractor.py` 中，先为每个 chunk 构造上下文：

- `_build_raw_metadata_index()`：从 `data/raw` 中建立 `document_id -> 元数据` 索引
- `_raw_metadata_for_chunk()`：按 `document_id` 找到原始元信息
- `_chunk_provenance()`：为每个 chunk 生成 provenance
- `_source_context_from_chunk()`：把 `source_name / source_region / source_org / source_category / source_batch` 统一成一个上下文对象

这一层的作用是：抽取时不是“只看文本”，而是同时看文档级元数据，保证后续每条实体和关系都能追溯到来源。

---

### 第四步：结构化抽取

`extract_from_chunk()` 是核心入口。

它的处理顺序是：

1. 清洗 chunk 文本
2. 构造根节点 `InheritProject`
3. 识别类别 `Category`
4. 识别地区 `Region`
5. 识别保护单位 `ProtectionUnit`
6. 从正文中抽取 `CulturalElement`
7. 组装关系
8. 返回单个 chunk 的结果

#### 4.1 项目根节点

每个 chunk 都先挂到一个 `InheritProject` 节点上。
这样做的好处是图谱有稳定根节点，便于 D 后续做检索，也便于把同一项目的多个 chunk 汇总到一起。

#### 4.2 类别抽取

`_extract_category()` 会优先识别真正的非遗门类，比如：

- 民间文学
- 传统音乐
- 传统舞蹈
- 传统戏剧
- 曲艺
- 传统体育、游艺与杂技
- 传统美术
- 传统技艺
- 传统医药
- 民俗

同时显式过滤：

- “第一批、第二批……”
- “2006、2011”等批次信息
- `批` 相关字段

这一步专门解决了之前“把批次当 Category”的错误。

#### 4.3 地区与保护单位抽取

`_split_regions()` 和 `_split_protection_units()` 分别负责地区和保护单位拆分。

核心规则是：

- `Region` 只能是行政地名
- `ProtectionUnit` 只能是机构单位
- 地名不能进保护单位，机构不能冒充地名

这部分又由 `resolver.py` 里的 `correct_entity_type()` 做最后兜底：

- 如果一个 `ProtectionUnit` 看起来像地名，就强制改成 `Region`
- 如果一个 `Region` 看起来像机构，就强制改成 `ProtectionUnit`

这套规则直接解决了最严重的类型误判问题。

#### 4.4 文化元素抽取

为了提高 recall，代码分两层抽文化元素：

- `_find_keyword_entities()`：先用一组手工词表找高置信关键词
- 再用正则模式抓取少量 `X舞 / X歌 / X绣 / X戏 / X画 / X曲` 之类的结构

这样做的原因是：非遗文本里文化元素很多是短语型、意象型表达，单靠严格分类容易漏掉，所以 Stage 1 采取“保守但尽量多抽”的方式。

#### 4.5 LLM 约束的预留

代码里保留了 `EXTRACTION_PROMPT` 和温度参数 `LLM_TEMPERATURE = 0.15`。

这表示系统结构已经预留了未来的 LLM 抽取接口，但 Stage 1 先以规则抽取为主，确保 baseline 稳定、可控、可解释。

---

### 第五步：实体消歧与去重

在 `c_module/graph_ops.py` 和 `c_module/resolver.py` 中完成两个动作：

#### 5.1 类型纠偏

`correct_entity_type()` 会根据名称规则判断：

- 地名更像 `Region`
- 机构更像 `ProtectionUnit`

同时会把纠偏原因写进 `attributes["type_correction"]`，方便后续审查。

#### 5.2 去重合并

`deduplicate_result()` 会按 `entity_id` 和关系签名进行融合：

- 同名同类实体合并
- 别名合并
- attributes 合并
- provenance 合并
- 关系按 `(relation_type, source, target)` 去重

这一步的底层逻辑是：原始抽取结果可能来自多个 chunk，同一个实体会重复出现，所以必须用稳定 ID 和 provenance 合并把它们收拢成一版最终图谱。

---

### 第六步：导出 Neo4j 与 D 友好数据

在 `c_module/neo4j_writer.py` 中完成三类输出：

#### 6.1 Neo4j 约束

先给每类节点建唯一约束，保证 `entity_id` 不重复。

#### 6.2 Cypher 导出

`entity_merge_cypher()` 和 `relation_merge_cypher()` 负责把实体和关系变成 `MERGE` 语句。

当前导出策略是：

- 只保留 Neo4j 能直接接受的属性值
- 复杂字段转成 JSON 字符串
- 每条语句单独结束，避免脚本被当成一条超长语句

这样能避免导入时的语法错误和内存压力。

#### 6.3 给 D 的轻量图

`export_graph_data()` 会输出 `graph_data_for_d.json`，里面只有：

- 节点
- 边
- 必要属性
- provenance

这份数据更适合检索模块读取，不需要再解析完整 Cypher。

---

### 第七步：质量统计

在 `c_module/quality.py` 中统计：

- 原始实体数
- 原始关系数
- 去重后实体数
- 去重后关系数
- 重复实体数
- 重复关系数
- 孤立节点数
- 实体类型分布
- 关系类型分布
- 风险报告

风险报告专门检查三类问题：

- 地名是否被误判成 `ProtectionUnit`
- 批次是否被误判成 `Category`
- `Category` 是否出现非标准门类

这一步是 C 模块的“自检”，也是答辩时最容易讲清楚的质量控制证据。

---

### 第八步：流水线一键执行

`c_module/pipeline.py` 把整个流程串起来：

1. 读取 chunks
2. 生成 raw 抽取结果
3. 生成去重后的最终结果
4. 导出 JSON
5. 导出 Neo4j Cypher
6. 输出质量报告

这意味着 C 模块不是零散脚本，而是一个完整可复现的数据处理流水线。

---

## 4. 当前结果

根据最新 `quality_report.json`，当前 Stage 1 的结果为：

- `entity_count`: 15528
- `relation_count`: 27935
- `deduped_entity_count`: 15528
- `deduped_relation_count`: 27935
- `duplicate_entity_count`: 0
- `duplicate_relation_count`: 0
- `isolated_entity_count`: 0
- `warning_count`: 0

实体类型分布：

- `InheritProject`: 1749
- `Category`: 6
- `Region`: 1072
- `ProtectionUnit`: 1349
- `CulturalElement`: 11352

风险检查结果：

- `region_as_protection_unit_count = 0`
- `batch_as_category_count = 0`
- `nonstandard_category_count = 0`

这说明 C 模块已经完成了 Stage 1 需要的“可用、可导、可追溯”的基础图谱构建。

---

## 5. 可以这样讲给老师听

> 我做的是把非遗文本变成一版稳定、可追溯的知识图谱。  
> 我先冻结了本体，再做结构化抽取，然后做类型纠偏、去重融合和 Neo4j 导出，最后用质量统计验证图谱是否可用。  
> 这套设计的重点不是“抽得最多”，而是“抽得稳、讲得清、能联调”。

---

## 6. 本阶段交付总结

C 模块 Stage 1 已完成以下工作：

- 本体冻结
- 抽取规则落地
- 实体消歧与类型纠偏
- Neo4j 导出
- D 可用轻量图输出
- 质量统计与风险检查

下一阶段的衔接重点是把 B 提供的实体候选继续融合，生成更干净的 KG V2，并支持 D 的后续图检索。

