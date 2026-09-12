# 任务3交付A
B负责人：雷玺功。题库为benchmark/benchmark.jsonl，共15题，单跳、多跳、归纳各5题。qid标识题目，gold_answer为参考答案，gold_evidence为切片ID，details保存原文及来源；答案要点逐项关联证据。
运行python benchmark/read_example.py读取；用validate_benchmark.py校验。语料版本、哈希见manifest.json。A仅将问题送入系统，参考答案留作评分，按题型统计答案质量与证据召回。尚待B与A/D交叉作答、Neo4j路径验证及旧接口映射确认，当前非人工审定金标。
