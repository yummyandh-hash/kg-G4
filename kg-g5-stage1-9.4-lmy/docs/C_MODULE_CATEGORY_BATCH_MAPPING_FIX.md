# C 模块 category/batch 字段语义错位修复说明

## 1. 问题背景

本次全仓审计发现，知识图谱数据中存在 category/batch 语义错位风险：

- B 模块旧版 chunk 中，`source_category` 大量为 `第一批`；
- 部分 KG 样本中出现 `heritage_category=传统舞蹈`、`raw_category_name=传统美术` 的字段冲突；
- 如果 C 模块直接信任上游字段，可能把“第一批/2006”误建成 `Category` 节点，或把错误 raw 字段继续写入 Neo4j。

C 模块本次修复的目标是：在不修改 B 模块的前提下，在 KG 构建层增加兼容与兜底规则，保证最终图谱中的 `Category` 只表示非遗门类，`batch` 只表示批次信息。

## 2. 字段语义重新确认

| 字段 | C 模块中的含义 | 允许值示例 | 禁止值示例 |
|---|---|---|---|
| `heritage_category` | 标准非遗门类 | `传统舞蹈`、`传统美术`、`民俗` | `第一批`、`2006` |
| `raw_category_name` | 进入 KG 前清洗后的门类来源值 | `传统舞蹈` | `第一批`、`2006(第一批)` |
| `batch` | 项目申报批次或年份 | `第一批`、`2006` | `传统舞蹈` |
| `Category` 节点 | 知识图谱中的非遗门类节点 | `传统舞蹈` | `第一批` |

## 3. 修复文件

本次只修改 C 模块相关文件：

- `c_module/extractor.py`
- `c_module/quality.py`
- `tests/test_c_module.py`
- `docs/C_MODULE_CATEGORY_BATCH_MAPPING_FIX.md`

没有修改 B、D、A 模块代码，也没有 push 到远程仓库。

## 4. 核心修复思路

### 4.1 增加批次识别规则

在 `extractor.py` 中新增 `_looks_like_batch_label()`，识别以下内容为批次：

- `第一批`、`第二批` 等中文批次；
- `2006`、`2008` 等年份；
- 包含 `批` 的组合文本，例如 `2006(第一批)`。

这样 C 模块可以明确知道：这些值不能进入 `Category` 和 `raw_category_name`。

### 4.2 增加标准门类白名单

C 模块继续使用十大非遗门类白名单：

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

只有命中白名单的值，才允许作为 `Category` 节点写入 KG。

### 4.3 增加项目编号兜底推断

由于旧版 B 数据中 `source_category` 可能是 `第一批`，C 模块不能只依赖 `source_category`。

本次新增 `PROJECT_NUMBER_CATEGORY_PREFIXES`，根据国家级非遗项目编号前缀推断门类：

| 编号前缀 | 推断门类 |
|---|---|
| `Ⅰ` | 民间文学 |
| `Ⅱ` | 传统音乐 |
| `Ⅲ` | 传统舞蹈 |
| `Ⅳ` | 传统戏剧 |
| `Ⅴ` | 曲艺 |
| `Ⅵ` | 传统体育、游艺与杂技 |
| `Ⅶ` | 传统美术 |
| `Ⅷ` | 传统技艺 |
| `Ⅸ` | 传统医药 |
| `Ⅹ` | 民俗 |

例如：

```text
项目编号：Ⅲ-024_01_222400
```

C 模块会兜底识别为：

```text
heritage_category = 传统舞蹈
Category 节点 = 传统舞蹈
```

不会再把 `第一批` 写成门类。

### 4.4 调整 C 模块字段优先级

修复后，C 模块识别门类时按以下优先级处理：

1. B 新字段：`heritage_category`
2. B 新字段或兼容字段：`source_type`、`raw_type`
3. B 修复后的 `source_category`
4. 清洗后的 `raw_category_name`
5. raw manifest 中的补充字段
6. 项目编号前缀兜底推断

批次字段则从以下位置识别：

1. 旧版误放到 `source_category` 的 `第一批`
2. `raw_category_name` 中的批次组合
3. `source_batch`
4. `batch`
5. chunk 正文
6. raw manifest 中的 `rx_time/category_name`

这样能同时兼容 B 的旧数据和 B 修复后的新数据。

