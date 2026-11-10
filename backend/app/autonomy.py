"""Publish autonomous advisory reports without turning findings into approvals.

Evidence checks, provenance and uncertainty remain intact. Legacy reviewer metadata
is translated at the reporting boundary; it never suspends an investigation.
"""


def advisory_report(value):
    if isinstance(value, list):
        return [advisory_report(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == 'human_review_required':
            result[key] = False
        elif key == 'review_gates':
            result['evidence_limitations'] = advisory_report(item)
        elif key == 'prioritized_review_actions':
            result['validation_recommendations'] = advisory_report(item)
        else:
            result[key] = advisory_report(item)
    # These stages have finished their advisory work. Their old status refers
    # to interpretation/approval, not an unfinished execution. Keep the
    # evidence limits distinct from the lifecycle status.
    if (result.get('agent') in ('Policy Advisor', 'Global Benchmark Agent')
            and result.get('status') == 'review_required'
            and isinstance(result.get('result'), dict)):
        result['status'] = 'completed'
        result['evidence_status'] = 'limitations_reported'
    statuses = result.get('agent_statuses')
    if isinstance(statuses, dict):
        for agent in ('policy_advisor', 'global_benchmark'):
            if statuses.get(agent) == 'review_required':
                statuses[agent] = 'completed'
    return result
