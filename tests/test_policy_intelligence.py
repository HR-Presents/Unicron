import unittest
from backend.app.policy_intelligence import policy_stage, benchmark_stage

CASE={'title':'Water outage','summary':'Residents report a water supply interruption and no restoration estimate.'}

def passage(citation, note, text, *, kind=None, status=None, jurisdiction=None):
    return {'citation':citation,'document_id':citation.split('#')[0], 'source_note':note,
            'filename':'sample.txt','text':text,'source_type':kind,
            'verification_status':status,'jurisdiction':jurisdiction,
            'official_url':'https://example.gov/source' if kind else None,
            'authority':'Example Authority' if kind else None,
            'document_title':'Example source' if kind else None,
            'publication_date':None,'effective_date':None,'verified_at':None,'verified_by':None}

class PolicyIntelligenceTests(unittest.TestCase):
    def test_no_sources_blocks_policy(self):
        result=policy_stage([],CASE)
        self.assertEqual(result['status'],'source_required')
        self.assertIsNone(result['result']['policy_conclusion'])

    def test_policy_is_extract_only(self):
        p=passage('doc1#p1','policy; uploaded by test user',
            'The utility shall publish a restoration notice when the supply is interrupted.',
            kind='policy',status='verified',jurisdiction='UAE')
        result=policy_stage([p],CASE)
        self.assertEqual(result['status'],'review_required')
        self.assertEqual(result['result']['source_authentication'],'reviewer_attested_not_independently_authenticated')
        self.assertEqual(result['result']['relevant_excerpts'][0]['citation'],'doc1#p1')
        self.assertIsNone(result['result']['policy_conclusion'])

    def test_benchmark_requires_two_jurisdictions(self):
        one=[passage('a#p1','benchmark; country=UAE',
            'Municipal service authorities shall publish timely incident updates to affected residents during water supply interruptions, including expected restoration times and alternative service arrangements.',
            kind='benchmark',status='verified',jurisdiction='UAE')]
        self.assertEqual(benchmark_stage(one,CASE)['status'],'source_required')
        two=one+[passage('b#p1','benchmark; country=Singapore',
            'Public service authorities shall communicate timely incident notifications to affected residents during essential water supply disruptions, including restoration estimates and emergency alternative service arrangements.',
            kind='benchmark',status='verified',jurisdiction='Singapore')]
        result=benchmark_stage(two,CASE)
        self.assertEqual(result['status'],'review_required')
        self.assertEqual(len(result['result']['jurisdiction_evidence']),2)
        self.assertIsNone(result['result']['comparison'])

    def test_unlabelled_document_is_not_policy(self):
        result=policy_stage([passage('x#p1','Test document, not official evidence',
            'The utility shall publish a notice.')],CASE)
        self.assertEqual(result['status'],'source_required')

if __name__=='__main__': unittest.main()
