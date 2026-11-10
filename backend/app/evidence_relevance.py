"""Bounded retrieval heuristics. Relevance signals never establish legal applicability."""
import re
from difflib import SequenceMatcher

STOP = set('the and for with from this that are was were have has been into their about will would could should must shall under within where which these those such other each article section regulation provisions purpose purposes relevant available using including case plans system systems requirements'.split())
CONCEPTS = (
    {'health', 'healthcare', 'hospital', 'hospitals', 'patient', 'patients', 'clinical', 'medical', 'medicine', 'triage', 'treatment'},
    {'continuity', 'outage', 'interruption', 'interrupted', 'disruption', 'restoration', 'recovery', 'fallback', 'availability'},
    {'accountability', 'oversight', 'audit', 'logging', 'transparency', 'responsibility', 'responsibilities'},
    {'privacy', 'consent', 'confidentiality', 'protection'},
)
HEALTH = CONCEPTS[0]
POLICING = re.compile(r'\b(?:law enforcement|police file|criminal offence|criminal offense|remote biometric identification)\b', re.I)


def terms(value):
    return set(re.findall(r'[a-z]{4,}', value.casefold())) - STOP


def query_terms(query):
    result = terms(query)
    for concept in CONCEPTS:
        if result & concept:
            result |= concept
    return result


def scope_mismatch(text, query):
    """Exclude policing-specific extracts from healthcare-only questions, not full laws."""
    return bool(terms(query) & HEALTH and POLICING.search(text) and not POLICING.search(query)
                and not re.search(r'not apply|exclud|exempt|scope of application', text, re.I))


def relevance_score(text, query):
    if scope_mismatch(text, query):
        return 0
    overlap = terms(text) & query_terms(query)
    generic = {'data', 'processing', 'personal', 'information', 'protection', 'services', 'public'}
    return sum(.4 if word in generic else 2 for word in overlap)


def publication_key(passage):
    # Separate jurisdictions and versions remain separate evidence families.
    title = ' '.join(str(passage.get('document_title') or '').casefold().split())
    url = str(passage.get('official_url') or '').split('#')[0]
    region = str(passage.get('jurisdiction') or '').strip().casefold()
    if title and url:
        return (region, title, url)
    return (region, str(passage.get('document_id') or passage['citation'].split('#')[0]))


def duplicate_excerpt(text, previous):
    """Collapse OCR/whitespace copies without merging differing numeric requirements."""
    normalized = ' '.join(re.findall(r'\w+', text.casefold()))
    for old in previous:
        comparable = ' '.join(re.findall(r'\w+', old.casefold()))
        if normalized == comparable:
            return True
        if re.findall(r'\d+', normalized) != re.findall(r'\d+', comparable):
            continue
        if min(len(normalized), len(comparable)) >= 90 and SequenceMatcher(None, normalized, comparable, autojunk=False).ratio() >= .9:
            return True
    return False


def scope_cautions(passages, query, limit=3):
    if not terms(query) & HEALTH and not re.search(r'government|public sector', query, re.I):
        return []
    results = []
    for passage in sorted(passages, key=lambda p: p['citation']):
        text = passage.get('text') or passage.get('content') or ''
        if not re.search(r'not apply|exempt(?:ion|ed)?|exclud(?:ed|es|ing)', text, re.I):
            continue
        if not re.search(r'government|health|medical|hospital', text, re.I):
            continue
        if duplicate_excerpt(text, [item['verbatim_excerpt'] for item in results]):
            continue
        results.append({'citation': passage['citation'], 'verbatim_excerpt': text[:850],
                        'reason': 'This source contains scope or exclusion language concerning government or health data. Applicability to this case remains unresolved.'})
        if len(results) == limit:
            break
    return results
