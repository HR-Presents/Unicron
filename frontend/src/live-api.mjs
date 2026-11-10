const base='/api/unicron';
export const forCase=id=>`/cases/${encodeURIComponent(id)}`;

export async function api(path,{method='GET',body,signal}={}) {
  const headers={Accept:'application/json'};
  const multipart=body instanceof FormData;
  if(body!==undefined && !multipart)headers['Content-Type']='application/json';
  const controller=new AbortController();
  const abort=()=>controller.abort();
  if(signal?.aborted)controller.abort();
  else signal?.addEventListener('abort',abort,{once:true});
  const timer=setTimeout(abort,method==='GET'?15000:150000);
  try {
  const response=await fetch(base+path,{
    method,headers,body:body===undefined || multipart?body:JSON.stringify(body),signal:controller.signal,
    cache:'no-store',credentials:'same-origin',
  });
  if(!(response.headers.get('Content-Type')??'').includes('application/json'))throw Error('Case activity is temporarily unavailable.');
  const data=await response.json();
  if(!response.ok){
    const detail=data?.detail;
    throw Error(typeof detail==='string'?detail:Array.isArray(detail)?detail.map(item=>item.msg).join(' · '):`Request failed (${response.status}).`);
  }
  return data;
  } catch(error) {
    if(controller.signal.aborted&&!signal?.aborted)throw Error('The request took longer than expected. Check recorded investigation activity before retrying.');
    throw error;
  } finally {clearTimeout(timer);signal?.removeEventListener('abort',abort);}
}

export async function runSnapshot(id,signal) {
  const path=forCase(id);
  const [jobs,executions]=await Promise.all([api(path+'/jobs',{signal}),api(path+'/executions',{signal})]);
  const job=jobs[0];
  const execution=executions[0];
  const belongsToJob=!job || !execution || new Date(execution.created_at)>=new Date(job.created_at);
  const currentExecution=job?.result_id ? executions.find(item=>item.id===job.result_id) : belongsToJob?execution:null;
  const events=currentExecution?await api(path+`/executions/${currentExecution.id}/events`,{signal}):[];
  return {job,execution:currentExecution,events};
}

export async function caseRecords(id,signal) {
  const path=forCase(id);
  const [investigations,sources,evidence,sessions,audit,reviews,analyses,triage]=await Promise.all([
    api(path+'/investigations',{signal}),api(path+'/sources',{signal}),api(path+'/evidence',{signal}),
    api(path+'/scenario-sessions',{signal}),api('/audit?caseId='+encodeURIComponent(id),{signal}),api(path+'/reviews',{signal}),api(path+'/evidence/analyses',{signal}),api(path+'/triage',{signal}),
  ]);
  return {investigations,sources,evidence,sessions,analyses,triage,audit:audit.filter(entry=>entry.case_id===id),reviews};
}

export function departmentFor(agent) {
  return {
    'Intake & Triage':'intake','Evidence Analyst':'evidence','Policy Advisor':'policy',
    'Global Benchmark Agent':'policy','Scenario Evaluator':'lab','Review & Synthesis':'oversight',
  }[agent];
}
