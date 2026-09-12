# B→A字段冻结与路由测试交接

负责人：雷玺功；日期：2026-09-12。A已反馈Router V2和引用校验接入完成。本说明确认B侧契约，未修改A代码或宣称已在本地验证新版链路。

1. data/chunks/chunks.jsonl当前字段结构与既有ID冻结为B-chunks-v1。全量27375条记录，11个字段均为字符串，chunk_id非空且唯一。完整字段、数据哈希见benchmark/chunk_contract.json。content为正文，可能含HTML实体；source_name是显示标题，source_url为网页来源。不存在title、source字段。
2. 引用校验真实键为chunk_id，例如ihchina_0098187ad030_content_3。A优先取Evidence.source_id时，应将chunk_id映射到source_id；evidence_id回退值也必须是真实chunk_id。document_id为文档ID，不能用于切片查询。非空但错误的source_id不会自动触发回退。图证据需展开为来源切片，不能直接用节点ID查询B索引。
3. benchmark/routing_questions.jsonl正式交付15道当前语料可定位的问题，三类各5道。A按qid关联benchmark.jsonl获取参考答案及证据，自行整理Router V1/V2路由标签。question_category是题型，不是最优路由；只将question送入被测系统，不能把题型、答案或黄金证据作为提示。

正式交付不代表人工审定：全部题目保留pending_human_cross_review，待B与A/D交叉作答、多跳路径验证。旧版枚举与summary兼容问题仍需A确认；本次独立问题清单不改A旧契约，也不强行转换或删题。

本次不改变chunks内容、字段或ID。已有切片ID保留；新增切片保证唯一，不按文件行号编号。重分块、ID规则及字段名称、类型、含义变化须先同步A/D。

仅优化内容且不改变契约时，A通常无需改接口代码，但须刷新受影响的向量/图谱/证据索引与缓存；B复核答案和证据、更新语料哈希后再重跑benchmark。旧索引上的实验不代表新语料效果。已知类别/批次字段错位仍不作为本题库答案依据。

复现：python benchmark/validate_benchmark.py；随后python benchmark/export_routing_handoff.py。后者检查全量字段、ID唯一性、语料版本和题目引用，导出问题清单及冻结快照。重建题库后须重新校验及导出。
