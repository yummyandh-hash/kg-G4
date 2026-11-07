# 非遗智谱 · AP-ICH-GraphRAG

面向中国非物质文化遗产的自适应 GraphRAG 智能问答系统，五人知识工程课程实践项目。

[![Repository CI](https://github.com/yummyandh-hash/kg-G4/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/yummyandh-hash/kg-G4/actions/workflows/ci.yml)

[贡献分工](CONTRIBUTORS.md) · [协作指南](CONTRIBUTING.md) · [测试范围](docs/TESTING.md) · [助教审查索引](docs/REPOSITORY_REVIEW.md) · [Gitee 历史](docs/history/README.md)

## 成果入口与分支现状

| 入口 | 实际内容 |
| --- | --- |
| [Stage2 集成分支](https://github.com/yummyandh-hash/kg-G4/tree/integration/stage2-base) | API/Web、路由、检索适配、证据处理和解释的集成候选，是功能审查的主要入口 |
| main | 迁移时的较早代码基线，加本次仓库治理；不能据此认定 Stage2 已合入 main |
| develop | 保留的开发分支，后续通过真实 PR 集成 |
| [Gitee 原仓库](https://gitee.com/tjuymh/kg-g5) | 原始协作记录的权威来源，访问可能需要权限 |
| [迁移归档](https://github.com/yummyandh-hash/kg-G4/releases/tag/gitee-migration-archive) | 原始项目 Git bundle、哈希映射、注明完整性范围的 PR/活动网页采集 |

## 模块与职责

以下功能入口对应真实 Stage2 文件。存在文件不等于线上端到端验收已完成。

| 模块 | 成员 | 代码 |
| --- | --- | --- |
| 查询分析、复杂度、自适应路由、编排与评估 | A | [orchestration/](https://github.com/yummyandh-hash/kg-G4/tree/integration/stage2-base/orchestration) |
| 采集、分块、数据文档 | B | [crawler/](crawler)、[data/](data)、[数据说明](docs/data_schema.md) |
| 抽取、清洗、Neo4j 图谱 | C | [C 模块](https://github.com/yummyandh-hash/kg-G4/tree/integration/stage2-base/kg-g5-stage1-9.4-lmy) |
| Vector / Graph 检索算法 | D | [retrieval/](https://github.com/yummyandh-hash/kg-G4/tree/integration/stage2-base/retrieval) |
| Web/API、上下文、可解释输出 | E | [api/main.py](https://github.com/yummyandh-hash/kg-G4/blob/integration/stage2-base/api/main.py) |

编排负责分析问题、选择检索路径、调用检索器、整理证据并返回回答与来源。A 负责调度和适配，D 负责具体 Retriever 算法。

## 克隆与验证

四个历史大 JSON 使用 Git LFS，需要这些输出时先安装 Git LFS。

~~~bash
git lfs install
git clone https://github.com/yummyandh-hash/kg-G4.git
cd kg-G4
python -m venv .venv
# 激活 .venv 后：
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
~~~

main 当前有 11 个单元测试，不连接数据库、不调用 LLM、不下载嵌入模型。CI 使用 Python 3.10 / 3.12，以 Actions 实际记录为准。

查看完整系统时，在独立克隆中切换 integration/stage2-base。该分支的实际 API 测试依赖模型、Neo4j、数据和配置；依赖声明与 Docker 本地 wheel 问题尚待验收，详见[测试说明](docs/TESTING.md)。main 的绿灯不能替代 Stage2 在线验收。

## 协作与历史

每项新变更使用独立分支、真实 PR、测试记录和清楚的提交说明。迁移基线保留 17 个项目分支、138 个项目提交及 34 个 PR 代码标签；新增治理提交另计。LFS 转换改变了 GitHub SHA，原作者、时间和提交关系已核验，原始对象保存在归档 bundle。

Gitee 网页索引覆盖 17 个 PR 编号，但评论和审核不是已验证的无损导出；10 条活动快照不代表全部历史推送。新增 GitHub PR、Issue 与审核使用真实当前身份和时间，不冒充原平台历史行为。

## 许可与数据

项目级代码许可证尚待团队确认，当前没有 LICENSE。公开可访问不代表已选择开源许可证。采集网页、数据、模型和依赖的权利与许可分别核实，不能自动套用未来的代码许可证。

课程没有明确评分细则；本仓库提供可核查的工程证据，不承诺评分结果。
