#!/usr/bin/env python3
"""Exercise a running local UNICRON gateway and real model. Creates/retains a case unless --case-id is supplied."""
import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

AGENTS = ('Intake & Triage', 'Evidence Analyst', 'Policy Advisor',
          'Global Benchmark Agent', 'Scenario Evaluator', 'Review & Synthesis')
DEFAULT_QUESTION = ('Assess the data protection and accountability gaps for AI-assisted patient '
                    'triage in a UAE public hospital, using relevant global policy examples.')


def local_base(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1')
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/')):
        raise argparse.ArgumentTypeError('Use the local frontend origin, for example http://127.0.0.1:45201')
    return value.rstrip('/') + '/api/unicron'


def call(base, path, body=None):
    payload = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=payload,
                                    headers={'Accept': 'application/json', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=155) as response:
        return json.load(response)


def verify(base, case_id=None, timeout=900, question=DEFAULT_QUESTION):
    connection = call(base, '/connection')
    if connection.get('state') != 'connected':
        raise ValueError('Gateway is not connected to its backend. No case created.')
    print('PASS: frontend gateway → authenticated backend', flush=True)
    reply = call(base, '/chat', {'question': 'Reply with exactly UNICRON_READY', 'context': []})
    if reply.get('answer', '').strip().rstrip('.') != 'UNICRON_READY':
        raise ValueError('Model did not return the requested readiness marker. No case created.')
    print('PASS: real model inference | model:', reply.get('model', 'not reported'), flush=True)
    if not case_id:
        routing = call(base, '/chat/route', {'question': question})
        if routing.get('route') != 'investigate':
            raise ValueError('The case question was not routed to an investigation. No case created.')
        print('PASS: model-backed conversation routing', flush=True)
        case = call(base, '/cases', {'title': 'Live integration verification', 'summary': question,
                                    'domain': 'Healthcare', 'priority': 'Medium'})
        case_id = case['id']
        print('CREATED CASE:', case_id, '| retained for inspection', flush=True)
        job = call(base, '/cases/' + case_id + '/investigate/async', {})
        job_id = job['id']
    else:
        if not re.fullmatch(r'[A-Za-z0-9-]{1,80}', case_id):
            raise ValueError('Invalid case identifier')
        jobs = call(base, '/cases/' + case_id + '/jobs')
        if not jobs:
            raise ValueError('The selected case has no investigation job; no new work was queued.')
        job_id = jobs[0]['id']
    path = '/cases/' + case_id
    deadline = time.monotonic() + timeout
    while True:
        jobs = call(base, path + '/jobs')
        job = next((item for item in jobs if item['id'] == job_id), None)
        if not job:
            raise ValueError('Queued job is no longer available')
        if job['status'] == 'completed':
            break
        if job['status'] not in ('queued', 'running'):
            raise ValueError('Investigation ended with status: ' + job['status'])
        if time.monotonic() >= deadline:
            raise ValueError('Timed out waiting for the worker. Case is retained; inspect activity before retrying.')
        time.sleep(2)
    reports = call(base, path + '/investigations')
    report = next((item for item in reports if item['id'] == job.get('result_id')), None)
    if report is None:
        raise ValueError('The completed job has no matching persisted report')
    stages = {stage['agent']: stage for stage in report.get('stages', [])}
    for agent in AGENTS:
        print('AGENT:', agent, '|', stages.get(agent, {}).get('status', 'missing'), flush=True)
    if any(stages.get(agent, {}).get('status') != 'completed' for agent in AGENTS):
        raise ValueError('Not all six agents completed. Source requirements/failures remain honest; inspect the report.')
    if report.get('human_review_required') is not False or report.get('analysis_mode') != 'autonomous_advisory':
        raise ValueError('Report is not an autonomous advisory result')
    events = call(base, path + '/executions/' + report['id'] + '/events')
    if not all(any(event.get('agent') == agent and event.get('stage') for event in events) for agent in AGENTS):
        raise ValueError('One or more persisted agent events are missing')
    print('PASS: six recorded stages, completed queue job, autonomous report and persisted events', flush=True)
    follow = call(base, path + '/desk', {'question': 'Which documented risk should be prioritized and why?',
                                      'mode': 'synthesis', 'context': []})
    if not follow.get('answer', '').strip():
        raise ValueError('Follow-up did not return an answer')
    citations = follow.get('citations', [])
    documentary = []
    for citation in citations:
        ref = citation if isinstance(citation, str) else citation.get('id') or citation.get('citation', '')
        match = re.fullmatch(r'([A-Za-z0-9-]{1,80})#p([0-9]{1,8})', ref)
        if match:
            source = call(base, '/evidence/verified/passages/' + match[1] + '/' + match[2])
            if source.get('citation') != ref or not source.get('text') or source.get('verification_status') != 'verified':
                raise ValueError('A documentary citation did not resolve to a verified passage')
            documentary.append(ref)
    print('PASS: context-aware follow-up | documentary passages resolved:', len(set(documentary)), flush=True)
    if not documentary:
        raise ValueError('Follow-up answered, but no verified documentary citation was exercised. Evidence flow remains unverified.')
    print('PASS: live gateway → backend → worker → model → persisted report → cited follow-up', flush=True)
    print('This verifies execution and source resolution, not legal correctness or ITU certification.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=local_base, help='Current local frontend origin printed by start.sh')
    parser.add_argument('--case-id', help='Reuse the latest job of an existing case; do not create a case')
    parser.add_argument('--timeout', type=int, default=900, help='Maximum worker wait in seconds')
    args = parser.parse_args()
    if not 1 <= args.timeout <= 7200:
        parser.error('--timeout must be between 1 and 7200 seconds')
    try:
        verify(args.base, args.case_id, args.timeout)
    except urllib.error.HTTPError as error:
        print('FAILED: gateway returned HTTP', error.code)
        return 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        print('FAILED:', str(error))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
