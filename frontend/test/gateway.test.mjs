import test from 'node:test';
import assert from 'node:assert/strict';
import {createGateway} from '../server/gateway.mjs';

const config={UNICRON_API_URL:'https://backend.example',UNICRON_API_TOKEN:'test-only',UNICRON_MODEL_URL:'https://inference.example/v1',UNICRON_MODEL_NAME:'test-model',UNICRON_REVIEWER_TOKEN:'server-review-token',UNICRON_REVIEWER_USER_ID:'owner'};
const request=(path,options={})=>new Request('https://site.example/api/unicron'+path,{...options,headers:{'oai-authenticated-user-id':'owner',...options.headers}});
const response=(value,status=200)=>Response.json(value,{status});

test('hosted API requires Site identity, a secured upstream and same-origin mutations',async()=>{
  const gateway=createGateway({}, {fetcher:()=>{throw Error('Must not call upstream');}});
  assert.equal((await gateway(new Request('https://site.example/api/unicron/connection'))).status,401);
  assert.equal((await (await gateway(request('/connection'))).json()).state,'unavailable');
  assert.equal((await gateway(request('/cases',{method:'POST',headers:{Origin:'https://elsewhere.example'}}))).status,403);
  assert.equal((await gateway(request('/cases/CIV-1/evidence/source/admin'))).status,404);
  const insecure=createGateway({...config,UNICRON_API_URL:'http://127.0.0.1:42515'});
  assert.equal((await (await insecure(request('/connection'))).json()).state,'unavailable');
});

test('gateway reads current backend data and forwards an allowlisted queued action',async()=>{
  let phase='queued';
  const gateway=createGateway(config,{fetcher:async(url,options)=>{
    assert.equal(options.headers.get('Authorization'),'Bearer test-only');
    if(url.endsWith('/health'))return response({service:'civitas-api',version:'0.3.0'});
    if(url.endsWith('/cases'))return response([{id:'CIV-1'}]);
    if(url.endsWith('/investigate/async') && options.method==='POST')return response({id:'job-1',status:phase},202);
    if(url.endsWith('/jobs'))return response([{id:'job-1',status:phase}]);
    throw Error('Unexpected test URL');
  }});
  assert.equal((await (await gateway(request('/connection'))).json()).state,'connected');
  assert.equal((await gateway(request('/cases/CIV-1/investigate/async',{method:'POST'}))).status,202);
  phase='running';
  assert.equal((await (await gateway(request('/cases/CIV-1/jobs'))).json())[0].status,'running');
});

test('scenario projection withholds unreleased event text and expected outcome',async()=>{
  const gateway=createGateway(config,{fetcher:async()=>response([{status:'running',expected_outcome:'target',events:[
    {id:'first',title:'Released',description:'visible',released_at:'2026-11-06T12:00:00Z'},
    {id:'second',title:'future title',description:'future text',target_agent:'future role',position:1,released_at:null},
  ]}])});
  const sessions=await (await gateway(request('/cases/CIV-1/scenario-sessions'))).json();
  assert.equal(sessions[0].events[0].description,'visible');
  assert.equal(sessions[0].events[1].title,undefined);
  assert.equal(sessions[0].expected_outcome,undefined);
});

test('model-backed desk uses retrieved excerpts and rejects fabricated citations',async()=>{
  let citation='doc-1#p1';
  let completionCalls=0;
  const gateway=createGateway(config,{fetcher:async(url,options)=>{
    if(url.includes('/evidence/search?')){
      assert.ok(url.includes('continuity'));
      return response({results:[{document_id:'doc-1',citation:'doc-1#p1',filename:'exercise.txt',content:'An assisted desk preserves continuity.'}]});
    }
    if(url.endsWith('/sources'))return response([{document_id:'doc-1',document_title:'Continuity exercise',verification_status:'verified'}]);
    if(url.endsWith('/chat/completions')){
      completionCalls++;
      const prompt=JSON.parse(options.body);
      assert.equal(prompt.model,'test-model');
      assert.ok(prompt.messages[1].content.includes('doc-1#p1'));
      return response({choices:[{message:{content:JSON.stringify({answer:'Offer an assisted desk.',citations:[citation],uncertainty:'Capacity unverified.'})}}]});
    }
    throw Error('Unexpected test URL');
  }});
  const ask=()=>gateway(request('/cases/CIV-1/desk',{method:'POST',body:JSON.stringify({question:'How do we maintain continuity?'})}));
  const result=await (await ask()).json();
  assert.equal(result.status,'answered');
  assert.equal(result.citations[0].verification,'verified');
  citation='fabricated#p1';
  assert.equal((await ask()).status,502);
  assert.equal(completionCalls,2);
});

