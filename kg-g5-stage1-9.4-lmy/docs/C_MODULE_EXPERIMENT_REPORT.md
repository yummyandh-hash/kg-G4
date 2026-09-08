# 非遗知识图谱构建实验报告

## 一、实验名称

基于本体约束的非遗知识图谱构建实验（成员 C，Stage 1）

---

## 二、实验目的

本实验的目标是将 B 提供的非遗文本分块数据转化为一版可用于联调和汇报的 Neo4j 知识图谱，并完成以下任务：

1. 冻结非遗领域 `Ontology V1`；
2. 从 `chunks.jsonl` 中抽取规范化实体与关系；
3. 对实体进行类型纠偏、消歧和去重；
4. 保留来源追踪信息 `provenance`；
5. 导出可导入 Neo4j 的图谱文件；
6. 输出给 D 模块使用的轻量图数据；
7. 统计图谱质量并检查常见抽取风险。

本阶段强调的是“稳定、可解释、可追溯”，而不是单纯追求规模或召回率。

---

## 三、实验环境

- 操作系统：Windows
- 开发工具：VS Code
- 编程语言：Python
- 图数据库：Neo4j Desktop
- 数据来源：中国非物质文化遗产网及 B 模块整理后的 chunks 数据
- 代码目录：`kg-g5-stage1-9.4-lmy/c_module/`

---

## 四、实验数据与输出

### 4.1 输入数据

- `data/chunks/chunks.jsonl`
- `data/raw/**/manifest.jsonl`
- B 模块提供的清洗文档与 provenance 信息

### 4.2 输出结果

- `outputs/c_module/raw_extraction_result.json`
- `outputs/c_module/extraction_result.json`
- `outputs/c_module/graph_data_for_d.json`
- `outputs/c_module/kg_export.json`
- `outputs/c_module/kg_export.cypher`
- `outputs/c_module/quality_report.json`

其中：

- `raw_extraction_result.json` 保存原始抽取结果；
- `extraction_result.json` 保存去重后结果；
- `graph_data_for_d.json` 是给 D 模块使用的轻量图结构；
- `kg_export.cypher` 用于导入 Neo4j；
- `quality_report.json` 用于统计质量与风险。

---

## 五、实验原理与总体设计

### 5.1 本体设计

实验首先在 `c_module/ontology.py` 中冻结 `Ontology V1`。本体中定义了系统允许的节点类型和关系类型：

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

本体设计的意义在于：先规定“能抽什么、能连什么”，再做抽取，避免模型自由发挥造成类型漂移。

### 5.2 数据结构设计

在 `c_module/schemas.py` 中，将所有结果封装成固定结构：

- `Provenance`：来源追踪
- `EntityRecord`：实体节点
- `RelationRecord`：关系边
- `ExtractionResult`：整批抽取结果

这样做的好处是，抽取、去重、导出、统计各环节都依赖统一数据结构，便于验证与扩展。

### 5.3 抽取原理

`extractor.py` 采用“规则抽取 + 预留 LLM 接口”的方式完成 Stage 1。

实验中真正起作用的是规则抽取逻辑，核心思想是：

1. 先建立文档级元数据索引；
2. 结合 chunk 内容和原始来源字段构造上下文；
3. 按本体类型抽取项目、类别、地区、保护单位和文化元素；
4. 用规则和纠偏模块修正明显错误；
5. 保留 provenance，方便追溯。

### 5.4 实体消歧原理

非遗文本中同一实体可能在多个 chunk 中重复出现，例如：

- 项目名称重复出现；
- 地区简称和正式名混用；
- 保护单位存在地域前缀和机构后缀；
- 文化元素在正文中会反复出现。

因此系统不能只靠字符串相等，而要先做：

- 类型纠偏；
- 规范化；
- ID 统一；
- provenance 合并。

### 5.5 Neo4j 导出原理

导出阶段采用 `MERGE` 而不是单纯 `CREATE`，其原因是：

- `MERGE` 具有幂等性；
- 重复导入时不会产生重复节点；
- 适合反复调试和增量更新。

由于 Neo4j 属性不接受任意嵌套 map，因此复杂字段会被序列化为 JSON 字符串，保存在 `attributes_json` 和 `provenance_json` 中。

### 5.6 质量统计原理

`quality.py` 统计图谱的核心指标：

- 节点数
- 关系数
- 去重前后变化
- 重复实体数
- 重复关系数
- 孤立节点数
- 类型分布
- 风险项

这样可以判断图谱是否“可用”，而不是只看图谱是否“能生成”。

---

## 六、实验步骤与实现方法

### 6.1 构建原始元数据索引

`extractor.py` 中的 `_build_raw_metadata_index()` 会扫描 `data/raw/**/manifest.jsonl`，建立 `document_id -> RawMetadata` 的索引。

这一层的作用是把原始文档中的：

- 项目名称
- 分类信息
- 地区
- 保护单位
- 批次
- 抓取时间

统一挂回到 chunk 上。

### 6.2 构建 provenance

`_chunk_provenance()` 会从 chunk 中提取：

