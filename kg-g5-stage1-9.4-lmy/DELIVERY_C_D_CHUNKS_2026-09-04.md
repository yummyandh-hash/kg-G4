# 数据交付文档 - C和D成员
**交付时间**: 2026年9月4日  
**交付人**: 成员B  
**交付内容**: chunks + provenance字段  

## 数据概况

### 1. 原始数据
- **来源**: 中国非物质文化遗产网 (www.ihchina.cn)
- **类别**: 传统美术类（类别16）
- **项目数量**: 1749个（原计划1557个，实际爬取1749个）
- **子项总数**: 约3610个
- **数据获取时间**: 2026-09-04T09:32:27+08:00
- **爬取页数**: 164页
- **爬取批次**: 分4批完成，每批50页

### 2. 清洗后数据
- **文档数量**: 1749个
- **存储位置**: `data/clean/documents/`
- **格式**: JSON（每个文件一个项目）

### 3. 分块数据
- **总块数量**: 27375个
- **分块类型分布**:
  - basic_info: 1749个
  - region_info: 1749个
  - organization: 1749个
  - detail_content: 22128个
- **存储位置**: `data/chunks/`
- **文件**:
  - `chunks.jsonl`: 所有分块数据（15.3MB）
  - `stats.json`: 统计信息
- **存储位置**: `data/chunks/`
- **格式**: JSONL（每行一个块）

## 分块策略

每个项目被分为以下3个块：

### 1. 基本信息 (basic_info)
- 项目名称、编号、批次、类别
- 示例：
```json
{
  "chunk_id": "ihchina_22301d8623f6_name",
  "chunk_type": "basic_info",
  "content": "项目名称：蜀绣\n项目编号：Ⅰ-FRZX-8\n批次：2006\n类别：第一批"
}
```

### 2. 地区信息 (region_info)
- 申报地区、地区简称
- 示例：
```json
{
  "chunk_id": "ihchina_22301d8623f6_region",
  "chunk_type": "region_info",
  "content": "申报地区：重庆市渝中区，四川省成都市\n地区简称：重庆渝中区，四川成都"
}
```

### 3. 组织信息 (organization)
- 保护单位信息
- 示例：
```json
{
  "chunk_id": "ihchina_22301d8623f6_org",
  "chunk_type": "organization",
  "content": "保护单位：重庆市渝中区，四川省成都市"
}
```

## Provenance 字段说明

每个chunk都包含以下完整的provenance字段：

- **source_name**: 源项目名称
- **source_category**: 源项目类别
- **source_region**: 源项目申报地区
- **source_org**: 源项目保护单位
- **source_url**: 源页面URL
- **retrieved_at**: 数据获取时间
- **document_id**: 源文档ID
- **source_batch**: 源批次信息

## 项目列表

交付的10个项目包括：

1. 京绣 (Ⅰ-FRZX-1) - 北京市房山区，河北省定兴县
2. 苏绣 (Ⅰ-FRZX-2) - 江苏省苏州市
3. 无锡精微绣 (Ⅰ-FRZX-3) - 江苏省无锡市
4. 南通仿真绣 (Ⅰ-FRZX-4) - 江苏省南通市
5. 扬州刺绣 (Ⅰ-FRZX-5) - 江苏省扬州市
6. 上海绒绣 (Ⅰ-FRZX-6) - 上海市浦东新区
7. 顾绣 (Ⅰ-FRZX-7) - 上海市松江区
8. 蜀绣 (Ⅰ-FRZX-8) - 重庆市渝中区，四川省成都市
9. 汴绣 (Ⅰ-FRZX-9) - 河南省开封市
10. 汉绣 (Ⅰ-FRZX-10) - 湖北省武汉市江汉区

## 使用说明

1. **分块数据读取**：使用 `data/chunks/chunks.jsonl` 文件
2. **统计信息**：查看 `data/chunks/stats.json` 获取统计信息
3. **清洗后数据**：从 `data/clean/documents/` 读取完整项目信息

## 下一步建议

1. **模块C（实体抽取）**: 使用chunks数据抽取实体关系
2. **模块D（信息检索）**: 使用chunks构建检索系统
3. **扩展数据**: 可以使用同一爬虫获取更多批次的非遗数据

## 注意事项

- 所有数据均来自官方公开渠道
- 数据包含完整的provenance信息，便于追溯
- 分块策略确保了数据的细粒度和可重用性
- 项目内容字段为空，如需详细信息需访问源URL