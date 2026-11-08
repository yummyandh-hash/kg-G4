import unittest
from score_evidence import score_one, evaluate

class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.q={'qid':'q','question_category':'multi_hop','gold_evidence':['a','b'],
                'evidence_alternatives':{'a':['a2'],'b':[]}}
        self.ix={k:{} for k in ['a','a2','b']}

    def test_alternative_separate_from_strict(self):
        r=score_one(self.q,[{'source_id':'a2'},{'evidence_id':'b'}],self.ix,2)
        self.assertEqual((r['strict_recall'],r['equivalent_recall']),(0.5,1))

    def test_bad_primary_is_not_silently_replaced(self):
        r=score_one(self.q,[{'source_id':'graph_node','evidence_id':'a'}],self.ix,1)
        self.assertEqual(r['equivalent_recall'],0)
        self.assertEqual(r['invalid_id_count'],1)

    def test_duplicates_consume_budget(self):
        r=score_one(self.q,[{'source_id':x} for x in ['a','a','b']],self.ix,2)
        self.assertEqual(r['strict_recall'],0.5)

    def test_missing_predictions_count_zero(self):
        r=evaluate([self.q],[],self.ix,5)
        self.assertEqual(r['overall']['strict_recall'],0)
        self.assertEqual(r['missing_prediction_qids'],['q'])

    def test_unknown_prediction_rejected(self):
        with self.assertRaises(ValueError): evaluate([self.q],[{'qid':'unknown','evidences':[]}],self.ix,5)

    def test_empty_primary_falls_back(self):
        r=score_one(self.q,[{'source_id':'','evidence_id':'a'}],self.ix,1)
        self.assertEqual(r['strict_recall'],0.5)

if __name__=='__main__': unittest.main()
