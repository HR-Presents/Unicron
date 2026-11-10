import test from 'node:test';
import assert from 'node:assert/strict';
import {readableResponse,responseCitations} from '../src/report-model.mjs';

const report={case_summary:'A public hospital proposes AI triage.',
  recommended_next_steps:['Have a domain reviewer validate scenario assumptions before operational use.','Document the data flows and consent process.'],
  unresolved_questions:['Which data crosses a jurisdictional boundary?'],
  evidence_summary:{findings:[{statement:'The source defines personal data.',citations:['policy-doc#p2']}],gaps:[]},
  evidence_limitations:[{agent:'Policy Advisor',code:'qualified_review_required',action:'Obtain qualified review.'},{code:'comparison_evidence_insufficient_or_contradicted'}],
  validation_recommendations:[{owner:'qualified_legal_reviewer',status:'review_required',action:'An unapproved compliance proposal.'}],
  standards_traceability:{status:'not_assessed',counts:{pending:0}},human_review_required:false};

test('synthesis becomes readable findings, next steps and explicit uncertainty',()=>{
  const view=readableResponse(report);
  assert.equal(view.lead,report.case_summary);
  assert(view.sections.some(section=>section.title==='What the evidence shows'));
  assert.deepEqual(responseCitations(report),['policy-doc#p2']);
  const text=JSON.stringify(view);
  assert(text.includes('Document the data flows'));
  assert(text.includes('does not establish legal applicability'));
  assert(text.includes('unsupported or contradicted'));
  assert(!text.includes('qualified_legal_reviewer'));
  assert(!text.includes('Have a domain reviewer'));
  assert(!text.includes('None recorded'));
  assert(!text.includes('unapproved compliance proposal'));
});

test('a flagged model-assessed comparison is not presented as supported',()=>{
  const result={ai_comparison_draft:{comparisons:[
    {observation:'The laws conflict.',citations:['EU#p1','UAE#p2']},
    {observation:'Both excerpts discuss notices.',citations:['EU#p3','UAE#p4']}],
    model_evidence_assessments:[{claim_index:0,verdict:'supported'},{claim_index:1,verdict:'supported'}],
    claim_risk_flags:[{claim_index:0,code:'unproven_legal_conflict'}]}};
  const view=readableResponse(result,'Global Benchmark Agent');
  const supported=view.sections.find(section=>section.title==='Supported comparisons');
  assert.equal(supported.items.length,1);
  assert.equal(supported.items[0].text,'Both excerpts discuss notices.');
  assert.deepEqual(responseCitations(result,'Global Benchmark Agent'),['EU#p3','UAE#p4']);
});

test('agent responses use each real agent narrative shape',()=>{
  const fixtures=[
    ['Intake & Triage',{classification:'Healthcare',rationale:'The case involves patient triage.',immediate_actions:['Map the data flow.']}],
    ['Evidence Analyst',{findings:[{statement:'The passage defines data.',citations:['doc#p1']}]}],
    ['Policy Advisor',{relevant_excerpts:[{verbatim_excerpt:'An exact policy excerpt.',citation:'doc#p2'}]}],
    ['Scenario Evaluator',{scenario:'Hypothetical triage service outage.',risks:['Delayed care.'],mitigations:['Provide a fallback route.']}],
  ];
  for(const [agent,result] of fixtures){const view=readableResponse(result,agent);assert(view.lead||view.sections.length);assert(!JSON.stringify(view).includes('No response has been recorded'))}
  assert(readableResponse(fixtures[3][1],fixtures[3][0]).hypothetical);
});

test('required human oversight in documentary evidence is not hidden as workflow boilerplate',()=>{
  const view=readableResponse({evidence_summary:{findings:[{statement:'The excerpt describes human oversight of high-risk AI.',citations:['doc#p7']}]}});
  assert(JSON.stringify(view).includes('human oversight of high-risk AI'));
});

test('scope exclusions and withheld obligations are visible without repeating unsupported advice',()=>{
  const result={case_summary:'A hospital is considering AI appointments.',recommended_next_steps:['Map clinical-data access roles.'],
    scope_cautions:[{citation:'scope#p2',reason:'Government and health-data scope exclusions remain unresolved.'}],
    withheld_claims:[{text:'Ensure compliance with the EU AI Act.'}],
    output_quality_flags:[{reason:'An unestablished compliance claim was withheld.'}]};
  const view=readableResponse(result);
  assert(view.sections.some(section=>section.title==='Scope and applicability'));
  assert(JSON.stringify(view).includes('claim was withheld'));
  assert(!JSON.stringify(view).includes('Ensure compliance'));
  assert.deepEqual(responseCitations(result),['scope#p2']);
});
