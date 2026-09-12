"""Read references separately; send only question to the evaluated system."""
import json
from pathlib import Path

def load_questions(path=None):
    path = Path(path) if path else Path(__file__).with_name('benchmark.jsonl')
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def evidence_recall_at_k(question, ranked_chunk_ids, k):
    if k <= 0:
        raise ValueError('k must be positive')
    # Preserve the original top-k budget; duplicates still consume slots.
    retrieved = set(ranked_chunk_ids[:k])
    groups = [{cid, *question.get('evidence_alternatives',{}).get(cid, [])}
              for cid in question['gold_evidence']]
    return sum(bool(group & retrieved) for group in groups) / len(groups)

if __name__ == '__main__':
    questions = load_questions()
    print(f'Loaded {len(questions)} questions; first ID: {questions[0]["qid"]}')
