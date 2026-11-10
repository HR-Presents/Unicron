export const agents=[
  {id:'triage',name:'Intake & Triage',short:'Intake',code:'INT',color:'#8fc49e',icon:'grid',department:'intake',kind:'Model-backed',description:'Classifies the incident, sets a provisional priority and identifies immediate checks.',sections:[
    ['Assessment',['classification','recommended_priority','rationale']],['Next steps',['missing_evidence','immediate_actions']],
  ]},
  {id:'evidence',name:'Evidence Analyst',short:'Evidence',code:'EVD',color:'#8abac0',icon:'file',department:'evidence',kind:'Model-backed',description:'Produces cited findings, flags evidence gaps and contradictions, and proposes verification checks.',sections:[
    ['Cited findings',['findings']],['Gaps and validation',['gaps','contradictions','recommended_checks']],
  ]},
  {id:'policy_gap',name:'Policy Advisor',short:'Policy',code:'POL',color:'#ccad76',icon:'shield',department:'policy',kind:'Verified-source analysis',description:'Finds relevant policy passages, identifies regulatory gaps and explains applicability limits.',sections:[
    ['Relevant policy excerpts',['relevant_excerpts','policy_conclusion','recommendation']],['Eligible sources',['eligible_sources','source_authentication']],
  ]},
  {id:'benchmark',name:'Global Benchmark Agent',short:'Benchmark',code:'BEN',color:'#a9b388',icon:'compass',department:'policy',kind:'Evidence matrix and model draft',description:'Compares verified sources across jurisdictions and records draft claims with their supporting citations.',sections:[
    ['Comparison draft',['ai_comparison_draft','ai_analysis_status','comparison']],['Jurisdiction evidence',['jurisdiction_evidence','evidence_matrix','comparison_draft']],['Sources and limitations',['eligible_sources','limitations','recommendation']],
  ]},
  {id:'continuity',name:'Scenario Evaluator',short:'Scenario',code:'SCN',color:'#b9a78b',icon:'layers',department:'lab',kind:'Model-backed',description:'Explores plausible failure scenarios, practical safeguards and the assumptions behind them.',sections:[
    ['Scenario assessment',['scenario','risks','mitigations','assumptions']],['Risk register and review flags',['risk_register','guardrail_flags','legal_applicability','assumptions_verified','human_review_required','automated_approval_permitted']],
  ]},
  {id:'synthesis',name:'Review & Synthesis',short:'Synthesis',code:'REV',color:'#bbaac4',icon:'history',department:'oversight',kind:'Autonomous advisory synthesis',description:'Combines the recorded assessments into clear findings, prioritized next steps and honest uncertainty.',sections:[
    ['Advisory brief',['case_summary','recommended_next_steps','unresolved_questions']],['Human review',['review_gates','prioritized_review_actions','human_review_required','automated_approval_permitted']],
  ]},
];

const statusNames={completed:'Recorded',review_required:'Review required',source_required:'Sources needed',needs_run:'Input needed',failed:'Failed',queued:'Queued',running:'Running',interrupted:'Interrupted'};
export const stageStatus=status=>statusNames[status]??'Awaiting run';

export function selectStage(agent,events,history,records,inProgress=false){
  const event=history?null:events.findLast(item=>item.agent===agent.name);
  const stage=history?.stages?.find(item=>item.agent===agent.name)??event?.stage;
  const standalone=agent.id==='triage'?records?.triage?.[0]:agent.id==='evidence'?records?.analyses?.[0]:null;
  if(!history && !inProgress && standalone?.result && (!event || Date.parse(standalone.created_at)>Date.parse(event.created_at))){
    return {stage:{agent:agent.name,status:'completed',result:standalone.result},time:standalone.created_at,origin:'Standalone analysis',model:standalone.model};
  }
  return stage?{stage,time:history?.created_at??event?.created_at,origin:history?'Saved investigation':'Investigation checkpoint'}:null;
}
