import React,{useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import ReactMarkdown from 'react-markdown';
import {api,forCase,runSnapshot} from './live-api.mjs';
import {agentNames as names,product} from '../product.mjs';
import AgentActivity,{agentModes,recordedStages} from './AgentActivity.jsx';
import ReportResponse,{SourceReferences} from './ReportResponse.jsx';
import './workspace.css';

const examples=[
  ['Healthcare','Assess the safeguards for AI-assisted patient triage in a UAE public hospital.'],
  ['AI governance','Identify policy gaps for an AI public-service assistant, using relevant global examples.'],
  ['Public services','Investigate risks and responsibilities when an automated government service gives conflicting guidance.'],
  ['Regulatory intelligence','What evidence is needed to assess a cross-border AI service that processes personal data?'],
];
function readStored(key,fallback){try{const raw=localStorage.getItem(key);if(key==='unicron-theme'&&['black','light'].includes(raw))return raw;return JSON.parse(raw)??fallback}catch{return fallback}}
function Mark({size=28}){return <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true"><path fill="currentColor" d="M6 6h9v25l9 7 9-7V6h9v29L24 48 6 35V6Z"/><path fill="currentColor" d="M20 6h8v25l-4 3-4-3V6Z"/></svg>}
function Icon({name}){return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{name==='plus'?<path d="M12 5v14M5 12h14"/>:name==='search'?<><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></>:name==='send'?<path d="M12 19V5m-5 5 5-5 5 5"/>:name==='trash'?<><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/></>:name==='panel'?<><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/></>:name==='settings'?<><circle cx="12" cy="12" r="3"/><path d="m9 3-1 3-3 1-2 5 2 5 3 1 1 3h6l1-3 3-1 2-5-2-5-3-1-1-3Z"/></>:<path d="M7 17 17 7M7 7h10v10"/>}</svg>}
function Markdown({text=''}){return <div className="markdown"><ReactMarkdown components={{a:({children,href})=><a href={href} target="_blank" rel="noopener noreferrer">{children}</a>}}>{text}</ReactMarkdown></div>}
function Message({message}){
  const assistant=message.role!=='user';
  return <article className={assistant?'assistant-message':'user-message'}>{assistant&&<div className="assistant-label"><Mark size={19}/><span>{message.agent||'UNICRON'}</span>{message.agent&&<small>Agent response</small>}</div>}<Markdown text={message.text}/>{message.uncertainty&&<p className="uncertainty">{message.uncertainty}</p>}{message.citations?.length>0&&<SourceReferences citations={message.citations.map(item=>item.id||item.citation)} sources={message.citations}/>}</article>;
}
function InvestigationAnswer({stages,active,snapshot}){
  const final=stages['Review & Synthesis'];
  const recorded=names.filter(name=>stages[name]?.result);
  if(!recorded.length&&!active)return null;
  return <section className="investigation-answer" aria-label="Investigation response">
    {active&&<p className="investigation-status" role="status"><span className="activity-dot"/>{snapshot?.job?.status==='queued'?'Queued for investigation':snapshot?.execution?.last_agent?`${snapshot.execution.last_agent} is working on this case`:'Waiting for a worker to record the first stage'}</p>}
    {final?.result&&<article className="assistant-message final-response"><div className="assistant-label"><Mark size={20}/><span>UNICRON</span><small>Investigation findings</small></div><ReportResponse result={final.result}/></article>}
    {recorded.length>0&&<details className="agent-contributions" open={!final?.result||undefined}><summary><span>Agent responses</span><small>{recorded.length} recorded</small><span aria-hidden="true">⌄</span></summary><div>{recorded.map(name=><details className="contribution" key={name}><summary><span>{name}</span><small>{stages[name].status==='completed'?'Completed':stages[name].status==='source_required'?'Sources missing':stages[name].status}</small></summary><ReportResponse result={stages[name].result} agent={name}/></details>)}</div></details>}
  </section>;
}
function Conversation({messages,current,stages,active,snapshot}){
  const initial=messages.findIndex(message=>message.role==='user'&&message.text===current?.summary);
  if(!current)return <>{messages.filter(message=>message.role!=='system').map((message,index)=><Message message={message} key={index}/>)}</>;
  const before=initial>=0?messages.slice(0,initial+1):[{role:'user',text:current.summary}];
  const after=initial>=0?messages.slice(initial+1):messages;
  return <><div className="case-meta"><span>Investigation</span><span>{current.id}</span></div>{before.filter(message=>message.role!=='system').map((message,index)=><Message message={message} key={'before'+index}/>)}<InvestigationAnswer stages={stages} active={active} snapshot={snapshot}/>{after.filter(message=>message.role!=='system').map((message,index)=><Message message={message} key={'after'+index}/>)}</>;
}

function App(){
  const [theme,setTheme]=useState(()=>readStored('unicron-theme','black'));
  const [sidebarOpen,setSidebarOpen]=useState(()=>window.matchMedia('(min-width:920px)').matches);
  const [agentsOpen,setAgentsOpen]=useState(false);
  const [selectedAgent,setSelectedAgent]=useState(null);
  const [compactComposer,setCompactComposer]=useState(false);
  const [modal,setModal]=useState(null),[query,setQuery]=useState('');
  const [deleteTarget,setDeleteTarget]=useState(null),[deleting,setDeleting]=useState(false);
  const deletedCases=useRef(new Set());
  const [cases,setCases]=useState([]),[id,setId]=useState(''),[draft,setDraft]=useState('');
  const [threads,setThreads]=useState(()=>readStored('unicron-conversations',{}));
  const [connection,setConnection]=useState(null),[snapshot,setSnapshot]=useState(null),[runs,setRuns]=useState([]);
  const [pending,setPending]=useState(false),[error,setError]=useState(''),[persistenceError,setPersistenceError]=useState('');
  const lock=useRef(false),generation=useRef(0),bottom=useRef(null),input=useRef(null),chatScroll=useRef(null);
  const current=cases.find(item=>item.id===id);
  const messages=threads[id]||[];
  const online=connection?.state==='connected';
  const active=['queued','running'].includes(snapshot?.job?.status);
  const latest=runs.find(run=>run.id===snapshot?.execution?.id);
  const events=snapshot?.events||[];
  const stages=recordedStages(events,latest);
  const canAsk=!active||Boolean(selectedAgent&&stages[selectedAgent]?.status==='completed');
  const hasConversation=Boolean(id||messages.length);

  useEffect(()=>{
    const handler=event=>{
      if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();setModal('search')}
      if(event.key==='Escape'){if(!deleting)setModal(null);if(!window.matchMedia('(min-width:920px)').matches)setSidebarOpen(false);if(!window.matchMedia('(min-width:1200px)').matches)setAgentsOpen(false)}
    };
    window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);
  },[deleting]);
  useEffect(()=>{document.documentElement.dataset.theme=theme;try{localStorage.setItem('unicron-theme',JSON.stringify(theme))}catch{}},[theme]);
  useEffect(()=>{try{localStorage.setItem('unicron-conversations',JSON.stringify(threads));setPersistenceError('')}catch{setPersistenceError('This browser could not save the conversation locally. Investigation results remain saved by the backend.')}},[threads]);
  useEffect(()=>{
    let live=true,timer;const controller=new AbortController();
    async function poll(){
      try{const value=await api('/connection',{signal:controller.signal});if(!live)return;setConnection(value);if(value.state==='connected'){const list=await api('/cases',{signal:controller.signal});if(live)setCases(list.filter(item=>!deletedCases.current.has(item.id)))}}
      catch{if(live)setConnection({state:'unavailable'})}
      if(live)timer=setTimeout(poll,15000);
    }
    poll();return()=>{live=false;controller.abort();clearTimeout(timer)};
  },[]);
  useEffect(()=>{
    setSnapshot(null);setRuns([]);setError('');setSelectedAgent(null);
    if(!id)return;
    let live=true,timer;const controller=new AbortController();
    async function poll(){
      try{const [state,history]=await Promise.all([runSnapshot(id,controller.signal),api(forCase(id)+'/investigations',{signal:controller.signal})]);if(live){setSnapshot(state);setRuns(history)}}
      catch(failure){if(live)setError(failure.message)}
      if(live)timer=setTimeout(poll,3000);
    }
    poll();return()=>{live=false;controller.abort();clearTimeout(timer)};
  },[id]);
  useEffect(()=>{bottom.current?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'end'})},[messages.length,pending,runs.length]);

  useEffect(()=>{
    const viewport=chatScroll.current;
    if(!viewport)return;
    const update=()=>setCompactComposer(previous=>hasConversation&&viewport.scrollHeight-viewport.clientHeight>(previous?4:128));
    const observer=new ResizeObserver(update);
    observer.observe(viewport);
    for(const child of viewport.children)observer.observe(child);
    const frame=requestAnimationFrame(update);
    return()=>{observer.disconnect();cancelAnimationFrame(frame)};
  },[hasConversation,agentsOpen]);

  function select(value){generation.current++;if(!value)setThreads(previous=>({...previous,['']:[]}));setId(value);if(!window.matchMedia('(min-width:920px)').matches)setSidebarOpen(false);setModal(null);setDraft('');setError('')}
  function append(key,message){setThreads(previous=>({...previous,[key]:[...(previous[key]||[]),message]}))}
  async function submit(event){
    event?.preventDefault();const question=draft.trim();
    if(lock.current||!canAsk||!question)return;
    if(!online){setError('The intelligence backend is not connected. Your question is kept here until the connection is restored.');return}
    lock.current=true;setPending(true);setError('');const gen=generation.current;let caseId=id;
    const context=messages.filter(message=>['user','assistant'].includes(message.role)).slice(-6).map(message=>({role:message.role,content:message.text.slice(0,600)}));
    const replyAgent=selectedAgent;
    try{
      if(!caseId){
        const routing=await api('/chat/route',{method:'POST',body:{question}});
        if(routing.route==='chat'){
          append('',{role:'user',text:question});if(gen===generation.current)setDraft('');
          const reply=await api('/chat',{method:'POST',body:{question,context}});
          append('',{role:'assistant',text:reply.answer,uncertainty:reply.uncertainty});return;
        }
        if(routing.route!=='investigate')throw Error('The request could not be routed. Please try again.');
        const item=await api('/cases',{method:'POST',body:{title:question.slice(0,180),summary:question,domain:'Policy intelligence',priority:'Medium'}});
        caseId=item.id;setCases(list=>[item,...list]);if(gen===generation.current){setId(caseId);setDraft('')}
        setThreads(previous=>({...previous,[caseId]:[...(previous['']||[]),{role:'user',text:question}],['']:[]}));
        await api(forCase(caseId)+'/investigate/async',{method:'POST'});
      }else{
        append(caseId,{role:'user',text:question});if(gen===generation.current)setDraft('');
        const reply=await api(forCase(caseId)+'/desk',{method:'POST',body:{question,mode:agentModes[replyAgent]||'synthesis',context}});
        append(caseId,{role:'assistant',text:reply.answer,citations:reply.citations,uncertainty:reply.uncertainty,agent:reply.answer_origin==='product_configuration'?null:replyAgent});
      }
    }catch(failure){if(gen===generation.current)setError(failure.message)}
    finally{lock.current=false;setPending(false)}
  }
  async function retryInvestigation(){
    if(!id||lock.current||active||!online)return;
    lock.current=true;setPending(true);setError('');
    try{await api(forCase(id)+'/investigate/async',{method:'POST'});setSnapshot(await runSnapshot(id))}
    catch(failure){setError(failure.message)}
    finally{lock.current=false;setPending(false)}
  }
  function requestDelete(target){setDeleteTarget(target);setModal('delete');setError('')}
  async function deleteConversation(){
    if(!deleteTarget||deleting||lock.current)return;
    const target=deleteTarget;setDeleting(true);setError('');
    try{
      if(target.id){await api(forCase(target.id),{method:'DELETE'});deletedCases.current.add(target.id);setCases(list=>list.filter(item=>item.id!==target.id))}
      setThreads(previous=>{const next={...previous};delete next[target.id];return next});
      if(target.id===id){generation.current++;setId('');setSnapshot(null);setRuns([]);setDraft('');setSelectedAgent(null)}
      setDeleteTarget(null);setModal(null);
    }catch(failure){setError(failure.message)}
    finally{setDeleting(false)}
  }
  function trapDialog(event){
    if(event.key!=='Tab')return;
    const nodes=event.currentTarget.querySelectorAll('button,input,select');const first=nodes[0],last=nodes[nodes.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
  }
  const filteredCases=cases.filter(item=>item.title.toLowerCase().includes(query.toLowerCase()));

  return <div className={'workspace '+(sidebarOpen?'navigation-open ':'')+(agentsOpen?'agents-open':'')}>
    <aside className="sidebar" aria-label="Workspace navigation">
      <button className="sidebar-collapse icon-button" aria-label="Collapse navigation" onClick={()=>setSidebarOpen(false)}><Icon name="panel"/></button><a className="brand" href="#" onClick={event=>{event.preventDefault();select('')}}><Mark/><span>UNICRON<small>Intelligence workspace</small></span></a>
      <button className="new-investigation" onClick={()=>select('')} disabled={pending}><Icon name="plus"/><span>New investigation</span></button>
      <button className="search-investigations" onClick={()=>setModal('search')}><Icon name="search"/><span>Search investigations</span><kbd>⌘ K</kbd></button>
      <div className="recent-heading">Recent investigations <span>{cases.length||''}</span></div>
      <nav className="recent-list" aria-label="Recent investigations">{cases.length?cases.map(item=><div key={item.id} className={'history-row '+(item.id===id?'selected':'')}><button className="history-title" onClick={()=>select(item.id)} title={item.title}><span>{item.title}</span></button><button className="history-delete" aria-label={'Delete investigation: '+item.title} title="Delete investigation" disabled={pending||deleting} onClick={()=>requestDelete({id:item.id,title:item.title})}><Icon name="trash"/></button></div>):<p className="history-empty">Your investigations will appear here when you begin a case.</p>}</nav>
      <div className="sidebar-footer"><button className="settings-button" onClick={()=>setModal('settings')}><Icon name="settings"/><span>Settings</span></button><div className="connection"><span className={'connection-dot '+(online?'connected':'')}/><span>{online?'Backend connected':connection?'Backend unavailable':'Checking connection'}</span></div><div className="ownership">Developed by <strong>HR-Presents</strong></div></div>
    </aside>
    {sidebarOpen&&<button className="navigation-scrim" aria-label="Close navigation" onClick={()=>setSidebarOpen(false)}/>}
    <main className="main">
      <header className="workspace-header"><div className="workspace-location"><button className="icon-button navigation-toggle" aria-label={sidebarOpen?'Collapse workspace navigation':'Open workspace navigation'} onClick={()=>setSidebarOpen(!sidebarOpen)}><Icon name="panel"/></button><span className="location-label">Workspace</span><span className="location-divider">/</span><span className="current-title">{current?.title||'New conversation'}</span></div><div className="header-actions"><button className="delete-chat-button" disabled={!hasConversation||pending||deleting} onClick={()=>requestDelete({id,title:current?.title||'this chat'})} aria-label="Delete chat" title="Delete chat"><Icon name="trash"/><span>Delete chat</span></button><button className={'agents-toggle '+(agentsOpen?'selected':'')} aria-expanded={agentsOpen} onClick={()=>{setAgentsOpen(!agentsOpen);if(!agentsOpen)chatScroll.current?.scrollTo({top:0,behavior:'instant'})}}><Icon name="panel"/>Agents <span>6</span></button></div></header>
      <div className="chat-scroll" ref={chatScroll}><AgentActivity names={names} events={events} latest={latest} snapshot={snapshot} active={active} online={online} caseId={id} open={agentsOpen} selected={selectedAgent} onSelect={setSelectedAgent} onClose={()=>setAgentsOpen(false)}/><div className={'conversation '+(!hasConversation&&!agentsOpen?'welcome':'')}>
        {!hasConversation&&!agentsOpen?<section className="intro"><div className="intro-mark"><Mark size={48}/></div><p className="eyebrow">AUTONOMOUS INTELLIGENCE</p><h1>Intelligence begins with a question.</h1><p className="intro-description">Ask a question or describe a case. Get clear answers, grounded in evidence.</p><div className="examples">{examples.map(([label,prompt])=><button key={label} onClick={()=>{setDraft(prompt);input.current?.focus()}}><span>{label}</span><Icon name="arrow"/></button>)}</div></section>:hasConversation?<Conversation messages={messages} current={current} stages={stages} active={active} snapshot={snapshot}/>:null}
        {pending&&<p className="working-message" role="status"><Mark size={17}/>{selectedAgent?`${selectedAgent} is preparing a response`:'Preparing a response'}<span className="thinking-dots" aria-hidden="true">···</span></p>}
        {id&&!active&&(snapshot?.job?.status==='failed'||(error&&!snapshot?.job))&&<div className="investigation-recovery"><p>This investigation has no active job. Recorded responses remain available.</p><button onClick={retryInvestigation} disabled={pending||!online}>Retry investigation</button></div>}
        <div ref={bottom}/>
      </div></div>
      <div className={'composer-region '+(compactComposer?'is-compact':'')}><div className="composer-width">{id&&selectedAgent&&<div className="replying-to">Asking {selectedAgent}<button onClick={()=>setSelectedAgent(null)} aria-label="Return to UNICRON synthesis">×</button></div>}<form className="composer" onSubmit={submit}><label className="sr-only" htmlFor="question">Your message to UNICRON</label><textarea ref={input} id="question" rows={compactComposer?1:2} value={draft} maxLength={id?400:4000} placeholder={selectedAgent&&id?`Ask ${selectedAgent}…`:id?'Ask a follow-up about this investigation…':'Ask UNICRON or describe a case…'} onChange={event=>setDraft(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();submit()}}}/><div className="composer-bottom"><span><Mark size={14}/>{active&&!canAsk?'Investigation running':id?'Evidence-grounded conversation':'Autonomous investigation'}</span><button className="send-button" aria-label="Send message" disabled={!draft.trim()||pending||!canAsk}><Icon name="send"/></button></div></form>{(error||persistenceError)&&<p className="error" role="alert">{error||persistenceError}</p>}<p className="composer-note">Findings are tied to available evidence. Open source references to inspect the supporting passages.</p></div></div>
    </main>
    {modal&&<div className="modal-backdrop" onClick={()=>{if(!deleting)setModal(null)}}><section className="modal" role="dialog" aria-modal="true" aria-label={modal==='delete'?'Delete conversation':modal==='search'?'Search investigations':'Settings'} onClick={event=>event.stopPropagation()} onKeyDown={trapDialog}><button className="modal-close" aria-label="Close dialog" onClick={()=>setModal(null)} disabled={deleting} autoFocus>×</button>{modal==='delete'?<><h2>Delete this conversation?</h2><p className="delete-description">{deleteTarget?.id?<>This permanently deletes <strong>{deleteTarget.title}</strong> and its case-owned investigation records. The shared evidence archive is preserved.</>:<>This clears the messages saved in this browser.</>}</p><p className="delete-description">This cannot be undone. Running investigations must finish before deletion.</p>{error&&<p className="error" role="alert">{error}</p>}<div className="dialog-actions"><button disabled={deleting} onClick={()=>setModal(null)}>Cancel</button><button className="confirm-delete" disabled={deleting||pending} onClick={deleteConversation}>{deleting?'Deleting…':'Delete conversation'}</button></div></>:modal==='search'?<><h2>Find an investigation</h2><input aria-label="Search by title" placeholder="Search your investigations…" value={query} onChange={event=>setQuery(event.target.value)}/><div className="search-results">{filteredCases.map(item=><button key={item.id} onClick={()=>select(item.id)}>{item.title}<Icon name="arrow"/></button>)}{!filteredCases.length&&<p>No matching investigations.</p>}</div></>:<><p className="eyebrow">WORKSPACE PREFERENCES</p><h2>Make it yours.</h2><label className="appearance-setting">Appearance<select value={theme} onChange={event=>setTheme(event.target.value)}><option value="black">Matte black</option><option value="light">Porcelain</option></select></label><div className="about-unicron"><strong>{product.name}</strong><p>{product.expansion}</p><p>{product.purpose}.</p><small>Developed and owned by HR-Presents.</small></div></>}</section></div>}
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
