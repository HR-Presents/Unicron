import React,{useState} from 'react';
import {api} from './live-api.mjs';
import {readableResponse,responseCitations} from './report-model.mjs';

export function SourceReferences({citations=[],sources=[]}){
  const refs=[...new Set(citations.filter(value=>typeof value==='string'))];
  const [open,setOpen]=useState(false),[records,setRecords]=useState({}),[loading,setLoading]=useState(false);
  if(!refs.length)return null;
  async function expand(){
    const next=!open;setOpen(next);
    if(!next||loading)return;
    setLoading(true);
    const values=await Promise.all(refs.map(async ref=>{
      if(records[ref])return [ref,records[ref]];
      const inline=sources.find(item=>(item.id||item.citation)===ref);
      if(inline)return [ref,{title:inline.title||inline.document_title,text:inline.text||inline.excerpt,verification_status:inline.verification||inline.verification_status,official_url:inline.url||inline.official_url}];
      const match=/^([A-Za-z0-9-]{1,80})#p([0-9]+)$/.exec(ref);
      if(!match)return [ref,{error:'This reference cannot be resolved to a documentary passage.'}];
      try{return [ref,await api(`/evidence/verified/passages/${match[1]}/${match[2]}`)]}
      catch{return [ref,{error:'The verified passage is not currently available. Its citation has been retained.'}]}
    }));
    setRecords(previous=>({...previous,...Object.fromEntries(values)}));setLoading(false);
  }
  return <div className="references"><button type="button" className="references-toggle" aria-expanded={open} onClick={expand}>{refs.length} source {refs.length===1?'reference':'references'} <span aria-hidden="true">{open?'−':'+'}</span></button>{open&&<div className="reference-list">{loading&&<p role="status">Loading source passages…</p>}{refs.map((ref,index)=>{const record=records[ref];let link;try{const url=new URL(record?.official_url);if((url.protocol==='https:'||url.protocol==='http:')&&!url.username&&!url.password)link=url.href}catch{}return <article className="reference" key={ref}><div className="reference-heading"><span className="reference-number">{index+1}</span><strong>{record?.title||'Documentary source'}</strong></div>{record?.text&&<blockquote>{record.text}</blockquote>}{record?.error&&<p>{record.error}</p>}<div className="reference-meta"><span>{record?.jurisdiction}</span>{link&&<a href={link} target="_blank" rel="noopener noreferrer">Official source ↗</a>}<code>{ref}</code></div></article>})}</div>}</div>;
}

export default function ReportResponse({result,agent='Review & Synthesis',compact=false}){
  const view=readableResponse(result,agent),refs=responseCitations(result,agent);
  return <div className={'report-response '+(compact?'compact':'')}>
    {view.hypothetical&&<span className="response-context">Hypothetical scenario · assumptions remain explicit</span>}
    {view.priority&&<span className="response-context">Suggested priority: {view.priority}</span>}
    {view.lead&&<p className="response-lead">{view.lead}</p>}
    {view.sections.map(section=><section className="response-section" key={section.title}><h3>{section.title}</h3><ul>{section.items.map((item,index)=><li key={index}>{item.quote?<blockquote>{item.text}</blockquote>:<span>{item.text}</span>}{item.citations?.length>0&&<span className="inline-citations" aria-label="Source references">{item.citations.map(ref=><span key={ref}>[{refs.indexOf(ref)+1}]</span>)}</span>}</li>)}</ul></section>)}
    <SourceReferences citations={refs}/>
  </div>;
}
