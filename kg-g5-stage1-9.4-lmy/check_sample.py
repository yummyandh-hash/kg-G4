import random
from c_module.pipeline import run_pipeline
from c_module.extractor import extract_chunks_deduped, load_chunks

chunks_path = "data/chunks/chunks.jsonl"
output_dir = "outputs/c_module"

quality_report = run_pipeline(chunks_path, output_dir)
chunks = load_chunks(chunks_path)
result = extract_chunks_deduped(chunks)

entities = result.entities
relations = result.relations

print("====随机抽取15个实体====")
for e in random.sample(entities, 15):
    print(f"{e.name} | {e.entity_type}")

print("\n====随机抽取10条关系====")
for r in random.sample(relations, 10):
    src_id = r.source_entity_id
    dst_id = r.target_entity_id
    rel = r.relation_type
    print(f"{src_id}  --{rel}--> {dst_id}")

print("\n====质量统计摘要====")
print(f"去重后实体数:{quality_report['deduped_entity_count']}, 去重后关系数:{quality_report['deduped_relation_count']}")
risk = quality_report["risk_report"]
print(f"文化碎片风险数:{risk['cultural_fragment_count']}")
if risk["cultural_fragment_samples"]:
    print(f"可疑文化元素样例:{risk['cultural_fragment_samples'][:10]}")
