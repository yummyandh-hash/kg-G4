# 任务 A Stage 2 代码说明

## 1. 目标

Stage 2 的 A 模块目标是把 Stage 1 的固定规则路由升级为轻量 Adaptive Router V2。

核心思路：

1. 保留 Stage 1 已有的 `QueryAnalyzer` 和 `ComplexityScorer`。
2. 对同一条问题分别强制执行 Vector Retrieval 和 Graph Retrieval。
3. 根据实际检索结果或人工标注得到 `best_route`。
4. 用轻量逻辑回归式模型学习路由决策。
5. 输出 `selected_route`、`confidence` 和 `reason`。
6. 做 Router V1 和 Router V2 的对比实验。

本阶段不引入复杂大模型训练、强化学习或神经网络。

## 2. 冻结接口

### 2.1 Retriever 调用入口

D 侧 Retriever 统一使用：

```python
retrieve(query, context, top_k)
```

A 侧通过 `orchestration.retriever_adapters.DRetrieverAdapter` 调用 D 侧 Retriever。

### 2.2 relation_path 标准

Stage 2 冻结标准为字典对象数组：

```python
relation_path = [
    {
        "source": "源实体ID或名称",
        "relation": "关系名",
        "target": "目标实体ID或名称",
    }
]
```

说明：

1. GraphRetriever 的关系类结果应稳定返回该结构。
2. VectorRetriever 没有关系路径时可以返回 `None` 或 `[]`。
3. A 侧会统一归一化为 `[]` 或上述字典数组。
4. 旧格式 `A --[R]--> B` 和 `["A", "R", "B"]` 仍可兼容解析，但不作为 Stage 2 标准。

## 3. 主要文件

### 3.1 Router V1

文件：

```text
orchestration/adaptive_router.py
```

作用：

基于人工规则和固定阈值选择 `vector` 或 `graph`。

### 3.2 Router V2

文件：

```text
orchestration/adaptive_router_v2.py
```

主要类：

```python
QueryFeatureExtractor
RoutingTrainingExample
AdaptiveRouterV2
```

能力：

1. 从 query 中提取 Stage 1 特征。
2. 根据 benchmark 标签训练轻量路由模型。
3. 未训练时自动 fallback 到 Router V1。
4. 支持保存和加载模型参数。

### 3.3 Benchmark

文件：

```text
orchestration/routing_benchmark.py
```

主要类和函数：

```python
DualRouteBenchmark
RoutingBenchmarkQuery
RoutingBenchmarkRecord
choose_best_route
training_examples_from_records
train_router_v2_from_records
compare_router_decisions
summarize_router_comparison
save_benchmark_records
load_benchmark_records
```

能力：

1. 对同一个问题强制执行 `vector` 和 `graph` 两路检索。
2. 记录两路 evidence、耗时和错误。
3. 生成 `best_route` 标签。
4. 保存和读取 benchmark 结果。
5. 训练 Router V2。
6. 汇总 V1/V2 对比结果。

### 3.4 实验入口

文件：

```text
orchestration/routing_experiment.py
```

运行方式：

```bash
python -m orchestration.routing_experiment \
  --queries data/router_benchmark_queries.sample.jsonl \
  --records-out outputs/router_benchmark_records.jsonl \
  --model-out outputs/router_v2.json \
  --summary-out outputs/router_summary.json \
  --top-k 5
```

query 文件支持 JSONL：

```json
{"query": "什么是蜀绣？", "expected_route": "vector"}
{"query": "蜀绣和四川有什么关系？", "expected_route": "graph"}
```

也支持一行一个普通问题，但普通问题没有人工标签，会使用启发式方法生成 `best_route`。

### 3.5 Stage 1 / Stage 2 服务构建

文件：

```text
orchestration/stage1.py
```

主要函数：

```python
build_stage1_retriever(...)
build_stage1_query_service(...)
```

默认仍使用 Router V1：

```python
build_stage1_query_service()
```

使用 Router V2：

```python
build_stage1_query_service(router_version="v2")
```

使用已保存的 Router V2 模型：

```python
build_stage1_query_service(
    router_version="v2",
    router_model_path="outputs/router_v2.json",
)
```

也可以通过环境变量：

```text
KG_G5_ROUTER_VERSION=v2
KG_G5_ROUTER_V2_MODEL=outputs/router_v2.json
```

## 4. 测试

当前新增和更新的测试包括：

```text
tests/test_adaptive_router_v2.py
tests/test_routing_benchmark.py
tests/test_routing_experiment.py
tests/test_stage1_routing.py
tests/test_context.py
tests/test_service.py
tests/test_explainability.py
```

运行：

```bash
python -m pytest tests
```

当前结果：

```text
36 passed
```

## 5. 当前完成度

已完成：

1. Router V2 基础模型。
2. V1 fallback。
3. query 特征提取。
4. 双路检索 benchmark。
5. benchmark 结果保存和加载。
6. Router V2 模型保存和加载。
7. V1/V2 对比汇总。
8. relation_path 字典数组标准化。
9. 单元测试覆盖。

待联调：

1. 使用真实 VectorRetriever 和 GraphRetriever 跑 benchmark。
2. 和 D 确认真实 relation_path 字段稳定输出。
3. 和 E 确认 graph_nodes / graph_edges 页面渲染正常。
4. 准备一批人工标注的 routing benchmark queries。
