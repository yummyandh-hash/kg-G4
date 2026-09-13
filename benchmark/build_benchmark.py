"""Materialize curated, source-grounded questions; standard library only."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
CORPUS = ROOT / 'data/chunks/chunks.jsonl'

# Each answer point is paired with the exact source sentence(s) reviewed.
SPECS = [
 ('single_hop','0098187ad030','按板头曲项目正文，板头曲的传播中心在哪座城市？', [('传播中心在南阳市。',[3])]),
 ('single_hop','00a45c44cc2a','按爬山调项目正文，山区爬山调和平原爬山调分别以哪里为代表？', [('山区以武川为代表，平原以河套地区为代表。',[6])]),
 ('single_hop','002f0878b7c0','锅庄舞的“郭卓”和“枯卓”分别指什么舞步？', [('郭卓为走舞，枯卓为转舞。',[8])]),
 ('single_hop','00635509aeb8','按花鼓戏项目正文，皖南花鼓戏的四大主腔是什么？', [('淘腔、北扭子、四平、悲腔。',[13])]),
 ('single_hop','00f56170ef94','按石家庄丝弦项目正文，文场的“四架弦”包含哪些乐器？', [('弦索、月琴、大三弦、小三弦。',[7])]),
 ('multi_hop','0098187ad030','按板头曲项目正文，1953年代表河南参加全国第一届民间音乐舞蹈会演的板头曲传人是谁？正文明确说由他传谱并远播海外的两首筝曲是什么？', [('传人为曹东扶。',[11]),('由曹东扶传谱的两首筝曲是《高山流水》和《苏武牧羊》。',[13])]),
 ('multi_hop','00635509aeb8','按花鼓戏项目正文，以湘北方言演唱的花鼓戏是哪一种？该种花鼓戏的声腔音乐分哪两大类？', [('是湖南岳阳花鼓戏。',[8]),('其声腔音乐分为锣腔与琴腔。',[9])]),
 ('multi_hop','00b1ae0763dc','按普安苗族芦笙舞正文，被称为“歪梳苗”的是哪一苗人群体？该群体的芦笙舞主要流传在普安县哪两个乡镇？', [('该群体是“蒙洒”苗人。',[4]),('主要流传于龙吟镇、白沙乡的“蒙洒”苗人世居村寨。',[2])]),
 ('multi_hop','00635509aeb8','按花鼓戏项目正文，“花鼓大走场”被称为哪一种花鼓戏的绝活儿？正文列出的该种花鼓戏主要曲调包括什么？', [('是淮北花鼓戏。',[12]),('正文列举宿州调、浍北调、口子调平板、寒板等曲调，并指出寒调尤具个性。',[11])]),
 ('multi_hop','009d43e2a146','按乌珠穆沁长调项目正文，核心分布在西乌珠穆沁旗和东乌珠穆沁旗的长调叫什么？它在民俗场合的副歌对唱部分叫什么、一般由什么乐器伴奏？', [('该长调是乌珠穆沁长调。',[1]),('副歌对唱部分叫“图日勒格”，一般由马头琴伴奏。',[4])]),
 ('summary','002d0d3856d2','仅根据恩施摆手舞正文，概括摆手舞的主要表现内容、最显著的手脚配合特征和文中列出的社会功能。', [('主要表现狩猎、农事、军事和社会生活，歌乐舞结合。',[12]),('最显著的特征是甩同边手、走同边脚。',[13]),('具有祭祀、娱乐、教育、交际等社会功能。',[14])]),
 ('summary','002f0878b7c0','仅根据甘孜锅庄正文，概括其表演的领舞设置、男女唱跳配合方式和节奏变化。', [('男女各有一名能歌善舞的卓本，即领舞人。',[17]),('男队唱跳时女队只跳不唱，女队唱跳时男队只跳不唱。',[19]),('节奏由慢渐快，进入高潮后以快节奏结束。',[20])]),
 ('summary','009d43e2a146','仅根据乌珠穆沁长调正文，概括其过去、新中国成立后以及文中所述当下三个阶段的传承方式。', [('过去通过岁时节日、人生仪礼及日常生活自然习得。',[8]),('新中国成立后通过舞台表演、课堂传授培养人才。',[9]),('文中所述当下通过政府、学校、民间团体和个人举办传习、培训、比赛等活动传承。',[10])]),
 ('summary','00a45c44cc2a','仅根据爬山调正文，从移民带来的民歌交流、唱词特点和旋律结构三个方面概括其艺术形成与表现。', [('移民带来的民歌长期交流，融合河北、山西、陕西、山东等地特点，并吸收蒙古、回、满等民族音乐元素。',[5]),('唱词短小精悍，多用乡土方言重叠词，字数无定、虚实相间。',[8]),('多采用两乐句的乐段结构，下句多是上句的变化重复。',[9])]),
 ('summary','00f56170ef94','仅根据石家庄丝弦正文，概括其唱腔的真假声运用、表演动作风格及文中记录的剧团困境；困境按材料记载回答，不视作当前调查。', [('真声唱字、旋律上跳翻高，再用假声拖腔、旋律顺级下行。',[4]),('表演热烈粗犷、动作夸张幅度大，刻画人物细腻传神。',[8]),('材料记录演出市场萎缩、观众锐减、剧目老化、经费紧张及专业人才青黄不接等问题。',[11])]),
]

PATHS = [
 [('1953年代表河南参加会演的板头曲传人','身份','曹东扶'),('曹东扶','传谱筝曲','高山流水、苏武牧羊')],
 [('以湘北方言演唱的花鼓戏','识别为','湖南岳阳花鼓戏'),('湖南岳阳花鼓戏','声腔分类','锣腔、琴腔')],
 [('歪梳苗','别称指向','蒙洒苗人'),('蒙洒苗人','芦笙舞主要流传乡镇','龙吟镇、白沙乡')],
 [('以花鼓大走场为绝活的花鼓戏','识别为','淮北花鼓戏'),('淮北花鼓戏','正文列举曲调','宿州调、浍北调、口子调平板、寒板等')],
 [('核心分布于西乌珠穆沁旗和东乌珠穆沁旗的长调','识别为','乌珠穆沁长调'),('乌珠穆沁长调','民俗副歌对唱及伴奏','图日勒格、马头琴')],
]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build():
    rows = [json.loads(line) for line in CORPUS.read_text(encoding='utf-8').splitlines() if line.strip()]
    index = {r['chunk_id']: r for r in rows}
    assert len(index) == len(rows), 'duplicate corpus IDs'
    questions = []
    path_number = 0
    for n, (category, suffix, question, points) in enumerate(SPECS, 1):
        doc = 'ihchina_' + suffix
        answer_points = [{'text': text, 'evidence_ids': [f'{doc}_content_{i}' for i in ids]} for text, ids in points]
        ids = list(dict.fromkeys(e for point in answer_points for e in point['evidence_ids']))
        details = []
        for cid in ids:
            r = index[cid]
            details.append({k: r[k] for k in ('document_id','chunk_id','source_url','retrieved_at') } | {
                'evidence_text': r['content'], 'source_field': 'content', 'start': 0,
                'end': len(r['content']), 'transformation': 'none'})
        path = []
        if category == 'multi_hop':
            for j, (head, relation, tail) in enumerate(PATHS[path_number]):
                path.append({'head':head,'relation':relation,'tail':tail,
                             'evidence_ids':answer_points[j]['evidence_ids'],
                             'depends_on': [] if j == 0 else [0]})
            path_number += 1
        # Exact duplicate text is a safe, mechanically discoverable alternative;
        # other semantic alternatives require human assessment.
        alternatives = {cid: [r['chunk_id'] for r in rows if r['chunk_id'] != cid and r['content'] == index[cid]['content']] for cid in ids}
        questions.append({'qid': f'ich_bench_{n:02}', 'question':question,
            'gold_answer':' '.join(p['text'] for p in answer_points),
            'question_category':category,'gold_evidence':ids,'gold_evidence_details':details,
            'answer_points':answer_points,'gold_relation_path':path,
            'evidence_alternatives':alternatives,'review_status':'pending_human_cross_review',
            'path_validation':'text_grounded_only_neo4j_pending' if path else 'not_applicable',
            'notes':'范围为指定项目正文；正文含邻近句指代时结合完整文档理解。字段类别/批次不作为答案依据。'})
    HERE.mkdir(exist_ok=True)
    (HERE/'benchmark.jsonl').write_text(''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in questions),encoding='utf-8')
    manifest = {'version':'B-stage2-task3-v1','owner':'雷玺功','generated_date':'2026-09-12',
        'corpus_path':CORPUS.relative_to(ROOT).as_posix(),'corpus_sha256':digest(CORPUS),
        'benchmark_sha256':digest(HERE/'benchmark.jsonl'),
        'clean_documents':{f'data/clean/documents/ihchina_{s}.json':digest(ROOT/f'data/clean/documents/ihchina_{s}.json') for s in sorted({s[1] for s in SPECS})},
        'question_count':len(questions),'limitations':['便利抽样，非全语料代表性抽样','未进行人工双人交叉作答','未进行Neo4j路径验证或三系统实验','未回访网页，事实仅据本地项目正文','未发现A的Benchmark读取器；未更改旧契约，summary映射待确认']}
    (HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Generated {len(questions)} questions')

if __name__ == '__main__':
    build()
