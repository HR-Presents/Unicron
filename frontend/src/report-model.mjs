// Render only documented narrative fields; never dump internal workflow objects.
const workflow = /\b(?:(?:qualified|domain|legal|policy|human) reviewer|(?:human|qualified) (?:approval|review))\b/i;
const text = value => typeof value === 'string' ? value.trim() : '';
const list = value => Array.isArray(value) ? value : [];
const unique = values => [...new Set(values.filter(Boolean))];
const prose = value => text(value) || text(value?.statement) || text(value?.description) || text(value?.action) || text(value?.observation) || text(value?.reason);
const entries = (value, filterWorkflow=false) => list(value).map(item=>({text:prose(item),citations:list(item?.citations).filter(ref=>typeof ref==='string')})).filter(item=>item.text && (!filterWorkflow||!workflow.test(item.text)));

export function readableResponse(result, agent='Review & Synthesis') {
  if(typeof result==='string')return {lead:result,sections:[]};
  if(!result||typeof result!=='object')return {lead:'No response has been recorded for this agent yet.',sections:[]};
  const sections=[];
  const section=(title,items)=>{const kept=items.filter(item=>item.text);if(kept.length)sections.push({title,items:kept});};
  let lead='';
  if(agent==='Intake & Triage'){
    lead=text(result.rationale)||text(result.classification);
    section('Immediate actions',entries(result.immediate_actions,true));
    section('Information needed',entries(result.missing_evidence));
  }else if(agent==='Evidence Analyst'){
    lead=text(result.summary);
    section('Findings',entries(result.findings||result.key_findings));
    section('Conflicting evidence',entries(result.contradictions));
    section('Evidence gaps',entries(result.gaps));
    section('Next checks',entries(result.recommended_checks,true));
  }else if(agent==='Policy Advisor'){
    lead=text(result.policy_conclusion);
    section('Relevant policy evidence',list(result.relevant_excerpts).map(item=>({text:text(item.verbatim_excerpt),citations:item.citation?[item.citation]:[],quote:true})));
    const recommendation=text(result.recommendation);
    if(recommendation&&!workflow.test(recommendation))section('Policy context',[{text:recommendation}]);
  }else if(agent==='Global Benchmark Agent'){
    const draft=result.ai_comparison_draft;
    const assessments=list(draft?.model_evidence_assessments);
    const risks=list(draft?.claim_risk_flags);
    const supported=list(draft?.comparisons).filter((_,index)=>assessments.some(item=>item.claim_index===index&&item.verdict==='supported')&&!risks.some(item=>item.claim_index===index));
    lead=supported.length?'The following comparisons have supporting passages and a recorded model assessment. They do not establish legal equivalence.':'';
    section('Supported comparisons',entries(supported));
    for(const region of list(result.jurisdiction_evidence)){
      const excerpts=list(region.source_excerpts||region.evidence);
      section(text(region.jurisdiction)||'Jurisdiction evidence',excerpts.map(item=>({text:text(item.verbatim_excerpt),citations:item.citation?[item.citation]:[],quote:true})));
    }
    if(draft&&list(draft.comparisons).length>supported.length)section('Evidence limits',[{text:'Some proposed comparisons lack supporting assessments or were contradicted. They are excluded from the supported findings.'}]);
  }else if(agent==='Scenario Evaluator'){
    lead=text(result.scenario);
    section('Hypothetical risks',entries(result.risks));
    section('Proposed safeguards',entries(result.mitigations,true));
    section('Assumptions',entries(result.assumptions));
  }else{
    lead=text(result.case_summary)||text(result.summary);
    section('What the evidence shows',entries(result.evidence_summary?.findings||result.findings));
    section('Recommended next steps',entries(result.recommended_next_steps,true));
    const uncertain=unique([...entries(result.unresolved_questions).map(item=>item.text),...entries(result.evidence_summary?.gaps).map(item=>item.text)]);
    section('What remains uncertain',uncertain.map(value=>({text:value})));
  }
  const limitations=[];
  for(const item of list(result.evidence_limitations||result.review_gates)){
    if(item.code==='qualified_review_required')limitations.push('The available evidence does not establish legal applicability.');
    else if(item.code?.includes('comparison_evidence'))limitations.push('Some proposed international comparisons are unsupported or contradicted and must not be treated as established findings.');
    else if(item.code?.includes('semantic_assessment'))limitations.push('An independent assessment of the comparison against its source passages is unavailable.');
    else if(item.code?.includes('scenario_assumptions'))limitations.push('Scenario assumptions and the effectiveness of proposed safeguards remain unverified.');
    else if(text(item.reason))limitations.push(text(item.reason));
  }
  for(const item of list(result.guardrail_flags)){
    if(item.code?.includes('jurisdictional'))limitations.push('Foreign legal requirements have not been established as applicable to this case.');
    if(item.code?.includes('assumption'))limitations.push('The scenario relies on assumptions that have not been verified.');
  }
  if(result.standards_traceability?.status==='not_assessed')limitations.push('Standards alignment has not yet been assessed for this case.');
  section('Evidence limitations',unique(limitations).map(value=>({text:value})));
  if(!lead&&!sections.length){
    const fallback=['rationale','assessment','recommendation','policy_conclusion'].map(key=>text(result[key])).filter(value=>value&&!workflow.test(value));
    lead=fallback[0]||'This agent has not recorded a supported narrative finding. Evidence availability and execution status are shown alongside its name.';
  }
  return {lead,sections,priority:agent==='Intake & Triage'?text(result.recommended_priority):'',hypothetical:agent==='Scenario Evaluator'};
}

export function responseCitations(result,agent){
  const view=readableResponse(result,agent);
  return unique(view.sections.flatMap(section=>section.items.flatMap(item=>item.citations||[])));
}
