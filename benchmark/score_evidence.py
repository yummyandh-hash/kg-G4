"""Score A's ranked evidence outputs without converting node IDs into citations.

Input JSONL: {qid, evidences: [{source_id, evidence_id}, ...]}.
CLI: python benchmark/score_evidence.py predictions.jsonl --k 5 --output report.json
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from build_benchmark import CORPUS, HERE, digest
from read_example import load_questions

def score_one(question, evidences, index, k):
    if k <= 0:
        raise ValueError('k must be positive')
    ids, invalid = [], []
    for evidence in evidences:
        if not isinstance(evidence, dict):
            raise ValueError('each evidence must be an object')
        cid = evidence.get('source_id') or evidence.get('evidence_id')
        if cid is not None and not isinstance(cid, str):
            raise ValueError('evidence ID must be string or null')
        if cid not in index:
            invalid.append({'selected_id':cid,'fallback_id':evidence.get('evidence_id'),
                            'reason':'missing_id' if not cid else 'not_a_chunk_id'})
        # Invalid and duplicate results still consume the original retrieval budget.
        ids.append(cid)
    top = set(ids[:k])
    gold = question['gold_evidence']
    groups = [{cid, *question.get('evidence_alternatives', {}).get(cid, [])} for cid in gold]
    return {'qid':question['qid'],'question_category':question['question_category'],
            'strict_recall':sum(cid in top for cid in gold)/len(gold),
            'equivalent_recall':sum(bool(g & top) for g in groups)/len(groups),
            'returned_count':len(ids),'invalid_id_count':len(invalid),
            'invalid_ids':invalid,'missing_gold_groups':[gold[i] for i,g in enumerate(groups) if not g & top]}

def evaluate(questions, predictions, index, k):
    by_id = {}
    known = {q['qid'] for q in questions}
    for p in predictions:
        if p['qid'] in by_id or p['qid'] not in known:
            raise ValueError('duplicate or unknown prediction qid: '+p['qid'])
        if not isinstance(p.get('evidences'), list):
            raise ValueError('evidences must be a ranked array')
        by_id[p['qid']] = p['evidences']
    results = [score_one(q,by_id.get(q['qid'],[]),index,k) for q in questions]
    grouped = defaultdict(list)
    for r in results:
        grouped[r['question_category']].append(r)
    def means(rows):
        return {key:sum(r[key] for r in rows)/len(rows) for key in ('strict_recall','equivalent_recall')}
    return {'k':k,'ranking_policy':'original top-k; invalid and duplicate entries consume slots',
            'overall':means(results),'by_category':{c:means(rs) for c,rs in grouped.items()},
            'missing_prediction_qids':sorted(known-set(by_id)),
            'invalid_id_count':sum(r['invalid_id_count'] for r in results),'per_question':results}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('predictions',type=Path)
    parser.add_argument('--k',type=int,default=5)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    manifest = json.loads((HERE/'manifest.json').read_text(encoding='utf-8'))
    if digest(CORPUS) != manifest['corpus_sha256'] or digest(HERE/'benchmark.jsonl') != manifest['benchmark_sha256']:
        raise ValueError('corpus/benchmark changed; revalidate references first')
    rows = [json.loads(x) for x in CORPUS.read_text(encoding='utf-8').splitlines() if x.strip()]
    index = {r['chunk_id']:r for r in rows}
    if len(index)!=len(rows): raise ValueError('duplicate corpus IDs')
    questions = load_questions()
    for q in questions:
        for cid in q['gold_evidence']:
            if cid not in index: raise ValueError('missing gold ID')
            for alt in q.get('evidence_alternatives',{}).get(cid,[]):
                if alt not in index or index[alt]['content']!=index[cid]['content']:
                    raise ValueError('unverified equivalent evidence')
    predictions = [json.loads(x) for x in args.predictions.read_text(encoding='utf-8').splitlines() if x.strip()]
    report = evaluate(questions,predictions,index,args.k)
    report.update(corpus_sha256=digest(CORPUS),benchmark_sha256=digest(HERE/'benchmark.jsonl'),
                  predictions_sha256=digest(args.predictions))
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('overall','by_category','invalid_id_count','missing_prediction_qids')},ensure_ascii=False))

if __name__ == '__main__':
    main()
