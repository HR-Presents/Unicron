import React,{useEffect,useRef} from 'react';
import ReportResponse from './ReportResponse.jsx';
import {agents} from './agents.mjs';

export const agentModes={'Intake & Triage':'triage','Evidence Analyst':'evidence','Policy Advisor':'policy_gap','Global Benchmark Agent':'benchmark','Scenario Evaluator':'continuity','Review & Synthesis':'synthesis'};
const labels={completed:'Completed',running:'Working',queued:'Queued',failed:'Failed',source_required:'Sources missing',needs_run:'Inputs missing',interrupted:'Interrupted',review_required:'Evidence limitations'};

export function recordedStages(events=[],latest){
  return Object.fromEntries((latest?.stages||[]).map(stage=>[stage.agent,stage]).concat(events.filter(event=>event.stage).map(event=>[event.agent,event.stage])));
}

export default function AgentActivity({names,events,latest,snapshot,active,online,caseId,open,selected,onSelect,onClose}){
  const responseRef=useRef(null);
  useEffect(()=>{if(open&&selected)responseRef.current?.scrollIntoView({block:'nearest',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'})},[open,selected]);
  if(!open)return null;
  const stages=recordedStages(events,latest);
  const current=active?snapshot?.execution?.last_agent:null;
  const stage=selected?stages[selected]:null;
  return <section className="agent-panel" aria-labelledby="agent-panel-title">
    <header className="agent-panel-header"><div><p className="panel-kicker">THE INTELLIGENCE TEAM</p><h2 id="agent-panel-title">Six perspectives. One investigation.</h2><p>Select an agent to inspect its recorded response and ask a focused follow-up.</p></div><button className="icon-button" onClick={onClose} aria-label="Close agents panel">×</button></header>
    <div className="agent-card-grid">{names.map((name,index)=>{
      const status=stages[name]?.status||(current===name?'running':null);
      const label=status?(labels[status]||status):active?'Waiting':caseId?'Not started':online?'Ready':'Backend offline';
      return <button key={name} className={'agent-card '+(selected===name?'selected':'')} onClick={()=>onSelect(selected===name?null:name)} aria-pressed={selected===name} aria-controls="agent-response">
        <div className="agent-card-top"><span>0{index+1}</span><span className="agent-card-status"><span className={'agent-dot '+(status==='running'?'working':status==='completed'?'done':'')} aria-hidden="true"/>{label}</span></div>
        <h3>{name}</h3><p>{agents.find(agent=>agent.name===name)?.description}</p><span className="agent-card-action">{stages[name]?.result?'Read assessment':'About this agent'} <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M7 17 17 7M7 7h10v10"/></svg></span>
      </button>;
    })}</div>
    {selected&&<section className="agent-card-response" id="agent-response" ref={responseRef} aria-label={selected+' response'}><header><h3>{selected}</h3><button onClick={()=>onSelect(null)} aria-label="Close selected agent response">×</button></header>{stage?.result?<ReportResponse key={selected} result={stage.result} agent={selected}/>:<p className="agent-empty">{active&&current===selected?'This agent is processing the case. Its response will appear here when recorded.':caseId?'This agent has no recorded assessment for this investigation yet.':'Start an investigation to see this agent’s assessment.'}</p>}</section>}
  </section>;
}
