# 任务2交付E说明

## 引用展示所需字段
```json
{
  "chunk_id": "ihchina_00175424c493_name",
  "evidence_text": "项目名称：朝鲜族农乐舞（象帽舞）...",
  "source_url": "https://www.ihchina.cn/project/12962",
  "source_name": "朝鲜族农乐舞（象帽舞）",
  "source_category": "第一批",
  "source_region": "吉林省延边朝鲜族自治州",
  "source_batch": "2006"
}
```

## 原文与URL查询方式
- 通过chunk_id调用get_evidence接口获取完整证据信息
- source_url字段提供原始页面链接
- evidence_text字段显示证据片段

## 异常及无依据提示
- **UNSUPPORTED**：显示"该事实未被证据支持"，提供原始链接
- **PARTIALLY_SUPPORTED**：显示"该事实部分被支持"，标注支持和不支持的证据
- **模型不可用**：显示"引用验证服务暂时不可用"，建议人工核查
- **证据缺失**：显示"找不到对应的证据片段"

## 展示建议
1. 在回答后添加引用标记
2. 支持点击查看原文片段
3. 对UNSUPPORTED的回答添加警告标识
4. 提供批量验证结果展示

## 限制
- 需要预先构建chunks索引
- 依赖NLI模型服务（当前为模拟实现）
- 不支持实时模型更新

## 联系方式
如有问题，请联系B模块负责人：王鑫