### 4.5 修复 raw_category_name 冲突

旧逻辑中，raw manifest 的 `category_name` 可能来自目录名，存在和项目真实 `type` 不一致的情况。

修复后：

- 如果 `raw_category_name` 是 `第一批` 或年份，则清空，不作为门类；
- 如果 `raw_category_name` 是标准门类但和 `heritage_category` 冲突，则以 `heritage_category` 为准；
- 如果没有可用 `raw_category_name`，但已有标准 `heritage_category`，则让 `raw_category_name` 与 `heritage_category` 保持一致。

因此不会再出现：

```text
heritage_category = 传统舞蹈
raw_category_name = 传统美术
```

而会统一为：

```text
heritage_category = 传统舞蹈
raw_category_name = 传统舞蹈
```

## 5. 质量检查增强

在 `quality.py` 中新增两个风险指标：

| 指标 | 含义 | 目标 |
|---|---|---|
| `project_category_conflict_count` | 项目节点中 `heritage_category` 和 `raw_category_name` 都是标准门类但不一致 | 必须为 0 |
| `project_raw_category_batch_count` | 项目节点中 `raw_category_name` 仍然是批次/年份 | 必须为 0 |

同时保留原有检查：

- `region_as_protection_unit_count`
- `batch_as_category_count`
- `nonstandard_category_count`

## 6. 验证结果

已重新运行 C 模块全量流水线：

```powershell
python -m c_module.pipeline --chunks data/chunks/chunks.jsonl --output outputs/c_module
```

本次全量输出的核心结果：

```json
{
  "entity_count": 14228,
  "relation_count": 26273,
  "duplicate_entity_count": 0,
  "duplicate_relation_count": 0,
  "isolated_entity_count": 0,
  "warning_count": 0,
  "risk_report": {
    "region_as_protection_unit_count": 0,
    "batch_as_category_count": 0,
    "nonstandard_category_count": 0,
    "project_category_conflict_count": 0,
    "project_raw_category_batch_count": 0
  }
}
```

这说明：

- `第一批/2006` 没有进入 `Category`；
- `raw_category_name` 没有继续保存批次；
- `heritage_category/raw_category_name` 冲突已经消除；
- 地名仍然没有误写为 `ProtectionUnit`；
- 去重后没有重复实体和重复关系；
- 没有孤立实体。

## 7. 典型成功案例

输入 chunk：

```json
{
  "source_name": "朝鲜族农乐舞（象帽舞）",
  "source_category": "第一批",
  "source_batch": "2006",
  "content": "项目名称：朝鲜族农乐舞（象帽舞）\n项目编号：Ⅲ-024_01_222400\n批次：2006\n类别：第一批"
}
```

修复前风险：

```text
Category = 第一批
```

修复后结果：

```text
batch = 第一批
heritage_category = 传统舞蹈
raw_category_name = 传统舞蹈
Category = 传统舞蹈
```

原因是 C 模块识别到：

- `第一批` 是批次；
- `Ⅲ` 编号前缀对应 `传统舞蹈`；
- 所以 `BELONGS_TO` 应该指向 `传统舞蹈`，不是 `第一批`。

## 8. 对 D 模块的交接说明

D 模块后续读取 Neo4j 或 `graph_data_for_d.json` 时，可以信任：

- `Category` 节点表示非遗门类；
- `BELONGS_TO` 关系指向非遗门类；
- `batch` 字段表示批次/年份；
- `raw_category_name` 不再保存 `第一批/2006` 这类批次值；
- `ProtectionUnit` 中不会写入纯行政地名。

如果 D 仍然查不到“项目属于什么门类”或“项目和地区有什么关系”，应优先检查 D 的自然语言 query 解析和 GraphRetriever 编排逻辑，而不是再回退到 C 的 KG schema。

## 9. 后续风险

仍需注意两个边界：

1. 如果 B 后续提供的新数据完全没有项目编号，也没有 `heritage_category/source_type/source_category`，C 模块不会凭空生成门类；
2. 如果原始项目编号本身错误，项目编号兜底推断也会受到影响，因此 B 的字段清洗仍然是第一优先来源。

总体上，本次修复已经完成 C 模块对 category/batch 语义错位问题的防护、修正和质量验证。
