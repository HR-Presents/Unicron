import React from 'react';
import {Icon} from './Icons.jsx';
import {agents,selectStage,stageStatus} from './agents.mjs';

const dayTime=value=>value?new Date(value).toLocaleString('en-GB',{timeZone:'Asia/Dubai',dateStyle:'medium',timeStyle:'short'})+' GST':'';
const hiddenKey=/^(?:raw(?:_.*)?|chain_of_thought|thinking|reasoning_content|worker_id|api_key|error_type|error_message)$/i;
const label=key=>key.replaceAll('_',' ');

export function DataValue({value,sourceLink=false}){
  if(value===null || value===undefined || value==='')return <span>—</span>;
  if(Array.isArray(value))return value.length?<ul className="output-list">{value.map((item,index)=><li key={index}><DataValue value={item}/></li>)}</ul>:<span>None recorded</span>;
  if(typeof value==='object')return <dl className="output-fields">{Object.entries(value).filter(([key])=>!hiddenKey.test(key)).map(([key,item])=><div key={key}><dt>{label(key)}</dt><dd><DataValue value={item} sourceLink={key==='official_url'}/></dd></div>)}</dl>;
  if(typeof value==='boolean')return <span>{value?'Yes':'No'}</span>;
  if(sourceLink && typeof value==='string' && /^https:\/\//i.test(value))return <a className="inline-action" href={value} rel="noreferrer" target="_blank">Source reference <Icon name="right" size={13}/></a>;
  return <span>{String(value)}</span>;
}

function AgentOutput({agent,result}){
  if(!result || typeof result!=='object')return <DataValue value={result}/>;
  const used=new Set(agent.sections.flatMap(([,keys])=>keys));
  const groups=agent.sections.map(([title,keys])=>[title,Object.fromEntries(keys.filter(key=>Object.hasOwn(result,key)).map(key=>[key,result[key]]))]).filter(([,fields])=>Object.keys(fields).length);
  const rest=Object.fromEntries(Object.entries(result).filter(([key])=>!used.has(key) && !hiddenKey.test(key)));
  return <div className="agent-output">
    {groups.map(([title,fields],i)=><details className="output-group" key={title} open={i===0 || undefined}><summary>{title}</summary><DataValue value={fields}/></details>)}
    {Object.keys(rest).length>0 && <details className="output-group"><summary>Additional findings</summary><DataValue value={rest}/></details>}
  </div>;
}

export default function AgentBoard({activeAgent,selected,onSelect,events,records,historical,setHistorical,inProgress,onAsk,onRun,onEvidence,onScenario,available,busy,deskAvailable}){
  const agent=agents.find(item=>item.id===selected)??agents[0];
  const history=records?.investigations?.find(item=>item.id===historical);
  const output=selectStage(agent,events,history,records,inProgress);
  const stage=output?.stage;
  return <div className="detail-body agent-workbench">
    <div className="detail-heading">
      <div><div className="eyebrow small">MULTI-AGENT OPERATIONS</div><h2>Agent activity</h2></div>
      {Boolean(records?.investigations?.length) && <label className="history-select">Investigation view<select value={historical} onChange={event=>setHistorical(event.target.value)}><option value="">Current activity</option>{records.investigations.map(run=><option key={run.id} value={run.id}>{dayTime(run.created_at)} · {run.id.slice(0,8)}</option>)}</select></label>}
    </div>
    <div className="agent-grid" aria-label="Six configured agents">
      {agents.map(item=>{
        const selectedOutput=selectStage(item,events,history,records,inProgress);
        const isRunning=!historical && inProgress && activeAgent===item.name;
        return <button key={item.id} type="button" aria-pressed={item.id===agent.id} aria-current={isRunning?'step':undefined} onClick={()=>onSelect(item.id)} className={`agent-card${isRunning?' agent-card-running':''}`} style={{'--agent-color':item.color}}>
          <span className="agent-card-top"><span className="agent-icon"><Icon name={item.icon} size={17}/></span><small>{item.code}</small></span>
          <strong>{item.name}</strong><span className="agent-card-state">{isRunning?'Running':stageStatus(selectedOutput?.stage.status)}</span>
        </button>;
      })}
    </div>
    <section className="agent-inspector" aria-label={agent.name+' response'}>
      <div className="inspector-heading">
        <div><div className="eyebrow small">{agent.kind}</div><h3>{agent.name}</h3><p>{agent.description}</p></div>
        <span className={'agent-pill agent-pill-'+(stage?.status??'idle')}>{stageStatus(stage?.status)}</span>
      </div>
      {output && <p className="output-meta">{output.origin}{output.time && ' · '+dayTime(output.time)}{output.model && ' · '+output.model}</p>}
      {stage?.note && !stage.note.startsWith('Run /') && <p className="output-note">{stage.note}</p>}
      {stage?.result ? <AgentOutput agent={agent} result={stage.result}/> : <p className="output-note">{inProgress?'The investigation has not recorded this checkpoint yet.':'A response appears here after this agent records an output.'}</p>}
      {Boolean(stage?.community_knowledge?.length) && <details className="output-group"><summary>Moderated community context</summary><p>For context during review.</p><DataValue value={stage.community_knowledge}/></details>}
      <div className="inspector-actions">
        {['triage','evidence'].includes(agent.id) && <button className="button primary" disabled={!available || busy || (agent.id==='evidence' && !records?.evidence?.length)} onClick={()=>onRun(agent.id)}><Icon name="play" size={15}/> {agent.id==='triage'?'Run triage':'Analyze evidence'}</button>}
        {['evidence','policy_gap','benchmark'].includes(agent.id) && <button className="button secondary" onClick={onEvidence}><Icon name="file" size={15}/> Open evidence</button>}
        {agent.id==='continuity' && <button className="button secondary" onClick={onScenario}><Icon name="layers" size={15}/> Open Scenario Lab</button>}
        <button className="button secondary" disabled={!deskAvailable} onClick={()=>onAsk(agent.id)}><Icon name="spark" size={15}/> Ask this agent</button>
      </div>
    </section>
  </div>;
}
