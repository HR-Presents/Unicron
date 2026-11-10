import React,{useState,useEffect,useRef} from 'react';
import ReactMarkdown from 'react-markdown';
import {createRoot} from 'react-dom/client';
import {api,forCase,runSnapshot} from './live-api.mjs';
import {DataValue} from './ResponseData.jsx';
import './workspace.css';
import {agentNames as names} from '../product.mjs';
import AgentActivity from './AgentActivity.jsx';
const prompts=[['Government policy','How can the UAE responsibly introduce AI into public services?'],['Healthcare','Assess the risks of AI-assisted patient triage in UAE hospitals.'],['AI governance','Compare AI governance approaches in the UAE and European Union.'],['Regulatory intelligence','Which data protection obligations apply to a cross-border AI service?']];
function Mark({size=32}){return <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true"><path fill="currentColor" d="M6 6h9v25l9 7 9-7V6h9v29L24 48 6 35V6Z"/><path fill="currentColor" d="M20 6h8v25l-4 3-4-3V6Z"/></svg>}
function Glyph({name}){return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{name==='plus'?<path d="M12 5v14M5 12h14"/>:name==='search'?<><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></>:name==='arrow'?<path d="M12 19V5m-5 5 5-5 5 5"/>:name==='panel'?<><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/></>:name==='settings'?<><circle cx="12" cy="12" r="3"/><path d="m9 3-1 3-3 1-2 5 2 5 3 1 1 3h6l1-3 3-1 2-5-2-5-3-1-1-3Z"/></>:<path d="m9 5 7 7-7 7"/>}</svg>}
function Markdown({text=''}){return <div className="markdown"><ReactMarkdown components={{a:({children,href})=><a href={href} target="_blank" rel="noopener noreferrer">{children}</a>}}>{text}</ReactMarkdown></div>}
function saved(){try{return JSON.parse(localStorage.getItem('unicron-conversations')||'{}')}catch{return {}}}
function App(){
 const [theme,setTheme]=useState(()=>localStorage.getItem('unicron-theme')||'black'),[side,setSide]=useState(false),[settings,setSettings]=useState(false),[search,setSearch]=useState(false),[query,setQuery]=useState(''),[cases,setCases]=useState([]),[id,setId]=useState(''),[draft,setDraft]=useState(''),[threads,setThreads]=useState(saved),[connection,setConnection]=useState(null),[snapshot,setSnapshot]=useState(null),[runs,setRuns]=useState([]),[sources,setSources]=useState([]),[pending,setPending]=useState(false),[error,setError]=useState('');
 const lock=useRef(false),bottom=useRef(null),input=useRef(null),generation=useRef(0);const current=cases.find(c=>c.id===id),messages=threads[id]||[],active=['queued','running'].includes(snapshot?.job?.status);
 useEffect(()=>{const handler=e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();setSearch(true)}if(e.key==='Escape'){setSettings(false);setSearch(false);setSide(false)}};window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler)},[]);
 useEffect(()=>{document.documentElement.dataset.theme=theme;localStorage.setItem('unicron-theme',theme)},[theme]);
 useEffect(()=>{localStorage.setItem('unicron-conversations',JSON.stringify(threads))},[threads]);
 useEffect(()=>{let live=true,timer;async function poll(){try{const c=await api('/connection');if(!live)return;setConnection(c);if(c.state==='connected'){const list=await api('/cases');if(live)setCases(list)}}catch{if(live)setConnection({state:'unavailable'})}if(live)timer=setTimeout(poll,15000)}poll();return()=>{live=false;clearTimeout(timer)}},[]);
 useEffect(()=>{setSnapshot(null);setRuns([]);setSources([]);setError('');if(!id)return;let live=true,timer;const controller=new AbortController();async function poll(){try{const [s,r,src]=await Promise.all([runSnapshot(id,controller.signal),api(forCase(id)+'/investigations',{signal:controller.signal}),api(forCase(id)+'/sources',{signal:controller.signal})]);if(live){setSnapshot(s);setRuns(r);setSources(src)}}catch(e){if(live)setError(e.message)}if(live)timer=setTimeout(poll,3000)}poll();return()=>{live=false;controller.abort();clearTimeout(timer)}},[id]);
 useEffect(()=>{bottom.current?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'})},[messages.length,pending,runs.length]);
 const online=connection?.state==='connected';
 function select(value){if(!value)setThreads(t=>({...t,['']:[]}));generation.current++;setId(value);setSide(false);setSearch(false);setDraft('');setError('')}
 function append(key,message){setThreads(t=>({...t,[key]:[...(t[key]||[]),message]}))}
 async function submit(e){
  e?.preventDefault();
  const question=draft.trim();
  if(lock.current||active||!question)return;
  if(!online){setError('The intelligence backend is not connected. Your question is kept here; try again when the connection is restored.');return}
  lock.current=true;setPending(true);setError('');
  let caseId=id;const gen=generation.current;
  const context=messages.filter(m=>['user','assistant'].includes(m.role)).slice(-6).map(m=>({role:m.role,content:m.text.slice(0,600)}));
  try{
   if(!caseId){
    const routing=await api('/chat/route',{method:'POST',body:{question:question.slice(0,4000)}});
    if(routing.route==='chat'){
     append('',{role:'user',text:question});setDraft('');
     const reply=await api('/chat',{method:'POST',body:{question:question.slice(0,4000),context}});
     append('',{role:'assistant',text:reply.answer,uncertainty:reply.uncertainty});
     return;
    }
    if(routing.route!=='investigate')throw Error('The request could not be routed. Please try again.');
    const c=await api('/cases',{method:'POST',body:{title:question.slice(0,180),summary:question,domain:'Policy intelligence',priority:'Medium'}});
    caseId=c.id;setCases(list=>[c,...list]);
    if(gen===generation.current)setId(caseId);
    setThreads(t=>({...t,[caseId]:[...(t['']||[]),{role:'user',text:question}],['']:[]}));setDraft('');
    await api(forCase(caseId)+'/investigate/async',{method:'POST'});
    append(caseId,{role:'system',text:'Investigation started. Findings will appear as the agents record their outputs.'});
   }else{
    append(caseId,{role:'user',text:question});setDraft('');
    const reply=await api(forCase(caseId)+'/desk',{method:'POST',body:{question,mode:'synthesis',context}});
    append(caseId,{role:'assistant',text:reply.answer,citations:reply.citations,uncertainty:reply.uncertainty});
   }
  }catch(e){if(gen===generation.current)setError(e.message)}
  finally{lock.current=false;setPending(false)}
 }
 const hasConversation=Boolean(id||messages.length);

 const latest=runs.find(run=>run.id===snapshot?.execution?.id),synthesis=latest?.stages?.find(s=>s.agent==='Review & Synthesis'),events=snapshot?.events||[];
 return <div className={'workspace '+(side?'sidebar-open':'')}>
 <aside className="sidebar"><a href="#" className="brand" onClick={e=>{e.preventDefault();select('')}}><Mark size={27}/><span>UNICRON</span></a><button className="new" onClick={()=>select('')}><Glyph name="plus"/>New investigation<span>↗</span></button><button className="navitem" onClick={()=>setSearch(true)}><Glyph name="search"/>Search investigations<kbd>⌘ K</kbd></button><div className="recent-label">YOUR WORKSPACE</div><div className="recents">{cases.length?cases.map(c=><button key={c.id} className={id===c.id?'selected':''} onClick={()=>select(c.id)} title={c.title}><span className="tiny-dot"/>{c.title}</button>):<p className="empty-history">Your investigations will appear here.</p>}</div><div className="sidebar-bottom"><button className="navitem" onClick={()=>setSettings(true)}><Glyph name="settings"/>Settings</button><div className="connection"><span className={'dot '+(online?'online':'')}/>{online?'Intelligence connected':connection?'Backend disconnected':'Checking connection'}<span className="status-code">{online?'LIVE':'OFFLINE'}</span></div><div className="profile"><div className="avatar">U</div><div>UNICRON Workspace<small>Intelligence, without boundaries.</small></div></div></div></aside>
 {side&&<button className="scrim" aria-label="Close sidebar" onClick={()=>setSide(false)}/>}
 <main><header className="header"><div><button className="panel-toggle" aria-label="Toggle sidebar" onClick={()=>setSide(!side)}><Glyph name="panel"/></button><span className="crumb">Workspace</span><span className="slash">/</span><span>{current?current.title:'New investigation'}</span></div><span className="header-tag"><span className="dot"/>AUTONOMOUS INTELLIGENCE</span></header>
 <AgentActivity names={names} events={events} latest={latest} snapshot={snapshot} active={active} online={online} caseId={id}/>
 <div className={'conversation '+(!hasConversation?'welcome':'')}>
 {!hasConversation?<section className="intro"><div className="intro-mark"><Mark size={54}/></div><div className="eyebrow">CLARITY THROUGH INTELLIGENCE</div><h1>Intelligence begins<br/>with a question.</h1><p>Complex questions. Connected evidence. Clear direction.<br/>Your autonomous intelligence workspace.</p></section>:<section className="thread">{id&&<div className="case-heading"><span className="eyebrow">INVESTIGATION</span><h1>{current?.title||'Investigation'}</h1></div>}{!messages.length&&current&&<div className="user-message">{current.summary}</div>}{messages.map((m,i)=><article key={i} className={m.role==='user'?'user-message':'assistant-message'}>{m.role==='assistant'&&<div className="assistant-label"><Mark size={19}/>UNICRON</div>}<Markdown text={m.text}/>{m.uncertainty&&<p className="uncertainty">{m.uncertainty}</p>}{m.citations?.length>0&&<details className="sources"><summary>{m.citations.length} evidence references</summary>{m.citations.map((c,j)=><details key={j}><summary>[{j+1}] {c.title}</summary><p>{c.text}</p><small>{c.id} · {c.verification}</small></details>)}</details>}</article>)}

 {synthesis?.result&&<article className="assistant-message"><div className="assistant-label"><Mark size={19}/>UNICRON <small>Final synthesis</small></div><DataValue value={synthesis.result}/>{sources.length>0&&<details className="sources"><summary>Source provenance · {sources.length} records</summary>{sources.map((s,i)=><details key={s.id||i}><summary>{s.title||s.filename||s.document_id}</summary><DataValue value={s}/></details>)}</details>}</article>}{!synthesis&&(active?events.map(e=>e.stage).filter(Boolean):latest?.stages)?.filter(s=>s.result).map((s,i)=><details className="stage-result" key={i}><summary>{s.agent} · {s.status}</summary><DataValue value={s.result}/></details>)}{pending&&<p className="working" role="status"><Mark size={18}/>Request in progress<span className="pulse"> ···</span></p>}<div ref={bottom}/></section>}
 <div className="composer-wrap"><form className="composer" onSubmit={submit}><label className="sr-only" htmlFor="question">Your investigation question</label><textarea id="question" ref={input} value={draft} maxLength={id?400:4000} rows={2} placeholder={id?'Ask a follow-up question…':'Describe a case, ask a question, or explore a policy…'} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();submit()}}}/><div className="composer-bottom"><span><Mark size={14}/> {id?'Evidence-grounded follow-up':'Autonomous investigation'}<span className="composer-divider">/</span><span className="agent-count">6 specialized agents</span></span><button className="send" aria-label="Send question" disabled={!draft.trim()||pending||active}><Glyph name="arrow"/></button></div></form>{error&&<p className="error" role="alert">{error}</p>}<div className="composer-note">Evidence-grounded by design. Verify critical findings against the cited sources.</div></div>
 {!hasConversation&&<section className="suggestions"><div className="suggestions-label">A STARTING POINT</div><div className="prompt-grid">{prompts.map(([label,text],i)=><button key={label} onClick={()=>{setDraft(text);input.current?.focus()}}><span className="prompt-number">0{i+1}</span><span><strong>{label}</strong><small>{text}</small></span><span className="prompt-arrow">↗</span></button>)}</div></section>}
 </div><footer><span>UNICRON</span><p>Unified Network for Intelligence, Compliance, Research, Oversight and Navigation</p><span>BUILT FOR CLARITY</span></footer></main>
 {(settings||search)&&<div className="modal-backdrop" onClick={()=>{setSettings(false);setSearch(false)}}><section className="modal" role="dialog" aria-modal="true" aria-label={settings?'Settings':'Search investigations'} onClick={e=>e.stopPropagation()} onKeyDown={e=>{if(e.key==='Escape'){setSettings(false);setSearch(false)}if(e.key==='Tab'){const nodes=e.currentTarget.querySelectorAll('button,input,select');const first=nodes[0],last=nodes[nodes.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}}}><button className="close" aria-label="Close dialog" onClick={()=>{setSettings(false);setSearch(false)}} autoFocus>×</button>{settings?<><span className="eyebrow">PREFERENCES</span><h2>Your workspace.</h2><label className="theme-setting">Appearance<select value={theme} onChange={e=>setTheme(e.target.value)}><option value="black">Matte black</option><option value="light">Porcelain</option></select></label><p className="settings-description">An autonomous AI intelligence system for evidence-grounded investigation, regulatory analysis, and cross-jurisdictional policy intelligence.</p><div className="settings-status">Connection: {online?'Connected':'Unavailable'}</div></>:<><h2>Find an investigation.</h2><input placeholder="Search by title…" aria-label="Search by title" value={query} onChange={e=>setQuery(e.target.value)}/><div className="search-results">{cases.filter(c=>c.title.toLowerCase().includes(query.toLowerCase())).map(c=><button key={c.id} onClick={()=>select(c.id)}>{c.title}<span>↗</span></button>)}{!cases.filter(c=>c.title.toLowerCase().includes(query.toLowerCase())).length&&<p>No matching investigations.</p>}</div></>}</section></div>}
 </div>
}
createRoot(document.getElementById('root')).render(<App/>);