test('unrestricted conversational roles use model knowledge without matching PDFs',async()=>{
  const gateway=createGateway(config,{fetcher:async(url,options)=>{
    if(url.includes('/evidence/search?'))return response({results:[]});
    if(url.endsWith('/sources'))return response([]);
    if(url.endsWith('/investigations'))return response([]);
    if(url.endsWith('/chat/completions')){
      const payload=JSON.parse(options.body);
      const prompt=payload.messages[1].content;
      assert.deepEqual(JSON.parse(prompt).excerpts,[]);
      assert.match(payload.messages[0].content,/general model knowledge/i);
      return response({choices:[{finish_reason:'stop',message:{content:JSON.stringify({
        answer:'Use clinical validation, bias monitoring, and human oversight.',
        citations:[],
        uncertainty:'These are general safeguards, not verified UAE policy requirements.',
      })}}]});
    }
    throw Error('Unexpected test URL: '+url);
  }});

  for(const mode of ['triage','evidence','continuity','synthesis']){
    const result=await gateway(request('/cases/CIV-1/desk',{
      method:'POST',
      body:JSON.stringify({
        question:'Explain safeguards for AI-assisted patient prioritization.',
        mode,
      }),
    }));
    const data=await result.json();
    assert.equal(result.status,200,mode);
    assert.equal(data.status,'answered',mode);
    assert.deepEqual(data.citations,[],mode);
    assert.match(data.answer,/clinical validation/i);
  }
});

test('evidence upload and reviewer provenance preserve multipart and credential boundaries',async()=>{
  const calls=[];
  const gateway=createGateway(config,{fetcher:async(url,options)=>{
    calls.push([url,options]);
    return response({id:'doc-1'},201);
  }});
  const body=new FormData();
  body.set('file',new File(['Published service continuity policy text.'],'policy.txt'));
  body.set('source_note','Public guidance');
  assert.equal((await gateway(request('/cases/CIV-1/evidence',{method:'POST',body}))).status,201);
  assert.match(calls[0][1].headers.get('Content-Type'),/^multipart\/form-data; boundary=/);
  assert.match(new TextDecoder().decode(calls[0][1].body),/Published service continuity/);
  const path='/cases/CIV-1/evidence/doc-1/provenance';
  assert.equal((await gateway(request(path,{method:'PUT',headers:{'oai-authenticated-user-id':'visitor','X-Reviewer-Key':'browser-key'},body:'{}'}))).status,403);
  assert.equal((await gateway(request(path,{method:'PUT',headers:{'X-Reviewer-Key':'browser-key'},body:'{}'}))).status,201);
  assert.equal(calls[1][1].headers['X-Reviewer-Key'],undefined);
  assert.equal(calls[1][1].headers.get('X-Reviewer-Key'),'server-review-token');
  assert.equal((await gateway(request('/cases/CIV-1/evidence',{method:'POST',body:'{}'}))).status,415);
});

test('policy gap adviser refuses unverified evidence before model invocation',async()=>{
  let calls=0;
  const gateway=createGateway(config,{fetcher:async url=>{
    if(url.includes('/evidence/search?'))return response({results:[{document_id:'doc-1',citation:'doc-1#p1',content:'Continuity plan'}]});
    if(url.endsWith('/sources'))return response([]);
    if(url.includes('/evidence/verified/search?'))return response({results:[]});
    calls++;
    throw Error('Model must not be called');
  }});
  const reply=await gateway(request('/cases/CIV-1/desk',{method:'POST',body:JSON.stringify({question:'Is there a continuity policy gap?',mode:'policy_gap'})}));
  assert.equal((await reply.json()).status,'evidence_required');
  assert.equal(calls,0);
});

test('only selected case activity is returned and implementation details stay behind the gateway',async()=>{
  const gateway=createGateway(config,{fetcher:async url=>{
    if(url.endsWith('/jobs'))return response([{id:'job-1',status:'failed',worker_id:'private-worker',error_type:'http://private.internal:42515'}]);
    if(url.endsWith('/audit'))return response([{case_id:'CIV-1',action:'case.created'},{case_id:'CIV-2',action:'case.created'}]);
    return response({detail:'http://private.internal:42515 secret stack trace'},500);
  }});
  assert.equal((await gateway(request('/health'))).status,404);
  const jobs=await (await gateway(request('/cases/CIV-1/jobs'))).json();
  assert.deepEqual(jobs,[{id:'job-1',status:'failed'}]);
  assert.equal((await gateway(request('/audit'))).status,422);
  assert.deepEqual(await (await gateway(request('/audit?caseId=CIV-1'))).json(),[{case_id:'CIV-1',action:'case.created'}]);
  const failure=await gateway(request('/cases'));
  assert.equal(failure.status,503);
  assert.doesNotMatch(await failure.text(),/private\.internal|stack trace/);
});

