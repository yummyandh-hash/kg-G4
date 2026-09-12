# B Stage2任务3（负责人：雷玺功）

15题（单跳、多跳、归纳各5），8份项目正文；便利抽样的小型试评题库，不代表全部非遗门类。所有题目以本地材料为范围，保留待人工交叉复核状态。

从B工作目录运行（仅Python标准库）：
```powershell
python benchmark/build_benchmark.py
python benchmark/validate_benchmark.py
python benchmark/read_example.py
```
build脚本保存逐题策划与答案要点，生成JSONL和语料manifest。修改语料后不得直接复用旧评测结果；哈希变化需重新审题。JSONL是唯一消费数据源，没有另外维护旧答案文件。

字段：qid唯一；question_category为single_hop/multi_hop/summary，与A路由标签分离；gold_answer及answer_points给出答案和逐点证据；gold_evidence是ID数组；gold_evidence_details包含文档ID、来源、抓取时间、原样content与Python字符区间[start,end)。HTML实体不解码、不删除，transformation=none。展示层可解码，但回查以原串为准。

gold_relation_path为正文推导的有序边，depends_on引用此前步骤索引，后一步使用前一步实体；不是已验证的Neo4j边类型，也不意味着必须使用图检索。多跳题包括同文档跨句实体识别、指代连接与属性查询，未覆盖广泛跨文档多跳。答案要点关联检查不能自动判定蕴含关系。

evidence_alternatives自动收录全文完全相同的切片；语义等价但文字不同的证据尚未穷举，需人工裁定并版本化。Evidence Recall@K按黄金证据组命中比例计算，先截取原始前K条再计算命中，重复及无效记录占名额；完全相同替代ID可命中同组。相较旧示例的先去重口径，本次显式修正预算计算；旧结果须使用同一口径重算才可比较。按题型分别平均，同时报告总体；答案质量按要点评审，不能直接用字符串完全匹配代替语义判断。引用支持度由任务2另评。

新增评分命令：`python benchmark/score_evidence.py predictions.jsonl --k 5 --output report.json`。输入每行格式为`{"qid":"ich_bench_01","evidences":[{"source_id":"真实chunk_id","evidence_id":"备用chunk_id"}]}`，evidences必须保留返回排名。输出严格与等价召回、无效ID、未命中证据组及分题型宏平均。source_id非空时不绕过错误值；缺少某题输出计零并列明，重复/未知qid报错。分数仅评价引用ID，不验证返回文本蕴含关系。完全相同正文的替代证据也应结合来源上下文人工审定；严格值始终并列保留。A的真实预测文件尚未提供，本次没有重算或宣称提高其召回。测试：`python -m unittest discover -s benchmark -p test_score_evidence.py`。

评测仅把question送入系统，答案、黄金证据、路径不得加入提问或检索索引，以免泄漏。三系统应固定语料版本、问题、生成模型和评分口径；本交付未运行三系统实验。

旧文档要求ich_bench_v1.json及single_fact/relation/multi_hop；本次未发现A的Benchmark读取器。未修改旧接口，也未强制把summary映射为multi_hop。A确认分类映射后再按实际读取器导出旧格式，不能默默删掉总结题。

可靠性：不使用已知错位的source_category/source_batch作答案；所有证据选自detail_content，脚本回查clean正文及来源URL。没有重新爬取或回访网页，因此验证的是本地材料一致性。EvidenceIndex会转换正文HTML并覆盖重复ID，本任务采用严格标准库读取并检查重复ID，保留原串，不调用其评分作为金标。

尚待：B与A/D逐题独立作答、消除歧义及核对题型；C/D在Neo4j验证路径（未发现可直接使用的本地图谱导出，未连接数据库）；A确认读取映射。review_status均为pending_human_cross_review，不冒充人工金标。跨题共享项目与事实，仅作统一小样本试评，不应用于训练/测试独立性的声明。
