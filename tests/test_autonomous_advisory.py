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


def test_generic_model_relay_requires_api_auth_and_hides_private_output(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.model_orchestrator import client
    captured = []
    def complete(payload, **kwargs):
        captured.append((payload, kwargs))
        return {'choices': [{'finish_reason': 'stop', 'message': {
            'content': 'A visible answer.', 'reasoning_content': 'private reasoning'}}],
            'private_endpoint': 'do not expose'}
    monkeypatch.setenv('CIVITAS_API_KEY', 'test-api-key')
    monkeypatch.setattr(client, 'completion', complete)
    api = TestClient(app)
    payload = {'messages': [{'role': 'user', 'content': 'Hello'}], 'model': 'client-selected-model'}
    assert api.post('/api/model/completion', json=payload).status_code == 401
    assert not captured
    response = api.post('/api/model/completion', json=payload,
        headers={'Authorization': 'Bearer test-api-key'})
    assert response.status_code == 200
    assert response.json()['choices'][0]['message']['content'] == 'A visible answer.'
    assert 'private' not in response.text
    assert captured[0][0]['chat_template_kwargs']['enable_thinking'] is False
    assert 'model' not in captured[0][0]
    assert captured[0][1]['route'].model == response.json()['model']


def test_model_relay_rejects_unbounded_generation(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    monkeypatch.setenv('CIVITAS_API_KEY', 'test-api-key')
    response = TestClient(app).post('/api/model/completion', json={
        'messages': [{'role': 'user', 'content': 'Hello'}], 'max_tokens': 900000},
        headers={'Authorization': 'Bearer test-api-key'})
    assert response.status_code == 422
