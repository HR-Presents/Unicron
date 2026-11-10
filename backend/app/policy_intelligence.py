"""Conservative, extractive policy and international benchmark analysis.

Only reviewer-attested sources are eligible for authenticated evidence displays.
A reviewer decision is not independent website authentication or legal advice.
"""
import re


def _sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if len(s.strip()) >= 18]


def _terms(text):
    stop = {'the','and','for','with','from','this','that','are','was','were','have','has','been','into','their','about','service','case','public','water','supply','issue','apply','shall','must','should','would','could','under','within','where','which','these','those','such','other','each','anyone','person','persons','article','section','regulation','provision','provisions','lawful','legal','authority','authorities','state','states','member','members','including','provided','subject','referred','respect','following','purpose','purposes','thereof','therein','thereby','hereby','accordance','requirement','requirements'}
    return {w for w in re.findall(r'[a-z]{4,}', text.lower()) if w not in stop}


def _rank(passages, query, limit=4):
    terms = _terms(query)
    ranked = []
    for passage in passages:
        for sentence in _sentences(passage['text']):
            overlap = len(_terms(sentence) & terms)
            ranked.append((overlap, passage['citation'], sentence[:450], passage))
    ranked.sort(key=lambda row: (-row[0], row[1], row[2]))
    # A citation identifies a passage, not an individual sentence. Keep the
    # highest-ranked sentence for each passage so the evidence matrix has
    # unambiguous citation identifiers without weakening draft validation.
    unique = []
    seen_citations = set()
    for row in ranked:
        citation = row[1]
        if citation in seen_citations:
            continue
        seen_citations.add(citation)
        unique.append(row)
        if len(unique) >= limit:
            break
    return unique


def _benchmark_rank(passages, query, limit=12):
    """Select substantive passage context, retaining original citation IDs."""
    terms = _terms(query)
    boilerplate = (
        'SOURCE EXCERPTS FOR UNICRON TESTING',
        'Human reviewer must compare each excerpt',
        'Extracted text only; independent verification required',
    )
    ranked = []
    for passage in passages:
        lines = [
            line.strip()
            for line in (passage.get('text') or '').splitlines()
            if line.strip()
            and not line.strip().startswith('===== ORIGINAL PDF PAGE')
            and not any(marker.lower() in line.lower() for marker in boilerplate)
        ]
        excerpt = ' '.join(lines)[:850]
        words = excerpt.split()
        if len(words) < 15 or len(excerpt) < 90:
            continue
        overlap = len(_terms(excerpt) & terms)
        score = overlap * 5 + min(len(words), 90) / 30
        ranked.append((score, passage['citation'], excerpt, passage))
    ranked.sort(key=lambda row: (-row[0], row[1], row[2]))

    # Select across source documents rather than letting one long document
    # occupy every evidence slot. This is retrieval diversity, not verification.
    groups = {}
    for row in ranked:
        passage = row[3]
        document_id = passage.get('document_id') or row[1].split('#')[0]
        groups.setdefault(document_id, []).append(row)

    selected = []
    seen_citations = set()
    seen_texts = set()

    while groups and len(selected) < limit:
        remaining = {}
        for document_id in sorted(groups):
            candidates = groups[document_id]
            while candidates:
                row = candidates.pop(0)
                normalized = ' '.join(row[2].casefold().split())
                if row[1] in seen_citations or normalized in seen_texts:
                    continue
                selected.append(row)
                seen_citations.add(row[1])
                seen_texts.add(normalized)
                break
            if candidates:
                remaining[document_id] = candidates
            if len(selected) >= limit:
                break
        groups = remaining

    return selected


def _tagged(passages, tag):
    return [p for p in passages if re.search(r'(?<!\w)' + re.escape(tag) + r'(?!\w)', p.get('source_note', ''), re.I)]


def _verified(passages, kind):
    return [p for p in passages if p.get('verification_status') == 'verified' and p.get('source_type') == kind and p.get('jurisdiction') and p.get('official_url')]


def _source(p):
    return {key: p.get(key) for key in ('citation','filename','document_id','authority','jurisdiction','official_url','document_title','publication_date','effective_date','verified_at','verified_by','verification_status')}


def policy_stage(passages, case):
    sources = _verified(passages, 'policy')
    if not sources:
        return {'agent':'Policy Advisor','status':'source_required','result':{
            'eligible_sources':[], 'policy_conclusion':None,
            'recommendation':'Provide applicable policy evidence with provenance and a completed authorized reviewer verification.'},
            'note':'No reviewer-verified policy passages available. Uploader labels alone are insufficient.'}
    ranked = _rank(sources, case['title'] + ' ' + case['summary'])
    excerpts = [{'citation': citation, 'verbatim_excerpt': sentence, 'provenance':_source(p)} for _, citation, sentence, p in ranked]
    return {'agent':'Policy Advisor','status':'review_required','result':{
        'eligible_sources':[_source(p) for p in sources],
        'relevant_excerpts':excerpts,
        'policy_conclusion':None,
        'recommendation':'Qualified human review must establish legal applicability, interpretation and any resulting policy recommendation.',
        'source_authentication':'reviewer_attested_not_independently_authenticated',
    },'note':'Verbatim passages from reviewer-attested documents only; no legal conclusion or claim entailment established.'}



