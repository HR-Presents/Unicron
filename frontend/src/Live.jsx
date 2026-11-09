import React,{useEffect,useMemo,useRef,useState} from 'react';
import {Icon} from './Icons.jsx';
import Twin from './Twin.jsx';
import Evaluation from './Evaluation.jsx';
import {api,forCase,runSnapshot,caseRecords,departmentFor} from './live-api.mjs';
import AgentBoard,{DataValue} from './AgentBoard.jsx';
import {agents,stageStatus} from './agents.mjs';
import {exportSnapshot,verifySnapshot} from './audit-export.mjs';
import EvidenceWorkbench from './EvidenceWorkbench.jsx';
import StandardsPanel from './StandardsPanel.jsx';
import {NewCase,ScenarioAuthor} from './CaseForms.jsx';
import {citizenRoutes,deriveHandoffs,handoffColor} from './twin-flow.mjs';

const checks=[
  ['activity','motion','Agent activity'],['scenario','layers','Scenario lab'],['evidence','file','Evidence'],['standards','shield','Standards'],['assistant','spark','AI desk'],['audit','link','Audit'],['evaluation','shield','Readiness'],
];
const emptyList=[];
const connectionLoader=(_,signal)=>api('/connection',{signal});
const casesLoader=(_,signal)=>api('/cases',{signal});
const pretty=value=>String(value??'').replaceAll('_',' ');
const time=value=>value?new Date(value).toLocaleTimeString('en-GB',{timeZone:'Asia/Dubai'}):'—';

function usePoll(load,key,interval,revision) {
  const [snapshot,setSnapshot]=useState(null);
  useEffect(()=>{
    if(key===null || key===undefined)return undefined;
    const controller=new AbortController();
    let timer;
    async function poll() {
      try {
        const value=await load(key,controller.signal);
        if(!controller.signal.aborted)setSnapshot({key,value,updated:Date.now(),error:''});
      } catch(error) {
        if(!controller.signal.aborted)setSnapshot(previous=>({
          key,value:previous?.key===key?previous.value:null,updated:previous?.key===key?previous.updated:null,error:error.message,
        }));
      } finally {
        if(!controller.signal.aborted)timer=setTimeout(poll,interval);
      }
    }
    void poll();
    return ()=>{controller.abort();clearTimeout(timer);};
  },[load,key,interval,revision]);
  return snapshot && snapshot.key===key?snapshot:{};
}

function exportCase(caseId,run,records) {
  const content=exportSnapshot(caseId,run,records);
  if(!verifySnapshot(content))return false;
  const url=URL.createObjectURL(new Blob([JSON.stringify(content,null,2)],{type:'application/json'}));
  const link=document.createElement('a');
  link.href=url;
  link.download=`unicron-${caseId.toLowerCase()}-evidence.json`;
  link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
  return true;
}

function EvidenceDesk({id,configured,connected,initialAgent}) {
  const [question,setQuestion]=useState('');
  const [mode,setMode]=useState(initialAgent);
  const [reply,setReply]=useState(null);
  const [pending,setPending]=useState(false);
  const [error,setError]=useState('');
  const controller=useRef(null);
  useEffect(()=>()=>controller.current?.abort(),[]);
  async function ask(event) {
    event.preventDefault();
    if(pending || !connected || !configured)return;
    controller.current=new AbortController();
    setPending(true);setError('');setReply(null);
    try {setReply(await api(forCase(id)+'/desk',{method:'POST',body:{question,mode},signal:controller.current.signal}));}
    catch(failure){if(!controller.current.signal.aborted)setError(failure.message);}
    finally {if(!controller.current.signal.aborted)setPending(false);}
  }
  return <div className="detail-body">
    <div className="detail-heading"><div><div className="eyebrow small">CASE EVIDENCE</div><h2>AI desk</h2></div><span className="meta-tag">{configured?'FOLLOW-UP AVAILABLE':'FOLLOW-UP UNAVAILABLE'}</span></div>
    <p className="detail-copy">Ask a follow-up in one of the six agent roles. Answers use the selected case’s evidence and identify uncertainties.</p>
    <form onSubmit={ask} className="ask-form role-ask"><label className="role-select">Agent role<select value={mode} onChange={event=>{setMode(event.target.value);setReply(null);setError('');}} disabled={pending}>{agents.map(agent=><option key={agent.id} value={agent.id}>{agent.name}</option>)}</select></label><label className="sr-only" htmlFor="live-question">Question for the briefing agent</label><input id="live-question" maxLength={400} placeholder="What evidence supports the continuity plan?" value={question} onChange={event=>setQuestion(event.target.value)}/><button className="button primary" disabled={!configured || !connected || pending || question.trim().length<4}>{pending?'Analyzing…':'Ask agent'} <Icon name="spark" size={16}/></button></form>
    {error && <p className="error" role="alert">{error}</p>}
    {reply && <article className="record desk-response" aria-live="polite">
      <p>{reply.answer}</p>
      {reply.uncertainty && <p><strong>Uncertainty</strong> {reply.uncertainty}</p>}
      {reply.model && <small>{reply.model} · {(reply.elapsedMs/1000).toFixed(1)}s</small>}
      {reply.citations?.map(citation=><details key={citation.id}><summary>{citation.title} · {citation.verification}</summary><p>{citation.text}</p><code>{citation.id}</code></details>)}
    </article>}
  </div>;
}

