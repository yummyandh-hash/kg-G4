"""Checked B-to-A export; no expected router labels are invented."""
import json
from collections import Counter
from build_benchmark import HERE, CORPUS, digest
from read_example import load_questions

FIELDS = 'chunk_id chunk_type content source_name source_category source_region source_org source_url retrieved_at document_id source_batch'.split()

def main():
    chunks = [json.loads(x) for x in CORPUS.read_text(encoding='utf-8').splitlines() if x.strip()]
    assert all(set(c)==set(FIELDS) and all(isinstance(c[k],str) for k in FIELDS) for c in chunks)
    ids = {c['chunk_id'] for c in chunks}
    assert len(ids)==len(chunks) and all(c['chunk_id'] and c['content'] for c in chunks)
    manifest = json.loads((HERE/'manifest.json').read_text(encoding='utf-8'))
    assert digest(CORPUS)==manifest['corpus_sha256'], 'Revalidate changed corpus'
    assert digest(HERE/'benchmark.jsonl')==manifest['benchmark_sha256']
    questions = load_questions()
    assert all(set(q['gold_evidence']) <= ids for q in questions)
    inputs = [{k:q[k] for k in ('qid','question','question_category','review_status')} for q in questions]
    output = HERE/'routing_questions.jsonl'
    output.write_text(''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in inputs),encoding='utf-8')
    contract = {'schema_version':'B-chunks-v1-frozen-2026-09-12','owner':'雷玺功',
        'corpus_path':'data/chunks/chunks.jsonl','corpus_sha256':digest(CORPUS),'row_count':len(chunks),
        'fields':{k:'string' for k in FIELDS},'citation_lookup_field':'chunk_id',
        'display_title_field':'source_name','source_url_field':'source_url',
        'absent_fields':['title','source','source_id','evidence_id'],
        'evidence_mapping':{'source_id':'chunk_id','evidence_id':'chunk_id (recommended fallback)','content':'content','source_url':'source_url'},
        'routing_inputs_sha256':digest(output),'question_count':len(inputs),
        'categories':dict(Counter(q['question_category'] for q in inputs)),
        'route_labels':'由A整理；题型不等于期望路由',
        'change_policy':'字段名称、类型、含义及既有切片ID冻结；结构或ID规则改变先同步A/D，内容变化需更新相关索引、复核题库并重跑。'}
    (HERE/'chunk_contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Checked {len(chunks)} chunks; exported {len(inputs)} routing questions')

if __name__ == '__main__':
    main()