def _comparison_candidates(summaries):
    """Build an evidence matrix without asserting legal equivalence."""
    items = []

    for item in summaries:
        excerpts = [
            e for e in item.get("source_excerpts", [])
            if e.get("citation") and e.get("verbatim_excerpt")
        ]

        if excerpts:
            items.append({
                "jurisdiction": item["jurisdiction"],
                "evidence": excerpts,
                "assessment": "requires_human_comparability_review"
            })

    if len(items) < 2:
        return None

    return {
        "type": "evidence_matrix_not_legal_comparison",
        "jurisdictions": items,
        "similarities": None,
        "differences": None,
        "transferability": "not_established",
        "conflict_status": "not_assessed",
        "legal_applicability": "not_established",
        "human_review_required": True,
        "limitations": [
            "Reviewer attestation is not independent source authentication.",
            "Excerpts do not establish the full meaning of a regulation.",
            "Legal equivalence and transferability require human review."
        ]
    }

def _comparison_draft(matrix):
    """Create citation-bound review prompts, not asserted legal conclusions.

    Matching vocabulary is a retrieval signal only; it cannot establish
    regulatory equivalence, conflict, or legal transferability.
    """
    if not matrix:
        return None
    jurisdictions = matrix['jurisdictions']
    candidates = []
    for i, left in enumerate(jurisdictions):
        for right in jurisdictions[i + 1:]:
            for a in left['evidence']:
                for b in right['evidence']:
                    common = sorted(_terms(a['verbatim_excerpt']) & _terms(b['verbatim_excerpt']))
                    if not common:
                        continue
                    candidates.append({
                        'jurisdictions': [left['jurisdiction'], right['jurisdiction']],
                        'citations': [a['citation'], b['citation']],
                        'shared_terms': common[:12],
                        'review_question': 'Do these excerpts address comparable requirements or practices?',
                        'classification': 'possible_topic_overlap_not_legal_equivalence',
                        'conflict': 'undetermined',
                        'transferability': 'not_established',
                    })
    # Generic administrative vocabulary is weak evidence of topical
    # comparability. Retain original shared terms for reviewer inspection.
    generic_terms = {
        'administrative', 'procedures', 'general', 'documentation',
        'reporting', 'registration', 'notification', 'assessment',
    }

    candidates.sort(
        key=lambda c: (
            -len(set(c['shared_terms']) - generic_terms),
            -len(c['shared_terms']),
            c['jurisdictions'],
            c['citations'],
        )
    )
    return {
        'status': 'review_required',
        'method': 'deterministic_lexical_candidate_retrieval',
        'candidates': candidates[:12],
        'policy_recommendation_drafts': [],
        'unresolved_questions': [
            'Are the cited passages authentic, current and applicable?',
            'Do the jurisdictions define the relevant terms in comparable ways?',
            'Are there conflicting provisions elsewhere in the source documents?',
            'Would adopting a practice be lawful and appropriate in the target jurisdiction?',
        ],
        'human_review_required': True,
        'limitations': 'Lexical overlap does not prove policy similarity, conflict, or legal applicability.',
    }

def benchmark_stage(passages, case):
    # Verified jurisdiction-specific policy texts can serve as comparative evidence.
    # Preserve source_type in provenance; exclude international guidance from
    # the two-jurisdiction benchmark threshold.
    sources = [
        p for p in passages
        if p.get('verification_status') == 'verified'
        and p.get('source_type') in ('benchmark', 'policy')
        and p.get('jurisdiction') and p.get('official_url')
        and p['jurisdiction'].strip().casefold() not in ('international', 'global')
    ]
    jurisdictions = {}
    for p in sources:
        jurisdiction = p['jurisdiction'].strip()
        if jurisdiction:
            jurisdictions.setdefault(jurisdiction.casefold(), {'jurisdiction':jurisdiction,'passages':[]})['passages'].append(p)
    summaries = []
    for item in sorted(jurisdictions.values(), key=lambda v: v['jurisdiction'].casefold()):
        excerpts = _benchmark_rank(item['passages'], case['title'] + ' ' + case['summary'], limit=12)
        summaries.append({'jurisdiction':item['jurisdiction'], 'source_excerpts':[
            {'citation':cid,'verbatim_excerpt':sentence,'provenance':_source(p)} for _,cid,sentence,p in excerpts]})
    ready_jurisdictions = [
        item for item in summaries if item['source_excerpts']
    ]
    enough = len(ready_jurisdictions) >= 2
    return {'agent':'Global Benchmark Agent','status':'review_required' if enough else 'source_required','result':{
        'eligible_sources':[_source(p) for p in sources],
        'jurisdiction_evidence':summaries,
        'comparison':None,
        'evidence_matrix':_comparison_candidates(summaries),
        'comparison_draft':_comparison_draft(_comparison_candidates(summaries)),
        'recommendation':('A qualified reviewer must assess comparability, applicability and differences before drawing cross-country conclusions.' if enough else 'Provide reviewer-verified benchmark evidence from at least two distinct jurisdictions.'),
        'source_authentication':'reviewer_attested_not_independently_authenticated' if sources else 'unverified',
    },'note':'Extractive jurisdiction evidence only; no automatically generated cross-country or legal conclusion.'}
