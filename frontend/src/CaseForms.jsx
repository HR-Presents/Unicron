import React,{useState} from 'react';
import {Icon} from './Icons.jsx';
import {departments} from './scenarios.mjs';

const read=(fields,key)=>String(fields.get(key)??'').trim();
const roles=[...departments.map(department=>department.role),'Global Benchmark Agent'];

export function NewCase({create,disabled}){
  const [open,setOpen]=useState(false);
  async function submit(event){
    event.preventDefault();
    const fields=new FormData(event.currentTarget);
    const item=await create({title:read(fields,'title'),summary:read(fields,'summary'),priority:read(fields,'priority'),domain:read(fields,'domain')});
    if(item)setOpen(false);
  }
  return <>
    <button className="button secondary" onClick={()=>setOpen(!open)} aria-expanded={open} disabled={disabled}><Icon name={open?'minus':'plus'} size={15}/> {open?'Close case intake':'New case'}</button>
    {open && <form className="record workbench-form intake-form" onSubmit={submit}>
      <div className="form-columns"><label>Case title<input name="title" minLength={3} maxLength={180} required/></label><label>Priority<select name="priority" defaultValue="Medium"><option>Low</option><option>Medium</option><option>High</option></select></label></div>
      <label>Domain
        <select name="domain" defaultValue="Healthcare">
          <option>Healthcare</option>
          <option>Government services</option>
          <option>Education</option>
          <option>Transportation</option>
          <option>Cybersecurity</option>
          <option>Financial services</option>
          <option>Energy</option>
        </select>
      </label>
      <label>Case summary<textarea name="summary" minLength={3} maxLength={8000} required placeholder="Describe the observed issue and its impact using approved exercise data."/></label>
      <button className="button primary" disabled={disabled}>Save case <Icon name="right" size={16}/></button>
    </form>}
  </>;
}

export function ScenarioAuthor({create,disabled}){
  const [open,setOpen]=useState(false);
  const [count,setCount]=useState(2);
  async function submit(event){
    event.preventDefault();
    const fields=new FormData(event.currentTarget);
    const result=await create({
      name:read(fields,'name'),initial_conditions:read(fields,'conditions'),expected_outcome:read(fields,'expected'),
      events:Array.from({length:count},(_,index)=>({
        title:read(fields,`title-${index}`),description:read(fields,`description-${index}`),
        target_agent:read(fields,`role-${index}`),offset_seconds:0,
      })),
    });
    if(result){setOpen(false);setCount(2);}
  }
  return <>
    <button className="button secondary" onClick={()=>setOpen(!open)} aria-expanded={open} disabled={disabled}><Icon name={open?'minus':'plus'} size={15}/> {open?'Close scenario builder':'New scenario'}</button>
    {open && <form className="record workbench-form intake-form" onSubmit={submit}>
      <label>Exercise name<input name="name" minLength={3} maxLength={160} required/></label>
      <label>Initial conditions<textarea name="conditions" minLength={3} maxLength={4000} required/></label>
      <label>Expected outcome<textarea name="expected" minLength={3} maxLength={2000} required/></label>
      {Array.from({length:count},(_,index)=><fieldset key={index}><legend>Event {index+1}</legend>
        <div className="form-columns"><label>Event title<input name={`title-${index}`} minLength={3} maxLength={160} required/></label><label>Assigned role<select name={`role-${index}`} defaultValue={roles[index%roles.length]}>{roles.map(role=><option key={role}>{role}</option>)}</select></label></div>
        <label>Event details<textarea name={`description-${index}`} minLength={3} maxLength={2000} required/></label>
      </fieldset>)}
      <div className="review-actions">
        <button type="button" className="button secondary" onClick={()=>setCount(count-1)} disabled={count<=2}>Remove last event</button>
        <button type="button" className="button secondary" onClick={()=>setCount(count+1)} disabled={count>=8}>Add event</button>
        <button className="button primary" disabled={disabled}>Save scenario <Icon name="right" size={16}/></button>
      </div>
    </form>}
  </>;
}
