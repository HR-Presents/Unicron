"""Verifier failure modes: a smoke check must never turn missing evidence into a pass."""
import argparse
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('verify_live', Path(__file__).parents[1] / 'scripts/verify-live.py')
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


def fixture_calls(monkeypatch, missing_agent=False, citation='doc#p2'):
    requests = []
    stages = [{'agent': agent, 'status': 'completed'} for agent in live.AGENTS]
    if missing_agent:
        stages.pop()
    report = {'id': 'run-1', 'stages': stages, 'analysis_mode': 'autonomous_advisory', 'human_review_required': False}
    def call(base, path, body=None):
        requests.append((path, body))
        if path == '/connection': return {'state': 'connected'}
        if path == '/chat': return {'answer': 'UNICRON_READY', 'model': 'test-fixture-only'}
        if path.endswith('/jobs'): return [{'id': 'job-1', 'status': 'completed', 'result_id': 'run-1'}]
        if path.endswith('/investigations'): return [report]
        if path.endswith('/events'): return [{'agent': stage['agent'], 'stage': stage} for stage in stages]
        if path.endswith('/desk'): return {'answer': 'A fixture answer.', 'citations': [{'id': citation}]}
        if path.startswith('/evidence/verified/passages/'): return {'citation': citation, 'text': 'Fixture documentary passage.', 'verification_status': 'verified'}
        raise AssertionError('Unexpected request: ' + path)
    monkeypatch.setattr(live, 'call', call)
    return requests


def test_live_check_is_limited_to_local_gateway_origins():
    assert live.local_base('http://127.0.0.1:43210') == 'http://127.0.0.1:43210/api/unicron'
    for value in ('https://example.com', 'http://token@localhost:1234', 'http://localhost:1234/?key=secret'):
        with pytest.raises(argparse.ArgumentTypeError): live.local_base(value)


def test_existing_case_check_matches_persisted_job_and_resolves_documentary_passage(monkeypatch):
    requests = fixture_calls(monkeypatch)
    live.verify('fixture-only', case_id='CIV-TEST')
    assert ('/evidence/verified/passages/doc/2', None) in requests
    assert not any(path == '/cases' or path.endswith('/investigate/async') for path, _ in requests)


def test_missing_agent_cannot_pass_live_verification(monkeypatch):
    fixture_calls(monkeypatch, missing_agent=True)
    with pytest.raises(ValueError, match='Not all six'): live.verify('fixture-only', case_id='CIV-TEST')


def test_agent_advisory_citation_does_not_count_as_documentary_evidence(monkeypatch):
    fixture_calls(monkeypatch, citation='RUN-agent-output')
    with pytest.raises(ValueError, match='no verified documentary citation'): live.verify('fixture-only', case_id='CIV-TEST')


def test_incorrect_routing_stops_before_creating_a_case(monkeypatch):
    writes = []
    def call(base, path, body=None):
        if path == '/connection': return {'state': 'connected'}
        if path == '/chat': return {'answer': 'UNICRON_READY'}
        if path == '/chat/route': return {'route': 'chat'}
        writes.append(path)
        raise AssertionError('Must not create a case after incorrect routing')
    monkeypatch.setattr(live, 'call', call)
    with pytest.raises(ValueError, match='not routed'): live.verify('fixture-only')
    assert writes == []