- `source_url`
- `document_id`
- `chunk_id`
- `retrieved_at`
- `source_name`
- `source_category`
- `source_region`
- `source_org`
- `source_batch`
- `evidence_text`

这保证了每一个节点和关系都能追溯到证据文本。

### 6.3 结构化抽取

`extract_from_chunk()` 是核心函数。其执行顺序如下：

1. 清洗文本；
2. 生成项目根节点 `InheritProject`；
3. 抽取 `Category`；
4. 抽取 `Region`；
5. 抽取 `ProtectionUnit`；
6. 抽取 `CulturalElement`；
7. 组装关系；
8. 返回该 chunk 的抽取结果。

#### 6.3.1 项目节点

每个 chunk 都会生成一个 `InheritProject` 节点，保证图谱有稳定根节点，便于后续检索和汇总。

项目节点属性中保存：

- `project_number`
- `batch`
- `heritage_category`
- `raw_category_name`
- `document_id`

#### 6.3.2 类别抽取

`_extract_category()` 只允许真正的非遗门类进入 `Category`，例如：

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

- “第一批、第二批……”等批次词
- “2006、2011”等年份批次信息
- 含“批”的字段

这一步专门解决了“把批次误当成 Category”的问题。

#### 6.3.3 地区与保护单位抽取

`_split_regions()` 和 `_split_protection_units()` 分别处理地区和保护单位。

规则约束是：

- `Region` 只能是行政地名；
- `ProtectionUnit` 只能是组织机构；
- 地名不能进入 `ProtectionUnit`；
- 机构不能误判成地名。

这一约束还会交给 `resolver.py` 中的 `correct_entity_type()` 做最后兜底：

- 如果 `ProtectionUnit` 看起来像地名，则改成 `Region`；
- 如果 `Region` 看起来像机构，则改成 `ProtectionUnit`。

#### 6.3.4 文化元素抽取

文化元素通过两层方式抽取：

1. `_find_keyword_entities()` 先从词表中抓高置信关键词；
2. 再通过正则抓取 `X舞 / X歌 / X绣 / X戏 / X画 / X曲` 等短语模式。

这样做的原因是，非遗文本里的文化元素表达较散、较短，单靠严格分类容易漏掉；所以 Stage 1 采用“保守但尽量多抽”的策略。

### 6.4 实体消歧与去重

`graph_ops.py` 中的 `deduplicate_result()` 负责去重与融合，核心逻辑包括：

- 用 `entity_id` 统一实体；
- 用 `(relation_type, source_entity_id, target_entity_id)` 统一关系；
- 合并 aliases；
- 合并 attributes；
- 合并 provenance；
- 更新实体类型纠偏结果。

`resolver.py` 中的 `correct_entity_type()` 进一步处理类型错误，避免把地名识别成保护单位，或者把机构误识别成地区。

### 6.5 Neo4j 导出

`neo4j_writer.py` 负责把最终图谱导成三类产物：

1. 约束语句；
2. 节点/关系 Cypher；
3. 给 D 用的轻量图 JSON。

导出策略如下：

- 节点与关系使用 `MERGE` 保证幂等；
- `entity_id` 作为唯一键；
- 复杂字段转为 JSON 字符串；
- Cypher 每条语句都单独结束；
- Stage 1 导出时默认不把完整 provenance 写入 Neo4j，以减小脚本体积；
- 完整 provenance 保存在 JSON 中，便于后续追踪。

### 6.6 质量统计

`quality.py` 负责统计和风险检测。

统计结果包含：

- `entity_count`
- `relation_count`
- `deduped_entity_count`
- `deduped_relation_count`
- `duplicate_entity_count`
- `duplicate_relation_count`
- `isolated_entity_count`
- 实体类型分布
- 关系类型分布
- 风险报告

风险报告重点检查三类错误：

- 地名误判为 `ProtectionUnit`
- 批次误判为 `Category`
- 非标准类别进入 `Category`

### 6.7 流水线执行

`pipeline.py` 将全部步骤串成一条命令式流程：

1. 读取 chunks；
2. 进行原始抽取；
3. 进行去重与纠偏；
4. 导出 JSON；
5. 导出 Neo4j Cypher；
6. 导出给 D 的图数据；
7. 计算质量报告。

这使得整个 C 模块可以一键复现。

---

## 七、关键代码逻辑分析

### 7.1 `ontology.py`

该文件定义本体骨架，是系统的“类型边界”。它告诉抽取器：哪些节点合法，哪些关系合法，关系两端应该是什么类型。

### 7.2 `schemas.py`

该文件定义实体、关系、来源追踪和总结果的数据结构，是整条流水线的数据基础。

### 7.3 `extractor.py`

这是最核心的业务文件，负责：

- 读取原始块；
- 构建上下文；
- 抽取实体和关系；
- 过滤批次词；
- 纠正类型；
- 保留 provenance；
- 输出原始和去重后的结果。

### 7.4 `resolver.py`

该文件负责实体消歧和类型修正。它通过名称规则、后缀规则和组织特征，判断某个实体更接近地区还是机构。