function ScenarioLab({id,sessions,mutate,busy,connected}) {
  const [sessionId,setSessionId]=useState('');
  const session=sessions.find(item=>item.id===sessionId)??sessions[0];
  const available=session?.status==='running';
  async function create(payload) {
    const created=await mutate(forCase(id)+'/scenario-sessions',payload);
    if(created)setSessionId(created.id);
    return created;
  }
  function act(action){return mutate(forCase(id)+`/scenario-sessions/${session.id}/${action}`);}
  return <div className="detail-body">
    <div className="detail-heading"><div><div className="eyebrow small">PROGRESSIVE EVENT RELEASE · EXERCISE</div><h2>Scenario lab</h2></div>{session && <span className="meta-tag">{pretty(session.status)}</span>}</div>
    <div className="live-action-row">
      <ScenarioAuthor create={create} disabled={busy || !connected}/>
      {sessions.length>0 && <label>Saved session <select value={session?.id??''} onChange={event=>setSessionId(event.target.value)}>{sessions.map(item=><option key={item.id} value={item.id}>{item.name} · {pretty(item.status)} · {time(item.created_at)}</option>)}</select></label>}
    </div>
    {session && <>
      <p className="detail-copy">{session.initial_conditions}</p>
      <p className="detail-copy">Each hypothetical event is released in sequence for the assigned role.</p>
      {session.status==='completed' && session.expected_outcome && <p className="detail-copy"><strong>Expected outcome</strong> {session.expected_outcome}</p>}
      <div className="live-action-row">
        {session.status==='draft' && <button className="button primary" disabled={busy || !connected} onClick={()=>act('start')}>Start session <Icon name="play" size={14}/></button>}
        {available && <><button className="button primary" disabled={busy || !connected} onClick={()=>act('evaluate-next')}>Release and evaluate <Icon name="spark" size={15}/></button><button className="button secondary" disabled={busy || !connected} onClick={()=>act('next')}>Release for operator</button><button className="button secondary" disabled={busy || !connected} onClick={()=>act('pause')}>Pause</button></>}
        {session.status==='paused' && <button className="button primary" disabled={busy || !connected} onClick={()=>act('resume')}>Resume session</button>}
      </div>
      <div className="scenario-events">
        {session.events?.map((event,index)=>{
          const assessment=session.assessments?.find(item=>item.stimulus_id===event.id);
          return <article className="record" key={event.id}><div><span className="ref static">{String(index+1).padStart(2,'0')}</span><span className="micro">{event.released_at?event.target_agent:'HELD FOR RELEASE'}</span></div>
            {event.released_at && <><h3>{event.title}</h3><p>{event.description}</p>{assessment && <details><summary>Model assessment · {assessment.model}</summary><DataValue value={assessment.result}/></details>}</>}
          </article>;
        })}
      </div>
    </>}
  </div>;
}

