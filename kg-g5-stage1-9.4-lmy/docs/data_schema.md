# ihchina 数据字段表（成员 B · 9/3 交付物）

> 数据源：中国非物质文化遗产网 名录页 `https://www.ihchina.cn/project.html#target1`
> 本表定义"一条非遗项目记录"在系统内的统一 schema。下游 C（抽取）、D（检索）、E（展示）都按此表消费数据。

## 一、clean document（清洗后的项目记录，`data/clean/documents/*.json`）

| 字段 | 类型 | 说明 | 示例 | 来源 |
|---|---|---|---|---|
| `name` | string | 项目规范名（去掉括号别名） | `苏绣` | 名录页 |
| `aliases` | string[] | 别名列表，来自名称括号部分 | `["苏州刺绣"]` | 名称括号拆分 |
| `number` | string | 官方项目编号（去重主键） | `Ⅱ-18` | 名录页 |
| `category` | string | 十大门类，规范枚举 | `传统美术` | 名录页 |
| `batch` | string | 批次 | `第二批` | 名录页 |
| `region` | string | 申报地区原文 | `江苏省苏州市` | 名录页 |
| `region_norm` | string | 地区规范形（剥省/市后缀） | `江苏苏州` | 规则生成 |
| `org` | string | 保护单位，可为 null | `苏州市非物质文化遗产保护管理办公室` | 详情页 |
| `body` | string | 项目介绍正文 | `苏绣是……` | 详情页 |
| `source_url` | string | provenance：原始页面地址 | `https://www.ihchina.cn/...` | 爬虫 |
| `document_id` | string | provenance：稳定唯一 ID（编号优先，无编号用名称哈希） | `ihchina_3f2a1b9c8d7e` | 规则生成 |
| `chunk_source_page` | int | provenance：来自爬虫第几页 | `3` | 爬虫 |
| `retrieved_at` | string | provenance：抓取时间 ISO8601 | `2026-09-03T21:40:00+08:00` | 爬虫 |

## 二、chunk（检索最小单元，`data/clean/chunks/chunks.jsonl`，每行一个 JSON）

| 字段 | 类型 | 说明 |
|---|---|---|
| `chunk_id` | string | `{document_id}_chunk_{序号}`，全局唯一 |
| `document_id` | string | 回链到所属项目记录 |
| `source_url` | string | 继承自 document |
| `retrieved_at` | string | 继承自 document |
| `text` | string | `[项目名 \| 类别 \| 批次 \| 地区]` 前缀 + 正文片段（300–500 字，重叠 50 字） |

## 三、清洗规则（写死在 `crawler/clean.py`，改规则要过 PR）

1. **去重**：按 `number`（无编号按 `document_id`）保留首条；
2. **地区规范化**：剥 `省/市/区/县/自治区` 等后缀 → `region_norm`；
3. **类别映射**：统一到十大门类标准名；
4. **别名拆分**：`苏绣（苏州刺绣）` → `name=苏绣, aliases=[苏州刺绣]`；
5. **缺失处理**：缺失字段显式写 `null`/空串，绝不静默丢弃（缺失率进 `reports/clean_report.md`）。

## 四、已知待办

- [ ] `parse_raw()` 里的字段映射（`crawler/clean.py` 的 `normalize()`）以 F12 实际返回字段为准调整
- [ ] 详情页（正文 `body`、保护单位 `org`）需要二次请求，skeleton 阶段先用列表页字段
