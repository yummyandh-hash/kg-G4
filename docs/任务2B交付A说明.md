# 任务2交付A说明

## 用途
本模块为A模块提供引用校验服务，用于验证AI回答的事实是否被原文支撑，作为证据充足度判断的依据。

## 实际接口
```python
from citation_service import CitationService

# 初始化服务
service = CitationService("data/chunks/chunks.jsonl")

# 获取证据信息
evidence = service.get_evidence("chunk_id")

# 验证claim
result = service.verify_claim(claim, ["chunk_id1", "chunk_id2"])
```

## 输入输出
- **输入**：claim（事实陈述）、chunk_ids（引用的chunk ID列表）
- **输出**：包含label（SUPPORTED/PARTIALLY_SUPPORTED/UNSUPPORTED）、confidence（0-1）、reason、evidences等字段

## 标签和分数含义
- **SUPPORTED**：事实被证据完全支持（confidence ≥ 0.8）
- **PARTIALLY_SUPPORTED**：事实被部分支持（0.5 ≤ confidence < 0.8）
- **UNSUPPORTED**：事实无依据或被证据反对（confidence < 0.5）

## A的接入方法
1. 调用verify_claim接口获取校验结果
2. 根据label和confidence判断证据充足度
3. 将UNSUPPORTED的回答标记为低可信度

## 限制
- 需要预先构建chunks索引
- 依赖NLI模型和LLM服务（当前为模拟实现）
- 不支持实时模型更新，需重新初始化服务

## 联系方式
如有问题，请联系B模块负责人：王鑫