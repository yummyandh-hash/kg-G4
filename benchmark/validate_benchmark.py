"""Validate provenance and structure, not semantic truth or human approval."""
import json
import re
from collections import Counter
from pathlib import Path
from build_benchmark import ROOT, HERE, CORPUS, digest

REQUIRED = {'qid','question','gold_answer','question_category','gold_evidence',
            'gold_evidence_details','gold_relation_path','notes','review_status','answer_points'}

def check_question(q, index):
    errors = []
    def check(ok, message):
        if not ok:
            errors.append(f"{q.get('qid','?')}: {message}")
    check(REQUIRED <= q.keys(), 'missing fields')
    if not REQUIRED <= q.keys():
        return errors
    ids = q['gold_evidence']
    check(bool(ids) and len(ids) == len(set(ids)), 'empty/duplicate gold evidence')
    check(q['question_category'] in ('single_hop','multi_hop','summary'), 'category')
    check(bool(q['question'].strip()) and bool(q['gold_answer'].strip()), 'empty question/answer')
    details = q['gold_evidence_details']
    check([d['chunk_id'] for d in details] == ids, 'detail IDs mismatch')
    for d in details:
        r = index.get(d['chunk_id'])
        check(r is not None, 'unknown evidence ID')
        if r is None:
            continue
        check(d['document_id'] == r['document_id'], 'document mismatch')
        check(d['source_url'] == r['source_url'] and bool(d['source_url']), 'URL mismatch')
        check(d['retrieved_at'] == r['retrieved_at'], 'timestamp mismatch')
        check(d['transformation'] == 'none' and d['source_field'] == 'content', 'unsupported transformation')
        check(0 <= d['start'] < d['end'] <= len(r['content']), 'invalid offsets')
        check(r['content'][d['start']:d['end']] == d['evidence_text'], 'excerpt mismatch')
        doc = json.loads((ROOT/'data/clean/documents'/f"{r['document_id']}.json").read_text(encoding='utf-8'))
        check(d['evidence_text'] in doc['body'], 'excerpt absent from clean body')
        check(doc['source_url'] == r['source_url'], 'clean source mismatch')
    used = set()
    check(bool(q['answer_points']), 'no answer points')
    for point in q['answer_points']:
        check(bool(point['text']) and bool(point['evidence_ids']), 'empty answer point')
        check(set(point['evidence_ids']) <= set(ids), 'unmapped answer point')
        used.update(point['evidence_ids'])
    check(used == set(ids), 'unused gold evidence')
    check(q['gold_answer'] == ' '.join(p['text'] for p in q['answer_points']), 'answer/points mismatch')
    path = q['gold_relation_path']
    if q['question_category'] == 'multi_hop':
        check(len(path) >= 2, 'multi-hop requires two steps')
        for i, step in enumerate(path):
            check(bool(step['evidence_ids']) and set(step['evidence_ids']) <= set(ids), 'path evidence')
            check(bool(step['head']) and bool(step['tail']) and bool(step['relation']), 'empty path edge')
            check(step['depends_on'] == ([] if i == 0 else [i-1]), 'path dependency')
            if i:
                check(step['head'] == path[i-1]['tail'], 'disconnected path')
    else:
        check(not path, 'unexpected path')
    for cid, alt_ids in q.get('evidence_alternatives',{}).items():
        for alt in alt_ids:
            check(cid in index and alt in index and index[cid]['content'] == index[alt]['content'], 'invalid exact-text alternative')
    check(q['review_status'] == 'pending_human_cross_review', 'unverified approval status')
    return errors

def main():
    manifest = json.loads((HERE/'manifest.json').read_text(encoding='utf-8'))
    rows = [json.loads(x) for x in CORPUS.read_text(encoding='utf-8').splitlines() if x.strip()]
    index = {r['chunk_id']:r for r in rows}
    questions = [json.loads(x) for x in (HERE/'benchmark.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    errors = []
    for name, ok in [('corpus hash',digest(CORPUS)==manifest['corpus_sha256']),
                     ('benchmark hash',digest(HERE/'benchmark.jsonl')==manifest['benchmark_sha256']),
                     ('unique corpus IDs',len(index)==len(rows)),
                     ('unique qid',len({q['qid'] for q in questions})==len(questions)),
                     ('unique questions',len({re.sub(r'\s+','',q['question']) for q in questions})==len(questions)),
                     ('question count',10<=len(questions)<=20 and len(questions)==manifest['question_count'])]:
        if not ok: errors.append(name)
    for path, sha in manifest['clean_documents'].items():
        if digest(ROOT/path) != sha: errors.append('clean hash: '+path)
    for q in questions:
        errors.extend(check_question(q,index))
    counts = Counter(q['question_category'] for q in questions)
    if set(counts) != {'single_hop','multi_hop','summary'}: errors.append('missing category')
    lengths = {}
    for filename in ['任务3B交付A说明.md','任务3在Stage2中的作用.md']:
        lengths[filename] = len(re.sub(r'\s+','',(ROOT/'docs'/filename).read_text(encoding='utf-8')))
        if lengths[filename] > 300: errors.append('document too long: '+filename)
    report = {'questions':len(questions),'categories':dict(counts),'source_documents':len(manifest['clean_documents']),
              'short_document_characters':lengths,'errors':errors,
              'checks':'结构、哈希、切片及clean正文回查、答案要点关联、路径连接；不自动证明语义正确',
              'pending':['B与A/D双人交叉作答','Neo4j路径验证','A读取兼容性确认','三系统评测']}
    (HERE/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main())
