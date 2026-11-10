import React from 'react';
const hiddenKey=/^(?:raw(?:_.*)?|chain_of_thought|thinking|reasoning_content|worker_id|api_key|error_type|error_message|human_review_required|automated_approval_permitted|analysis_mode)$/i;
const label=key=>key.replaceAll('_',' ');
export function DataValue({value,sourceLink=false}){
  if(value===null || value===undefined || value==='')return <span>—</span>;
  if(Array.isArray(value))return value.length?<ul className="output-list">{value.map((item,index)=><li key={index}><DataValue value={item}/></li>)}</ul>:<span>None recorded</span>;
  if(typeof value==='object')return <dl className="output-fields">{Object.entries(value).filter(([key])=>!hiddenKey.test(key)).map(([key,item])=><div key={key}><dt>{label(key)}</dt><dd><DataValue value={item} sourceLink={key==='official_url'}/></dd></div>)}</dl>;
  if(typeof value==='boolean')return <span>{value?'Yes':'No'}</span>;
  if(sourceLink && typeof value==='string' && /^https:\/\//i.test(value))return <a className="inline-action" href={value} rel="noreferrer" target="_blank">Source reference</a>;
  return <span>{String(value)}</span>;
}

