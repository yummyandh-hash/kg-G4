# B模块数据字段映射问题解决方案说明

## 1. 问题概述

在Codex全仓审计中发现B模块数据字段存在以下问题：
- source_category当前样本大量为"第一批"
- 部分KG样本出现heritage_category=传统舞蹈、raw_category_name=传统美术的语义错位
- 数据清洗过程中字段映射不完整

## 2. 根因分析

通过代码审查发现主要问题在于`clean_simple.py`中的`normalize`函数：

```python
def normalize(raw: dict, category_id: str, retrieved_at: str) -> dict:
    """规范化数据"""
    # 从实际数据中提取字段
    name = raw.get("title", "")
    project_num = raw.get("project_num", "")
    province = raw.get("province", "")
    unit = raw.get("unit", "")
    protect_unit = raw.get("protect_unit", "")
    content = raw.get("content", "")

    doc = {
        "name": name,
        "aliases": [],
        "number": project_num,
        "category": "第一批",  # 硬编码问题
        "batch": "2006",       # 硬编码问题
        "region": province,
        "region_norm": province.replace("省", "").replace("市", "").replace("县", ""),
        "org": unit or protect_unit,
        "body": content,
        "source_url": f"https://www.ihchina.cn/project/{raw.get('id', '')}",
        "document_id": "",
        "chunk_source_page": int(category_id),
        "retrieved_at": retrieved_at,
    }

    # 生成document_id
    key = doc["number"] or doc["name"]
    doc["document_id"] = f"ihchina_{hashlib.md5(key.encode('utf-8')).hexdigest()[:12]}"
    return doc
```

**问题根源**：
1. `category`字段被硬编码为"第一批"
2. `batch`字段被硬编码为"2006"
3. 缺少`heritage_category`和`raw_category_name`字段的映射
4. 没有从`project_data`中提取实际的类别信息

## 3. 解决方案

已对`clean_simple.py`进行以下修改：

```python
def normalize(raw: dict, category_id: str, retrieved_at: str) -> dict:
    """规范化数据"""
    # 从实际数据中提取字段
    name = raw.get("title", "")
    project_num = raw.get("project_num", "")
    province = raw.get("province", "")
    unit = raw.get("unit", "")
    protect_unit = raw.get("protect_unit", "")
    content = raw.get("content", "")

    # 从project_data中提取类别信息
    project_data = raw.get("project_data", {})
    actual_category = project_data.get("type", "第一批")  # 使用实际的type字段
    actual_batch = project_data.get("batch", "2006")

    doc = {
        "name": name,
        "aliases": [],
        "number": project_num,
        "category": actual_category,  # 使用实际的类别
        "batch": actual_batch,       # 使用实际的批次
        "region": province,
        "region_norm": province.replace("省", "").replace("市", "").replace("县", ""),
        "org": unit or protect_unit,
        "body": content,
        "source_url": f"https://www.ihchina.cn/project/{raw.get('id', '')}",
        "document_id": "",
        "chunk_source_page": int(category_id),
        "retrieved_at": retrieved_at,
        "heritage_category": actual_category,  # 添加heritage_category字段
        "raw_category_name": actual_category  # 添加raw_category_name字段
    }

    # 生成document_id
    key = doc["number"] or doc["name"]
    doc["document_id"] = f"ihchina_{hashlib.md5(key.encode('utf-8')).hexdigest()[:12]}"
    return doc
```

## 4. 实施步骤

### 4.1 重新运行数据清洗

1. **清理现有数据**：
   ```bash
   # 删除旧的清洗数据
   rm -rf "D:\大三上课程\知识工程综合实践\王鑫项目\kg-g5\worktrees\kg-g5-feat-b-crawler\data\clean\documents\*"
   rm -rf "D:\大三上课程\知识工程综合实践\王鑫项目\kg-g5\worktrees\kg-g5-feat-b-crawler\data\chunks\*"
   ```

2. **重新运行清洗脚本**：
   ```bash
   python crawler/clean_simple.py
   ```

3. **重新运行分块脚本**：
   ```bash
   python crawler/chunk_simple.py
   ```

### 4.2 验证数据正确性

验证以下字段是否正确映射：

```python
# 验证示例
import json

# 检查清洗后的文档
with open("data/clean/documents/ihchina_00175424c493.json", "r", encoding="utf-8") as f:
    doc = json.load(f)
    print(f"项目名称: {doc['name']}")
    print(f"类别: {doc['category']}")  # 应该显示实际的非遗类别
    print(f"批次: {doc['batch']}")    # 应该显示实际的批次
    print(f"heritage_category: {doc['heritage_category']}")
    print(f"raw_category_name: {doc['raw_category_name']}")

# 检查分块数据
with open("data/chunks/chunks.jsonl", "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i < 5:  # 检查前5个块
            chunk = json.loads(line)
            print(f"\n块ID: {chunk['chunk_id']}")
            print(f"类别: {chunk['source_category']}")
            print(f"heritage_category: {chunk.get('heritage_category', 'N/A')}")
            print(f"raw_category_name: {chunk.get('raw_category_name', 'N/A')}")
```

## 5. 预期效果

修改后，数据将正确反映：

- **source_category**：从"第一批"变为实际的非遗类别（如"传统美术"、"传统舞蹈"等）
- **heritage_category**：与source_category保持一致
- **raw_category_name**：与source_category保持一致
- **batch**：从"2006"变为实际的批次信息

## 6. 影响范围

- **正面影响**：KG样本的类别信息将更加准确，避免语义错位
- **兼容性**：C模块的实体规范化处理将基于正确的类别信息
- **下游影响**：D模块的检索和A模块的自适应路由将基于更准确的数据

## 7. 后续建议

1. **定期验证**：每次数据更新后验证字段映射的正确性
2. **监控指标**：添加数据质量监控，检查类别分布的合理性
3. **文档更新**：更新数据字典，明确各字段的含义和来源

如需进一步协助或有任何疑问，请随时联系。