# 任务B - 代码说明文档

## 项目概述
这是为ICH GraphRAG项目开发的爬虫和数据预处理代码，用于获取中国非物质文化遗产数据并准备知识图谱构建。

## 文件结构

### 1. 核心脚本（crawler/）
- **ihchina_crawler_simple.py** - 简化版爬虫（推荐使用）
  - 支持自动获取类别
  - 支持预览模式（测试用）
  - 支持完整模式（正式爬取）
  - 已成功获取第一批10个非遗项目

- **ihchina_crawler_v3.py** - 完整版爬虫V3
  - 包含子项抓取功能
  - 多种自动类别获取策略
  - 详细的错误处理

- **ihchina_crawler_v3_working.py** - 工作版爬虫V3
  - 调试版本

- **clean_simple.py** - 简化版清洗脚本
  - 处理原始数据
  - 标准化字段格式
  - 生成清洗后的文档

- **chunk_simple.py** - 简化版分块脚本
  - 将文档分为基本信息、地区信息、组织信息
  - 生成适合知识图谱构建的chunks

### 2. 数据文件（data/）
- **raw/** - 原始爬取数据
  - category_0/ - 全部数据
  - category_1/ - 第一批数据（2006年）
  
- **clean/documents/** - 清洗后的文档（10个）
  - JSON格式，每个项目一个文件
  
- **chunks/** - 分块后的数据（30个chunks）
  - JSONL格式，每行一个块
  - 包含完整的provenance字段

### 3. 交付文档
- **DELIVERY_C_D_CHUNKS_2026-09-04.md** - 给C和D成员的交付说明
- **GIT_PUSH_INSTRUCTIONS.md** - Git推送指南
- **README_任务B_代码说明.md** - 本说明文档

## 使用方法

### 1. 预览模式（推荐先测试）
```python
# 在爬虫脚本中设置
PREVIEW_MODE = True
```
运行：`python crawler/ihchina_crawler_simple.py`

### 2. 完整模式
```python
# 在爬虫脚本中设置
PREVIEW_MODE = False
```
运行：`python crawler/ihchina_crawler_simple.py`

### 3. 数据清洗
```bash
python crawler/clean_simple.py
```

### 4. 数据分块
```bash
python crawler/chunk_simple.py
```

## 已完成工作

1. ✅ **爬虫开发** - 成功获取第一批10个非遗项目数据
2. ✅ **数据清洗** - 处理并标准化数据格式
3. ✅ **数据分块** - 生成30个chunks，包含provenance字段
4. ✅ **交付准备** - 准备完整的交付文档和数据

## 数据统计

- **原始项目数**: 10个（第一批国家级非遗）
- **清洗后文档数**: 10个
- **分块数**: 30个（每个项目3个块）
- **分块类型**: 
  - basic_info: 10个
  - region_info: 10个
  - organization: 10个

## 项目列表

交付的项目包括：
1. 京绣 (Ⅰ-FRZX-1)
2. 苏绣 (Ⅰ-FRZX-2)
3. 无锡精微绣 (Ⅰ-FRZX-3)
4. 南通仿真绣 (Ⅰ-FRZX-4)
5. 扬州刺绣 (Ⅰ-FRZX-5)
6. 上海绒绣 (Ⅰ-FRZX-6)
7. 顾绣 (Ⅰ-FRZX-7)
8. 蜀绣 (Ⅰ-FRZX-8)
9. 汴绣 (Ⅰ-FRZX-9)
10. 汉绣 (Ⅰ-FRZX-10)

## 下一步

1. 将代码推送到Gitee（参考GIT_PUSH_INSTRUCTIONS.md）
2. 将chunks数据交付给C和D成员
3. 扩展爬取更多批次的非遗数据

## 注意事项

- 所有数据均来自官方公开渠道
- 包含完整的provenance字段，便于数据追溯
- 预览模式用于测试，完整模式用于正式爬取
- 如需获取更多数据，请设置PREVIEW_MODE = False