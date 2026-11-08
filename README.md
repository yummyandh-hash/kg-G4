# 非遗智谱 · AP-ICH-GraphRAG

面向中国非物质文化遗产的自适应 GraphRAG 智能问答系统。项目由五名成员完成，包含数据采集、知识图谱构建、检索、路由、问答和 Web 展示。

Stage2 已合入 `main`。代码、数据、测试和文档位于同一分支；完整在线查询仍需配置外部服务并进行端到端验收。

[成员分工](CONTRIBUTORS.md) · [测试说明](docs/TESTING.md) · [审查索引](docs/REPOSITORY_REVIEW.md) · [协作指南](CONTRIBUTING.md) · [迁移历史](docs/history/README.md)

## 项目结构

| 内容 | 目录 | 负责人 |
| --- | --- | --- |
| 查询分析、路由、编排和评估 | [orchestration/](orchestration/) | A |
| 采集、清洗、分块及语料 | [crawler/](crawler/)、[data/](data/)、[数据说明](docs/data_schema.md) | B |
| 实体关系抽取、清洗和图谱导出 | [C 模块](kg-g5-stage1-9.4-lmy/c_module/) | C |
| 向量和图谱检索 | [retrieval/](retrieval/) | D |
| Web/API、上下文与解释 | [api/main.py](api/main.py) | E |

## 安装与测试

推荐 Python 3.10 或 3.12。首次获取代码和安装依赖：

```bash
git lfs install
git clone https://github.com/yummyandh-hash/kg-G4.git
cd kg-G4
python -m venv .venv
# 激活虚拟环境：Windows 用 .venv\Scripts\activate，macOS/Linux 用 source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

四个历史图谱 JSON 使用 Git LFS；若用 ZIP 交付，请确认所需文件不是 LFS 指针。根目录 `data/chunks/chunks.jsonl` 是向量检索输入。

测试包含隔离外部服务的 API 契约测试，不能代替真实数据库和模型的在线验证。C 模块测试和验证边界见 [测试说明](docs/TESTING.md)。

## 配置与启动

1. 将 `.env.example` 复制为 `.env`，填写 Neo4j 地址、用户名和密码，以及兼容 Chat Completions 的模型服务地址、模型名和密钥。请使用自己的服务配置。
2. 准备 Neo4j 实例并导入项目图谱数据；C 模块的抽取和 Cypher 导出入口见 [C 模块说明](kg-g5-stage1-9.4-lmy/c_module/README_C_MODULE.md)。数据库配置有效不代表已导入图谱。
3. 运行 `python -m uvicorn api.main:app --host 127.0.0.1 --port 8000`，打开 `http://127.0.0.1:8000/`。API 入口为 `POST /query`，请求示例：`{"question": "什么是蜀绣？"}`。

首次启动需要获取 `all-MiniLM-L6-v2` 模型，并根据完整分块数据构建向量索引，可能耗时较长。Neo4j、模型服务、网络和证书均需正常可用。项目也提供 Dockerfile 和 Compose 配置；容器构建及在线查询须在目标环境验证。

## 已知验证范围

2026-11-08 的本机小样本试运行中，模型成功加载，向量检索返回 3 条证据；Neo4j 连接和模型服务 SSL 握手失败，完整在线查询尚未通过。自动测试和最新结果以 [GitHub Actions](https://github.com/yummyandh-hash/kg-G4/actions/workflows/ci.yml) 为准。

项目迁移自 [Gitee](https://gitee.com/tjuymh/kg-g5)。分支及提交历史的保留范围和原平台记录限制见 [迁移历史](docs/history/README.md)。
