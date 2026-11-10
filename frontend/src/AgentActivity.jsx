import React from 'react';
import ReportResponse from './ReportResponse.jsx';

export const agentModes={'Intake & Triage':'triage','Evidence Analyst':'evidence','Policy Advisor':'policy_gap','Global Benchmark Agent':'benchmark','Scenario Evaluator':'continuity','Review & Synthesis':'synthesis'};
const labels={completed:'Completed',running:'Working',queued:'Queued',failed:'Failed',source_required:'Sources missing',needs_run:'Inputs missing',interrupted:'Interrupted',review_required:'Evidence limitations'};

export function recordedStages(events=[],latest){
  return Object.fromEntries((latest?.stages||[]).map(stage=>[stage.agent,stage]).concat(events.filter(event=>event.stage).map(event=>[event.agent,event.stage])));
}

export default function AgentActivity({names,events,latest,snapshot,active,online,caseId,open,selected,onSelect,onClose}){
  const stages=recordedStages(events,latest);
  const current=active?snapshot?.execution?.last_agent:null;
  const focused=selected||current||null;
  const stage=stages[focused];
  return <aside className={'agents-sidebar '+(open?'is-open':'')} aria-label="Investigation agents">
    <header className="agents-header"><div><h2>Agents <span>06</span></h2><p>{active?'Investigation in progress':caseId?'Recorded investigation activity':'Ready when you have a case'}</p></div><button className="icon-button close-agents" onClick={onClose} aria-label="Close agents panel">×</button></header>
    <button className={'agent-overview '+(!selected?'selected':'')} onClick={()=>onSelect(null)}>Investigation overview <span>↗</span></button>
    <div className="agents-nav">{names.map((name,index)=>{
      const status=stages[name]?.status||(current===name?'running':null);
      const label=status?(labels[status]||status):active?'Waiting':online?'Not started':'Offline';
      return <button key={name} className={'agent-nav-item '+(focused===name?'selected':'')} onClick={()=>onSelect(name)} aria-pressed={selected===name}>
        <span className="agent-index">0{index+1}</span><span className="agent-name">{name}<small>{label}</small></span><span className={'agent-dot '+(status==='running'?'working':status==='completed'?'done':'')} aria-hidden="true"/>
      </button>;
    })}</div>
    <div className="agent-reading"><div className="agent-reading-heading"><span>RECORDED RESPONSE</span><h3>{focused||'Independent assessments'}</h3></div>{stage?.result?<ReportResponse key={focused} result={stage.result} agent={focused} compact/>:<p className="agent-empty">{active&&current&&current===focused?'This agent is processing your investigation. Its response will appear when the backend records it.':caseId?'A recorded response appears here when this agent executes.':'Describe a case to run an investigation. Select an agent to read its recorded assessment and ask a focused follow-up.'}</p>}</div>
  </aside>;
}
