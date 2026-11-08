# B交付A：雷玺功
chunks字段及既有ID冻结。引用键为chunk_id，正文为content，标题为source_name，来源为source_url；无title/source字段。Evidence.source_id应填chunk_id，回退evidence_id也须为切片ID，不能填document_id。
benchmark/routing_questions.jsonl含15题，三类各5；答案见benchmark.jsonl。供A对比V1/V2，题型不等于路由。已回查，待人工复核。结构或ID变化先同步；内容变化更新索引、复核题库并重跑。
