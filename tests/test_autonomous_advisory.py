"""Autonomy preserves evidence constraints and does not certify decisions."""
from backend.app.autonomy import advisory_report
from backend.app import briefing
from fastapi import HTTPException
import pytest


def test_advisory_report_retains_evidence_and_never_grants_approval():
    source = {'human_review_required': True, 'review_gates': [{'code': 'contradicted'}],
              'stages': [{'result': {'human_review_required': True,
                                    'automated_approval_permitted': False,
                                    'citations': ['doc#p1'], 'legal_applicability': 'not_established'}}]}
    result = advisory_report(source)
    assert result['human_review_required'] is False
    assert result['evidence_limitations'] == [{'code': 'contradicted'}]
    stage = result['stages'][0]['result']
    assert stage['human_review_required'] is False
    assert stage['automated_approval_permitted'] is False
    assert stage['legal_applicability'] == 'not_established'
    assert stage['citations'] == ['doc#p1']
    assert source['human_review_required'] is True


def request():
    return briefing.BriefingRequest(question='What does the evidence support?',
        excerpts=[{'id': 'doc#p1', 'title': 'Source', 'text': 'A published notice.'}])


def test_briefing_rejects_fabricated_citations(monkeypatch):
    monkeypatch.setattr(briefing.investigation, 'model_json', lambda *a, **k: {
        'answer': 'Claim', 'citations': ['invented#p7'], 'uncertainty': ''})
    with pytest.raises(HTTPException) as failure:
        briefing.briefing(request())
    assert failure.value.status_code == 502


def test_briefing_returns_only_validated_visible_output(monkeypatch):
    monkeypatch.setattr(briefing.investigation, 'model_json', lambda *a, **k: {
        'answer': 'The source describes a published notice.', 'citations': ['doc#p1'],
        'uncertainty': 'Applicability is not established.', 'reasoning_content': 'private'})
    response = briefing.briefing(request())
    assert 'doc#p1' in response['choices'][0]['message']['content']
    assert 'reasoning_content' not in str(response)


def test_qwen_credentials_are_server_side(monkeypatch):
    from backend.app.llm_headers import completion_headers
    monkeypatch.setenv('CIVITAS_LLM_API_KEY', 'test-model-key')
    assert completion_headers()['Authorization'] == 'Bearer test-model-key'
