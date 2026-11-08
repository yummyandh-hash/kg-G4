# 测试与复现范围

## 单元和接口测试

在仓库根目录安装 `requirements-dev.txt` 后运行：

```bash
python -m pytest tests -q
```

根目录测试覆盖查询分析、路由、检索调度、上下文、引用、评估、服务和 API 契约。API 测试使用受控的检索器和生成器，不连接真实 Neo4j 或模型服务。CI 在 Python 3.10 和 3.12 上运行；实际版本和结果以 Actions 为准。

C 模块测试可单独运行：

```bash
cd kg-g5-stage1-9.4-lmy
python -m pytest tests/test_c_module.py -q
```

根目录的 pytest 配置不会自动运行上述 C 模块测试，也不代表 `retrieval/test_retriever.py` 的手工检索脚本已运行。

## 在线验证

真实运行需配置 `.env`、准备 Neo4j 和图谱数据、提供可访问的模型服务，并允许首次下载嵌入模型。启动方法见 [README](../README.md)。

2026-11-08 本机使用 3 条匹配语料的小样本测试：嵌入模型加载并返回 3 条向量证据；Neo4j 连接失败，模型服务发生 SSL 错误。完整数据集和端到端回答没有通过验收。排查后应记录运行环境、数据版本、测试问题及实际结果，勿提交密钥。

模型会在启动时为分块构建向量，完整语料可能需要较长时间。容器构建仍需在有 Docker 引擎和网络的环境验证。