test('all six follow-up roles apply their matching evidence restrictions and recorded context',async()=>{
  const roles=['triage','evidence','policy_gap','benchmark','continuity','synthesis'];
  const names=['Intake & Triage','Evidence Analyst','Policy Advisor','Global Benchmark Agent','Scenario Evaluator','Review & Synthesis'];
  const source=(id,type,jurisdiction)=>({document_id:id,verification_status:'verified',source_type:type,jurisdiction});
  const registry=[source('local','policy','UAE'),source('ref-1','benchmark','United Kingdom'),source('ref-2','benchmark','Singapore')];
  const results=registry.map(item=>({document_id:item.document_id,citation:item.document_id+'#p1',content:'Assisted service continuity practice.'}));
  const prompts=[];
  const gateway=createGateway(config,{fetcher:async(url,options)=>{
    if(url.includes('/evidence/search?'))return response({results});
    if(url.endsWith('/sources'))return response(registry);
    if(url.endsWith('/investigations'))return response([{id:'run-1',stages:names.map(agent=>({agent,status:'completed',result:{summary:'Recorded guidance'}}))}]);
    if(url.endsWith('/chat/completions')){
      const data=JSON.parse(JSON.parse(options.body).messages[1].content);
      prompts.push(data);
      return response({choices:[{message:{content:JSON.stringify({answer:'Cited advisory briefing.',citations:data.excerpts.map(item=>item.id)})}}]});
    }
    throw Error('Unexpected route');
  }});
  for(const mode of roles){
    const result=await gateway(request('/cases/CIV-1/desk',{method:'POST',body:JSON.stringify({question:'What continuity evidence applies?',mode})}));
    assert.equal((await result.json()).status,'answered');
  }
  assert.match(prompts[0].recordedAdvisory,/Recorded guidance/);
  assert.deepEqual(prompts[2].excerpts.map(item=>item.id),['local#p1']);
  assert.ok(prompts.every(prompt=>prompt.excerpts.every(item=>!item.id.startsWith('RUN-'))));
  assert.deepEqual(prompts[3].excerpts.map(item=>item.id),['ref-1#p1','ref-2#p1']);
  assert.match(prompts[4].recordedAdvisory,/Recorded guidance/);
  assert.match(prompts[5].recordedAdvisory,/Recorded guidance/);
});

test('standards routes require reviewer access and preserve credential boundaries',async()=>{
  const calls=[];
  const gateway=createGateway(config,{
    fetcher:async(url,options)=>{
      calls.push({url,options});
      return response([],200);
    },
  });

  const read=await gateway(request('/standards/frameworks'));
  assert.equal(read.status,200);
  assert.ok(calls[0].url.endsWith('/api/standards/frameworks'));

  const blocked=await gateway(request(
    '/standards/frameworks',
    {
      method:'POST',
      headers:{'oai-authenticated-user-id':'visitor'},
      body:JSON.stringify({}),
    },
  ));
  assert.equal(blocked.status,403);

  const created=await gateway(request(
    '/standards/frameworks',
    {
      method:'POST',
      headers:{'X-Reviewer-Key':'browser-supplied-secret'},
      body:JSON.stringify({}),
    },
  ));
  assert.equal(created.status,200);

  const forwarded=calls.at(-1);
  assert.equal(
    forwarded.options.headers.get('X-Reviewer-Key'),
    'server-review-token'
  );
  assert.notEqual(
    forwarded.options.headers.get('X-Reviewer-Key'),
    'browser-supplied-secret'
  );

  const mapping=await gateway(request(
    '/cases/CIV-1/standards/mappings'
  ));
  assert.equal(mapping.status,200);

  const review=await gateway(request(
    '/cases/CIV-1/standards/mappings/MAP-1/review',
    {
      method:'POST',
      body:JSON.stringify({
        decision:'verified',
        reviewer:'Authorized Reviewer',
        rationale:'Evidence association reviewed and confirmed.',
      }),
    },
  ));
  assert.equal(review.status,200);

  assert.equal(
    (await gateway(request('/standards/private'))).status,
    404
  );
});

test('standards mapping review forwards the selected decision securely',async()=>{
  const calls=[];
  const gateway=createGateway(config,{
    fetcher:async(url,options)=>{
      calls.push({url,options});
      return response({review_status:'verified'},201);
    },
  });

  const path='/cases/CIV-1/standards/mappings/MAP-1/review';
  const payload={
    decision:'verified',
    reviewer:'Authorized Reviewer',
    rationale:'The cited passage supports the recorded evidence association.',
  };

  const result=await gateway(request(path,{
    method:'POST',
    body:JSON.stringify(payload),
  }));

  assert.equal(result.status,201);
  assert.equal(calls.length,1);
  assert.deepEqual(JSON.parse(calls[0].options.body),payload);
  assert.equal(
    calls[0].options.headers.get('X-Reviewer-Key'),
    'server-review-token'
  );
});
