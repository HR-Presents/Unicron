"""Regress the hospital output: policing noise, copied sources and unestablished obligations."""
from backend.app.policy_intelligence import _rank, _benchmark_rank, policy_stage, benchmark_stage
from backend.app.evidence_relevance import duplicate_excerpt, query_terms, scope_cautions
from backend.app.advisory_quality import screen_advisory, unestablished_obligation

CASE = {'title': 'AI-assisted hospital appointments', 'summary': 'A UAE public hospital processes patient clinical records. Assess data protection, accountability and service continuity.'}
QUERY = CASE['title'] + ' ' + CASE['summary']
HEALTH = 'Health systems must protect patient clinical records and maintain appropriate controls for medical data processing and treatment.'
POLICE = 'Regardless of the deployer, each use of these high-risk AI systems shall be documented in the relevant police file and provided to law enforcement authorities.'
SCOPE = 'Provisions of this Decree by Law shall not apply to Government Data, governmental entities which process personal data, or personal health data regulated by separate legislation.'


def p(ref, text, region='UAE', status='verified'):
    return {'citation': ref, 'document_id': ref.split('#')[0], 'text': text, 'source_type': 'policy',
            'verification_status': status, 'jurisdiction': region, 'authority': 'Fixture authority',
            'official_url': 'https://example.gov/document', 'document_title': 'Fixture policy'}


def test_hospital_policy_does_not_select_police_passage():
    result = policy_stage([p('police#p1', POLICE, 'European Union'), p('health#p2', HEALTH)], CASE)
    assert [item['citation'] for item in result['result']['relevant_excerpts']] == ['health#p2']


def test_zero_overlap_policy_is_not_presented_as_relevant():
    result = policy_stage([p('unrelated#p1', 'Agricultural irrigation schedules specify seasonal fertilizer quantities and crop rotation intervals.')], CASE)
    assert result['status'] == 'source_required'
    assert not result['result']['relevant_excerpts']


def test_policing_is_retained_for_explicit_healthcare_policing_case():
    assert _benchmark_rank([p('police#p1', POLICE)], QUERY + ' Compare law enforcement biometric identification policy.')


def test_duplicate_policy_sentence_across_imports_is_shown_once():
    result = _rank([p('first#p1', HEALTH), p('copy#p9', HEALTH.upper())], QUERY)
    assert len(result) == 1
    assert result[0][1] in ('first#p1', 'copy#p9')


def test_benchmark_removes_copied_excerpts_without_changing_citations():
    result = _benchmark_rank([p('first#p1', HEALTH), p('copy#p2', HEALTH.upper())], QUERY)
    assert len(result) == 1
    assert result[0][1] in ('first#p1', 'copy#p2')


def test_different_numeric_requirements_are_not_merged():
    base = 'Operators retain clinical audit records to support accountability, incident investigation and documented data protection safeguards for '
    assert not duplicate_excerpt(base + '6 months.', [base + '12 months.'])


def test_irrelevant_second_jurisdiction_cannot_make_benchmark_ready():
    result = benchmark_stage([p('health#p1', HEALTH), p('police#p1', POLICE, 'European Union')], CASE)
    assert result['status'] == 'source_required'
    assert result['result']['evidence_matrix'] is None


def test_scope_exclusion_retains_source_reference_and_is_not_legal_determination():
    result = policy_stage([p('scope#p1', SCOPE), p('health#p2', HEALTH)], CASE)
    caution = result['result']['scope_cautions'][0]
    assert caution['citation'] == 'scope#p1'
    assert caution['verbatim_excerpt'] == SCOPE
    assert 'remains unresolved' in caution['reason']


def test_unverified_scope_text_does_not_enter_verified_policy_cautions():
    result = policy_stage([p('scope#p1', SCOPE, status='unverified'), p('health#p2', HEALTH)], CASE)
    assert not result['result']['scope_cautions']


def test_ordinary_water_query_is_not_expanded_into_healthcare():
    assert 'clinical' not in query_terms('Water outage and restoration notices')
    assert 'clinical' in query_terms(QUERY)


def test_unestablished_compliance_recommendation_is_withheld_and_auditable():
    original = {'case_summary': 'The proposed system handles clinical records.', 'recommended_next_steps': [
        'Ensure compliance with UAE data protection laws and the EU AI Act.',
        'Map patient-data flows, access roles and fallback appointment handling.']}
    result = screen_advisory(original, CASE, ('case_summary', 'recommended_next_steps'))
    assert result['recommended_next_steps'] == [original['recommended_next_steps'][1]]
    assert result['withheld_claims'][0]['text'] == original['recommended_next_steps'][0]
    assert result['output_quality_flags']
    assert len(original['recommended_next_steps']) == 2  # Original persisted/returned object is not mutated.


def test_comparative_and_conditional_analysis_is_not_withheld():
    for statement in ('Assess whether the EU AI Act applies before adopting its requirements.',
                      'Use EU AI Act controls as comparative examples.',
                      'Do not assume the hospital must comply with the EU AI Act.'):
        assert not unestablished_obligation(statement)


def test_scenario_controls_cannot_smuggle_foreign_law_obligations():
    result = screen_advisory({'mitigations': ['Implement governance practices in accordance with the EU AI Act.',
                                            'Maintain a staffed appointment fallback during service outages.']},
                            CASE, ('mitigations',))
    assert result['mitigations'] == ['Maintain a staffed appointment fallback during service outages.']


def test_unestablished_summary_is_not_published_with_a_footnote_only():
    result = screen_advisory({'case_summary': 'The hospital must comply with the EU AI Act.'}, CASE, ('case_summary',))
    assert 'must comply' not in result['case_summary']
    assert 'unresolved' in result['case_summary']