function AdvisoryReview({id,investigation,reviews,mutate,busy,connected,reviewAvailable}) {
  const [ack,setAck]=useState(false);
  const existing=reviews.find(review=>review.investigation_id===investigation?.id);
  if(!investigation?.id)return null;
  const blocked=investigation.stages?.some(stage=>!['completed','review_required'].includes(stage.status));
  async function submit(event) {
    event.preventDefault();
    const fields=new FormData(event.currentTarget);
    const decision=event.nativeEvent.submitter?.value;
    if(!decision)return;
    await mutate(forCase(id)+`/investigations/${investigation.id}/reviews`,{
      decision,reviewer:fields.get('reviewer'),rationale:fields.get('rationale'),acknowledged_limitations:ack,
    });
  }
  return <div className="review-box">
    <h3>Human review</h3>
    {existing?<p>{pretty(existing.decision)} · {existing.reviewer} · {existing.rationale}</p>:!reviewAvailable?<p>A qualified reviewer is required to record a decision.</p>:<form onSubmit={submit}>
      <label>Reviewer name <input name="reviewer" required minLength={2} maxLength={120}/></label>
      <label>Decision rationale <textarea name="rationale" minLength={10} maxLength={2000} required/></label>
      <label className="checkbox"><input type="checkbox" checked={ack} onChange={event=>setAck(event.target.checked)}/> I acknowledge the limitations of this advisory run.</label>
      {blocked && <p className="detail-copy">Approval requires all evidence-dependent stages to be complete.</p>}
      <div className="review-actions"><button className="button secondary" value="changes_requested" disabled={busy || !connected}>Request changes</button><button className="button primary" value="approved" disabled={busy || !connected || !ack || blocked}>Approve advisory output</button></div>
    </form>}
  </div>;
}