### 7.5 `graph_ops.py`

该文件负责把原始抽取结果合并成最终图谱，避免重复节点和重复边。

### 7.6 `neo4j_writer.py`

该文件负责导出 Neo4j 兼容格式。它解决了两个实际问题：

- Cypher 语法兼容；
- Neo4j 属性类型兼容。

### 7.7 `quality.py`

该文件负责把图谱质量量化，避免只凭感觉判断图谱好坏。

### 7.8 `pipeline.py`

该文件把所有模块串联起来，是 C 模块的一键入口。

---

## 八、实验结果

根据最新 `outputs/c_module/quality_report.json`，结果如下：

| 指标 | 数值 |
|---|---:|
| 原始实体数 | 15528 |
| 原始关系数 | 27935 |
| 去重后实体数 | 15528 |
| 去重后关系数 | 27935 |
| 重复实体数 | 0 |
| 重复关系数 | 0 |
| 孤立节点数 | 0 |
| 风险告警数 | 0 |

实体类型分布：

| 类型 | 数量 |
|---|---:|
| `InheritProject` | 1749 |
| `Category` | 6 |
| `Region` | 1072 |
| `ProtectionUnit` | 1349 |
| `CulturalElement` | 11352 |

关系类型分布：

| 类型 | 数量 |
|---|---:|
| `BELONGS_TO` | 1739 |
| `LOCATED_IN` | 1691 |
| `PROTECTED_BY` | 1727 |
| `RELATED_TO` | 22778 |

风险检查结果：

- 地名误判为保护单位：0
- 批次误判为类别：0
- 非标准类别：0

---

## 九、结果分析

### 9.1 图谱质量

从统计结果看，图谱已经具备以下特征：

- 节点与关系规模稳定；
- 没有重复实体和重复关系；
- 没有孤立节点；
- 风险检查全部通过。

这说明 C 模块已经完成了 Stage 1 所需的“可用图谱”构建。

### 9.2 类型纠偏效果

本实验最重要的改进之一，是修复了“地名与保护单位混淆”的问题。通过规则纠偏与本体约束，系统避免了将行政地域错误标为机构类型。

### 9.3 类别抽取效果

系统只保留真实非遗门类，不再把“第一批、第二批”等批次词写入 `Category`。这保证了类别层数据是干净的。

### 9.4 文化元素召回

文化元素数量较大，说明正文抽取策略在 Stage 1 中具备较高召回率。由于采用的是规则 + 关键词模式，部分文化元素会切得比较细，这是 Stage 1 为了提升覆盖率所接受的取舍。

### 9.5 对 D 模块的价值

`graph_data_for_d.json` 为 D 提供了直接可读的图结构，使检索模块不必先解析整份 Cypher，就能快速获取节点、关系和 provenance。

---

## 十、实验中遇到的问题与解决

### 问题 1：地名被误判为保护单位

**原因**：地区和机构在中文文本中常常同时出现“县、市、中心、馆”等字样，容易混淆。  
**解决**：在 `resolver.py` 中加入类型纠偏规则，优先识别地名与机构后缀。

### 问题 2：批次被误判为类别

**原因**：很多文本里同时出现“类别”和“批次”，容易被抽取器混写。  
**解决**：在 `_extract_category()` 中显式过滤“第一批、第二批、2006”等批次信息。

### 问题 3：Neo4j 导入脚本过大或语法不兼容

**原因**：复杂属性直接写入 Cypher，Neo4j 对嵌套 map 支持有限。  
**解决**：将复杂属性序列化为 JSON 字符串，并让每条语句独立结束。

### 问题 4：导入时内存压力过大

**原因**：完整 provenance 太长，直接写入 Neo4j 脚本会显著增大体积。  
**解决**：Stage 1 导入时默认只保留轻量图，完整 provenance 留在 JSON 中，供后续分析使用。

---

## 十一、实验结论

本实验完成了成员 C 在 Stage 1 中的全部核心职责，形成了一版可运行、可导入、可验证的非遗知识图谱构建流水线。系统已经具备以下能力：

1. 依据本体进行结构化抽取；
2. 对地名、机构、类别进行规则约束；
3. 保留来源追踪；
4. 支持去重与实体融合；
5. 输出 Neo4j 可导入图谱；
6. 输出给 D 模块使用的轻量图数据；
7. 通过质量统计验证图谱健康度。

Stage 1 的目标不是终点，而是为后续 Stage 2 的实体融合、图检索和多跳路径检索打下稳定基础。

---

## 十二、附录

### 12.1 运行命令

```bash
python -m c_module.pipeline --chunks data/chunks/chunks.jsonl --output outputs/c_module
```

### 12.2 导入 Neo4j

生成 `kg_export.cypher` 后，可使用 Neo4j Desktop 对应的 `cypher-shell` 导入数据库。

### 12.3 关键测试

项目中包含以下测试思路：

- 基本信息抽取是否正确；
- 实体消歧是否正确；
- 类别是否能过滤批次词；
- 地名是否会被纠正为 `Region`。

