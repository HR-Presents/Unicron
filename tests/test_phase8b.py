import unittest
from backend.app.policy_intelligence import policy_stage, benchmark_stage

CASE={'title':'Water outage','summary':'Residents report interrupted water supply.'}

def passage(cid, kind='policy', status='verified', jurisdiction='UAE'):
    return {'citation':cid,'document_id':cid.split('#')[0], 'source_note':'policy benchmark',
        'filename':'sample.txt','text':(
            'Residents must receive a timely public notice when an essential '
            'municipal service is interrupted, including information about '
            'expected restoration and alternative service arrangements.'
        ),
        'source_type':kind,'verification_status':status,'jurisdiction':jurisdiction,
        'official_url':'https://example.gov/policy','authority':'Example Authority',
        'document_title':'Example document','verified_at':'2026-11-05T00:00:00+00:00',
        'verified_by':'Test reviewer','publication_date':None,'effective_date':None}

class Phase8BTests(unittest.TestCase):
    def test_unverified_and_rejected_are_excluded(self):
        for status in ('unverified','rejected'):
            with self.subTest(status=status):
                self.assertEqual(policy_stage([passage('a#p1',status=status)],CASE)['status'],'source_required')
    def test_verified_policy_is_extract_only(self):
        result=policy_stage([passage('a#p1')],CASE)
        self.assertEqual(result['status'],'review_required')
        self.assertIsNone(result['result']['policy_conclusion'])
        self.assertEqual(result['result']['relevant_excerpts'][0]['citation'],'a#p1')
        self.assertEqual(result['result']['eligible_sources'][0]['jurisdiction'],'UAE')
    def test_label_cannot_override_source_type(self):
        self.assertEqual(policy_stage([passage('a#p1',kind='benchmark')],CASE)['status'],'source_required')
    def test_benchmark_needs_two_verified_jurisdictions(self):
        one=passage('a#p1',kind='benchmark',jurisdiction='UAE')
        self.assertEqual(benchmark_stage([one],CASE)['status'],'source_required')
        second=passage('b#p1',kind='benchmark',jurisdiction='Singapore')
        self.assertEqual(benchmark_stage([one,second],CASE)['status'],'review_required')
        self.assertIsNone(benchmark_stage([one,second],CASE)['result']['comparison'])
    def test_rejected_second_jurisdiction_not_counted(self):
        one=passage('a#p1',kind='benchmark',jurisdiction='UAE')
        two=passage('b#p1',kind='benchmark',jurisdiction='Singapore',status='rejected')
        self.assertEqual(benchmark_stage([one,two],CASE)['status'],'source_required')

if __name__=='__main__': unittest.main()