export default function Live({motion}) {
  const [selected,setSelected]=useState('');
  const [panel,setPanel]=useState('activity');
  const [agentId,setAgentId]=useState('triage');
  const [askAgent,setAskAgent]=useState('evidence');
  const [historical,setHistorical]=useState('');
  const [wasOnline,setWasOnline]=useState(false);
  const [revision,setRevision]=useState(0);
  const [busy,setBusy]=useState(false);
  const [actionError,setActionError]=useState('');
  const [auditNotice,setAuditNotice]=useState('');
  const [focus,setFocus]=useState('overview');
  const [follow,setFollow]=useState(true);
  const [flat,setFlat]=useState(false);
  const [showAgents,setShowAgents]=useState(true);
  const [showHandoffs,setShowHandoffs]=useState(true);
  const [flow,setFlow]=useState('all');
  const [cameraView,setCameraView]=useState('overview');
  const [zoom,setZoom]=useState(null);
  const [viewReset,setViewReset]=useState(0);
  const lock=useRef(false);
  const map=useRef(null);
  const [mapVisible,setMapVisible]=useState(false);
  const connection=usePoll(connectionLoader,'workspace',15000,revision);
  const online=connection.value?.state==='connected' && !connection.error;
  const deskAvailable=online && connection.value.deskConfigured;
  const reviewAvailable=online && connection.value.reviewAvailable;
  useEffect(()=>{if(online)setWasOnline(true);},[online]);
  const caseList=usePoll(casesLoader,online || wasOnline?'cases':null,6500,revision);
  const cases=caseList.value??emptyList;
  const id=cases.find(item=>item.id===selected)?.id??cases[0]?.id;
  const selectedCase=cases.find(item=>item.id===id);
  const runs=usePoll(runSnapshot,id,2800,revision);
  const records=usePoll(caseRecords,id,8200,revision);
  const run=runs.value;
  const info=records.value;
  const liveEvents=run?.events??emptyList;
  const jobStatus=run?.job?.status;
  const jobActive=['queued','running'].includes(jobStatus);
  const savedInvestigation=info?.investigations?.find(
    item=>item.id===historical
  )??info?.investigations?.[0];
  const savedEvents=(savedInvestigation?.stages??emptyList).map(stage=>({
    agent:stage.agent,
    status:stage.status,
    stage,
    created_at:savedInvestigation.created_at
  }));
  const events=historical
    ? savedEvents
    : liveEvents.length
      ? liveEvents
      : savedEvents;
  const progressEvents=historical
    ? savedEvents
    : jobStatus==='queued'
      ? emptyList
      : jobStatus==='running'
        ? liveEvents
        : jobStatus==='completed'
          ? liveEvents.length ? liveEvents : savedEvents
          : events;
  const completedStages=agents.filter(agent=>
    progressEvents.some(event=>event.agent===agent.name)
  ).length;
  const progressPercent=Math.round(completedStages/agents.length*100);
  const activeAgent=jobStatus==='running' && !historical
    ? run?.execution?.current_agent
    : null;
  const progressLabel=jobStatus==='queued' && !historical
    ? Number.isInteger(run?.job?.queue_position)
      ? `Queue position: ${run.job.queue_position} · Waiting for an available worker`
      : 'Waiting for the investigation worker'
    : jobStatus==='running' && !historical
      ? activeAgent
        ? `Executing: ${activeAgent} · ${completedStages} of ${agents.length} checkpoints recorded`
        : `Starting investigation · ${completedStages} of ${agents.length} checkpoints recorded`
      : `${completedStages} of ${agents.length} checkpoints recorded`;
  const handoffs=useMemo(()=>deriveHandoffs(events),[events]);
  const routes=flow==='all' ? citizenRoutes : citizenRoutes.filter(route=>route.id===flow);
  const lastHandoff=handoffs.at(-1);
  const latest=events.at(-1);
  const active=jobStatus==='running' && !historical
    ? departmentFor(activeAgent)
    : departmentFor(latest?.agent);
  const currentFocus=follow
    ? (jobStatus==='running' && active ? active : 'overview')
    : focus;
  const stale=runs.error || records.error || caseList.error;
  const currentStatus=jobActive && !liveEvents.length && savedEvents.length
    ? 'queued_with_history'
    : jobStatus??run?.execution?.status;
  const runTime=jobStatus==='completed' ? Math.max(0,(Date.parse(run.job.updated_at)-Date.parse(run.job.created_at))/1000) : null;

  useEffect(()=>{
    const observer=new IntersectionObserver(([entry])=>setMapVisible(entry.isIntersecting));
    if(map.current)observer.observe(map.current);
    return ()=>observer.disconnect();
  },[]);
  useEffect(()=>{setActionError('');setAuditNotice('');setFocus('overview');setHistorical('');setAgentId('triage');},[id]);

  async function mutate(path,body,options={}){
    if(lock.current || !online)return null;
    lock.current=true;setBusy(true);setActionError('');
    try {
      const value=await api(path,{method:'POST',body,...options});
      setRevision(previous=>previous+1);
      return value;
    } catch(error) {
      setActionError(error.message);setRevision(previous=>previous+1);
      return null;
    } finally {lock.current=false;setBusy(false);}
  }

  async function create(payload){
    const created=await mutate('/cases',payload);
    if(created)setSelected(created.id);
    return created;
  }

  function focusDepartment(department){
    setFollow(false);
    setFocus(department);
  }

  function changeCamera(view){
    focusDepartment('overview');
    setCameraView(view);
    setFlat(false);
    setViewReset(previous=>previous+1);
  }

  function selectAgent(id){
    const agent=agents.find(item=>item.id===id);
    setAgentId(id);
    if(agent)focusDepartment(agent.department);
  }

  function openActivity(id){
    setHistorical('');
    selectAgent(id);
    setPanel('activity');
  }

  const selectedInvestigation=savedInvestigation;
  const brief=selectedCase?.summary??(online?'Create or select a case to begin an investigation.':'Case activity appears here when records are available.');

  return <>
    <div className="intro">
      <div className="intro-copy">
        <div className="eyebrow"><span className="eyebrow-mark"/> UAE GOVERNMENT · AI OVERSIGHT</div>
        <h1>Command centre<span>.</span></h1>
        <p>Evidence-led intelligence for public-sector AI decisions</p>
      </div>
      <div className="intro-utilities">
        <div className={`system-status ${online ? 'is-online' : 'is-offline'}`}>
          <span className="micro">API CONNECTION</span>
          <strong><i/>{online ? 'Connected' : 'Disconnected'}</strong>
        </div>
        <div className="system-status">
          <span className="micro">INVESTIGATION</span>
          <strong>{jobStatus ? pretty(jobStatus) : 'Idle'}</strong>
        </div>
        <label className="case-select">
          <span className="micro">ACTIVE CASE</span>
          <span className="case-control"><Icon name="file" size={17}/><select aria-label="Active case" value={id??''} onChange={event=>setSelected(event.target.value)} disabled={busy || !cases.length}>
            {!cases.length && <option value="">{online?'No cases yet':'No case available'}</option>}
            {cases.map(item=><option value={item.id} key={item.id}>{item.title}</option>)}
          </select><Icon name="chevron" size={16}/></span>
        </label>
      </div>
    </div>
    <div className="operations-grid">
      <section className="twin-card" aria-labelledby="twin-title">
        <div className="scene-viewport" ref={map}>
          <div className="map-canvas"><Twin focus={currentFocus} onSelect={focusDepartment} cameraView={cameraView} command={zoom} viewReset={viewReset} layers={{agents:showAgents,policy:false}} active={active} motion={motion} flat={flat} mapVisible={mapVisible} animateActivity={mapVisible && jobActive} routes={routes} handoffs={showHandoffs?handoffs:emptyList}/></div>
          <div className="scene-head"><div><div className="map-kicker"><Icon name="compass" size={15}/> OPERATIONS MAP</div><h2 id="twin-title">Civic district</h2></div><span className="sim-tag"><i/>{selectedCase?'EXERCISE':'DISTRICT VIEW'}</span></div>
          <div className="map-tools" aria-label="Map controls">
            <button title="Zoom in" aria-label="Zoom in" onClick={()=>setZoom({zoom:1})} disabled={flat}><Icon name="plus" size={18}/></button>
            <button title="Zoom out" aria-label="Zoom out" onClick={()=>setZoom({zoom:-1})} disabled={flat}><Icon name="minus" size={18}/></button>
            <button title="Campus overview" aria-label="Campus overview" onClick={()=>changeCamera('overview')} aria-pressed={currentFocus==='overview' && cameraView==='overview' && !flat}><Icon name="focus" size={18}/></button>
            <button title={flat?'Switch to 3D':'Switch to campus plan'} aria-label={flat?'Switch to 3D':'Switch to campus plan'} aria-pressed={flat} onClick={()=>setFlat(!flat)}><Icon name="layers" size={17}/></button>
          </div>
          <div className="map-caption"><span>{flat?'CAMPUS PLAN':'3D DIGITAL TWIN'}</span><span>{flat?'Select a department':'Drag to orbit · scroll to zoom'}</span></div>
        </div>
        <div className="map-footer">
          <label className="map-select">Camera
            <select value={currentFocus==='overview'?cameraView:'department'} onChange={event=>changeCamera(event.target.value)} disabled={flat}>
              {currentFocus!=='overview' && <option value="department" disabled>Department</option>}
              <option value="overview">Overview</option>
              <option value="street">Street level</option>
              <option value="plan">Overhead</option>
            </select>
          </label>
          <label className="map-select">Citizen flow
            <select value={flow} onChange={event=>setFlow(event.target.value)}>
              <option value="all">All routes</option>
              {citizenRoutes.map(route=><option key={route.id} value={route.id}>{route.label}</option>)}
              <option value="off">Hidden</option>
            </select>
          </label>
          <button aria-pressed={showAgents} onClick={()=>setShowAgents(!showAgents)}><Icon name="motion" size={15}/> Agent markers</button>
          <button aria-pressed={follow} onClick={()=>{if(follow)setFocus(currentFocus);setFollow(!follow);}}><Icon name="focus" size={15}/> Follow activity</button>
          <button aria-pressed={showHandoffs} onClick={()=>setShowHandoffs(!showHandoffs)}><Icon name="link" size={15}/> Handoffs</button>
        </div>
        <div className="map-legend" aria-label="Map legend">
          {routes.length>0 && <div><strong>Simulated citizen flow</strong>{routes.map(route=><span key={route.id}><i style={{'--route-color':route.color}}/>{route.label}</span>)}</div>}
          {showHandoffs && <div><strong><i style={{'--route-color':handoffColor}}/>Recorded agent handoffs</strong>
            <span>{lastHandoff?`${handoffs.length} · Latest: ${lastHandoff.from.name} → ${lastHandoff.to.name}`:'No handoffs recorded for this run'}</span>
          </div>}
        </div>
      </section>

      <aside className="side-panel" aria-label="Incident and departments">
        <div className="section-cap"><span className="micro">INCIDENT BRIEF</span>{selectedCase && <span className="risk">{selectedCase.priority}</span>}</div>
        <h2>{selectedCase?.title??'Case overview'}</h2><p className="brief">{brief}</p>
        <div className="metrics">
          <div><strong>{selectedCase?events.length:'—'}</strong><span>Agent checkpoints</span></div>
          <div><strong>{info?.evidence?.length??'—'}</strong><span>Evidence files</span></div>
        </div>
        <div className="section-cap dept-cap"><span className="micro">AGENT NETWORK</span></div>
        <div className="department-list network-list">
          {agents.map(agent=>{
            const event=events.findLast(item=>item.agent===agent.name);
            const selected=agent.id===agentId;
            return <button key={agent.id} type="button" className={selected?'selected':''} aria-pressed={selected} onClick={()=>openActivity(agent.id)}>
              <span className="dept-code" style={{'--pin':agent.color}}>{agent.code}</span><span className="dept-name">{agent.name}</span><span className={'agent-state state-'+(event?.status??'idle')}>{event?stageStatus(event.status):'Standby'}</span>
            </button>;
          })}
        </div>
        <div className="side-note"><Icon name="history" size={14}/><span>{latest?`${latest.agent} · ${stageStatus(latest.status)}`:'Awaiting case activity'}</span></div>
      </aside>
    </div>

    <section className="timeline" aria-labelledby="timeline-title">
      <div className="timeline-head">
        <div><div className="eyebrow small"><Icon name="history" size={15}/> INVESTIGATION WORKFLOW</div><h2 id="timeline-title">Incident timeline</h2></div>
        <div className="timeline-actions">
          {online && <NewCase create={create} disabled={busy}/>}
          <button className="button primary" disabled={!id || busy || !online || jobActive || Boolean(runs.error) || !run} onClick={()=>{setHistorical('');mutate(forCase(id)+'/investigate/async');}}><Icon name="play" size={15}/>{jobActive?'Investigation in progress':'Run investigation'}</button>
        </div>
      </div>
      {id && <div className="investigation-progress" role="group" aria-label="Investigation progress">
        <div className="investigation-progress-heading">
          <strong>Agent execution progress</strong>
          <span>{progressPercent}%</span>
        </div>
        <div className="investigation-progress-track" role="progressbar"
          aria-label="Recorded investigation checkpoints"
          aria-valuemin={0} aria-valuemax={100}
          aria-valuenow={progressPercent}>
          <div className="investigation-progress-fill"
            style={{width:`${progressPercent}%`}}/>
        </div>
        <p className="investigation-progress-caption">{progressLabel} · Checkpoint completion does not imply evidence verification or human approval.</p>
      </div>}
      <div className="steps agent-steps" aria-label="Six investigation stages">
        {agents.map((agent,index)=>{
          const event=events.findLast(item=>item.agent===agent.name);
          const phase=event?(event===latest?'current':'released'):'upcoming';
          return <button key={agent.id} type="button" className={'step step-'+phase} onClick={()=>openActivity(agent.id)}>
            <span className="step-track">{event?.status==='completed'?<Icon name="check" size={13}/>:String(index+1).padStart(2,'0')}</span>
            <span className="step-name">{agent.short}</span><small>{event?stageStatus(event.status):'Awaiting run'}</small>
          </button>;
        })}
      </div>
      <div className="timeline-note" aria-live="polite"><Icon name="motion" size={15}/><p>{currentStatus==='queued_with_history'?'New investigation queued. Showing previously recorded checkpoints.':currentStatus==='queued'?'Investigation queued.':currentStatus==='failed'||currentStatus==='interrupted'?'This investigation stopped before completion.':latest?`${latest.agent} recorded the latest checkpoint.`:'Recorded checkpoints appear as the investigation progresses.'}{Number.isFinite(runTime) && ` Total elapsed: ${runTime.toFixed(1)}s.`}</p></div>
      {(actionError || stale) && <p className="error" role="alert">{actionError||'Some case records could not be refreshed.'}</p>}
    </section>

    <section className="detail-section live-details">
      <div className="detail-nav" aria-label="Investigation tools">{checks.map(([key,icon,label])=><button key={key} aria-pressed={panel===key} onClick={()=>setPanel(key)}><Icon name={icon} size={16}/>{label}</button>)}</div>
      {panel==='activity' && <>
        <AgentBoard activeAgent={activeAgent} selected={agentId} onSelect={selectAgent} events={events} records={info} historical={historical} setHistorical={setHistorical} inProgress={jobActive} available={Boolean(id && online)} busy={busy || jobActive} deskAvailable={Boolean(id && deskAvailable)}
          onAsk={agent=>{setAskAgent(agent);setPanel('assistant');}} onRun={agent=>mutate(forCase(id)+(agent==='triage'?'/triage':'/evidence/analyze'))} onEvidence={()=>setPanel('evidence')} onScenario={()=>setPanel('scenario')}/>
        {agentId==='synthesis' && <div className="detail-body advisory-panel"><AdvisoryReview key={selectedInvestigation?.id??id} id={id} investigation={selectedInvestigation} reviews={info?.reviews??emptyList} busy={busy || jobActive} connected={online} reviewAvailable={reviewAvailable && selectedInvestigation?.id===info?.investigations?.[0]?.id}/></div>}
      </>}
      {panel==='evaluation' && <Evaluation records={info} run={run}/>}
      {!id && !['activity','evaluation'].includes(panel) && <div className="detail-body"><h2>{checks.find(item=>item[0]===panel)?.[2]}</h2><p className="detail-copy">Select an available case to use this workspace.</p></div>}
      {id && panel==='scenario' && <ScenarioLab key={id} id={id} sessions={info?.sessions??emptyList} mutate={mutate} busy={busy} connected={online}/>}
      {id && panel==='evidence' && <EvidenceWorkbench key={id} id={id} records={info} mutate={mutate} busy={busy || jobActive} connected={online} reviewAvailable={reviewAvailable} renderData={value=><DataValue value={value}/>}/>}
      {id && panel==='standards' && <StandardsPanel key={id} id={id} connected={online} reviewAvailable={reviewAvailable}/>}
       {id && panel==='assistant' && <EvidenceDesk key={id+askAgent} id={id} initialAgent={askAgent} configured={deskAvailable} connected={online}/>}
      {id && panel==='audit' && <div className="detail-body">
        <div className="detail-heading"><div><div className="eyebrow small">CASE RECORDS</div><h2>Audit evidence</h2></div><button className="button secondary" disabled={!info} onClick={()=>setAuditNotice(exportCase(id,run,info)?'Exported a verified SHA-256 snapshot.':'Could not verify export integrity.')}><Icon name="download" size={16}/> Export evidence</button></div>
        <p className="detail-copy">Investigation events, source decisions and human reviews. Exports include a SHA-256 integrity chain.</p>
        {auditNotice && <p className="verify-status" role="status">{auditNotice}</p>}
        <div className="audit-list">{info?.audit.map(entry=><details className="audit-item" key={entry.id}><summary><span className="ref static">LOG</span><strong>{entry.action}</strong><span/><time>{time(entry.created_at)} GST</time><Icon name="chevron" size={15}/></summary><div className="audit-content">{entry.detail}</div></details>)}</div>
      </div>}
    </section>
    <footer className="footer"><div><img src="/mark.svg" width="21" height="21" alt=""/><strong>HR-PRESENTS</strong><span>Advisory exercise</span></div></footer>
  </>;
}
