import React from 'react';
import {DataValue} from './ResponseData.jsx';

const labels={completed:'Completed',running:'Running',queued:'Queued',failed:'Failed',
  source_required:'Sources missing',needs_run:'Inputs missing',interrupted:'Interrupted',
  review_required:'Evidence limitations'};

export default function AgentActivity({names,events,latest,snapshot,active,online,caseId}) {
  const current=active?snapshot?.execution?.last_agent:null;
  return <details className="agent-panel visible-agents" open>
    <summary><span className="agent-heading">Agents <span className="agent-total">06</span></span>
      <small>{active?'Investigation in progress':caseId?(snapshot?.job?.status||'Not started'):'No investigation selected'}</small>
      <span className="agent-chevron" aria-hidden="true">⌄</span>
    </summary>
    <p className="agent-explanation">Six autonomous specialists. Select an agent to inspect its recorded findings.</p>
    <div className="agent-roster">{names.map((name,index)=>{
      const event=events.findLast(item=>item.agent===name);
      const stage=event?.stage||latest?.stages?.find(item=>item.agent===name);
      const status=stage?.status||event?.status||(current===name?'running':null);
      const label=status?(labels[status]||status):(active?'Waiting':online?'Not started':'Offline');
      return <details className={'agent-entry '+(status==='running'?'is-running':'')} key={name}>
        <summary><span className="agent-index">0{index+1}</span><span className="agent-name">{name}<small>{label}</small></span><span className="agent-state" aria-hidden="true">{status==='completed'?'✓':status==='running'?'•':'—'}</span></summary>
        <div className="agent-detail">{stage?.result?<DataValue value={stage.result}/>:<p>{status==='running'?'This agent is processing the selected investigation.':!online?'Connect the intelligence backend to run an investigation.':'Recorded findings appear here when this agent executes. Asking a general question does not start an investigation.'}</p>}</div>
      </details>;
    })}</div>
  </details>;
}
