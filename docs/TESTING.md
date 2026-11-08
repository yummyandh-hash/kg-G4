# 测试范围与复现

## main 基线

~~~bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
~~~

两个测试文件为 tests/test_models.py、tests/test_query_analysis.py，参数化后 11 个用例。独立副本已实测 11 passed（Python 3.13.9，pytest 8.4.2）。CI 用 Python 3.10 / 3.12 运行同一套测试，实际日志见 Actions。

覆盖数据模型、Retriever 协议、查询类型和复杂度顺序，不连接 Neo4j、调用 LLM 或下载模型。

## Stage2 的独立范围

integration/stage2-base 的 tests/ 包含路由、调度、上下文、引用、评估和 API 测试，但不能用 main 的绿灯代替完整系统验收。

tests/test_api.py、tests/test_stage2_contract.py 导入真实 API 服务，会构建检索器，需要模型、数据与 Neo4j 等环境。pytest.ini 只收集 tests/，不代表 retrieval/test_retriever.py 的手工脚本已经运行。

审计发现的待办：
- requirements.txt 写 httpx2，API 测试使用 httpx，需模块维护者确认修正并验证安装。
- retrieval/llm_client.py 导入 openai，但依赖未显式声明。
- Dockerfile 依赖未随仓库提供的 torch-cache/...whl，不能声称克隆后即可构建。
- 完整在线测试需要记录模型、数据库、数据版本、配置名称及实际结果，不能提交密钥。

不通过删除测试、静默跳过在线用例或虚报全量通过来消除这些待办。

## PR 测试记录

提供命令、分支或提交、实际通过/失败数量和未验证范围。截图只作补充，以可重跑命令和 Actions 日志为主要证据。
