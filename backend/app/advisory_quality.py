"""Conservative output screening; not legal interpretation or semantic verification."""
import re
from copy import deepcopy

LEGAL_TARGET = re.compile(r'\b(?:EU AI Act|European AI Act|GDPR|AI Act|UAE (?:data protection |privacy )?(?:laws?|regulations?)|Federal Decree|Law No\.)', re.I)
OBLIGATION = re.compile(r'\b(?:ensur\w*\s+(?:full\s+)?compliance|guarante\w*\s+compliance|comply(?:ing)?\s+with|compliant\s+with|in accordance with|legally required|must\s+(?:follow|adopt|implement|enforce))\b', re.I)
NEGATED = re.compile(r'\b(?:do not|cannot|does not|not established|whether|if applicable|if it applies)\b', re.I)


def unestablished_obligation(text):
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        if LEGAL_TARGET.search(sentence) and OBLIGATION.search(sentence) and not NEGATED.search(sentence):
            return True
    return False


def screen_advisory(result, case, fields, cautions=()):
    """Withhold selected unestablished obligations; retain originals for provenance.

    This does not change source verification, stage completion or approval gates.
    It does not establish that statements which pass are legally correct.
    """
    cleaned = deepcopy(result)
    withheld = list(cleaned.get('withheld_claims') or [])
    for field in fields:
        value = cleaned.get(field)
        values = value if isinstance(value, list) else [value] if isinstance(value, str) else []
        keep = []
        for index, statement in enumerate(values):
            if isinstance(statement, str) and unestablished_obligation(statement):
                withheld.append({'field': field, 'index': index, 'text': statement,
                                 'code': 'legal_obligation_not_established'})
            else:
                keep.append(statement)
        if isinstance(value, list):
            cleaned[field] = keep
        elif isinstance(value, str) and not keep:
            cleaned[field] = ('Advisory assessment of ' + str(case.get('title', 'the described case'))[:180]
                              + '. Legal applicability remains unresolved.')
    if cautions:
        cleaned['scope_cautions'] = list(cautions)
    if withheld:
        cleaned['withheld_claims'] = withheld
        cleaned['output_quality_flags'] = [{
            'code': 'legal_obligation_not_established',
            'reason': 'Some generated compliance or obligation statements were withheld because legal applicability has not been established. This screen is conservative and does not verify the remaining analysis.'}]
    return cleaned
