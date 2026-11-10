import test from 'node:test';
import assert from 'node:assert/strict';
import {productIdentityAnswer,productIdentityPrompt,agentNames} from '../product.mjs';
import {agents} from '../src/agents.mjs';
import {createGateway} from '../server/gateway.mjs';

test('product identity names HR-Presents as the developer and owner',()=>{
  for(const question of ['can you tell about yourself','arent you developed by HR-Presents','Who owns you?','Who are your owners?','What does UNICRON stand for?']){
    const answer=productIdentityAnswer(question);
    assert.match(answer,/developed and owned by HR-Presents/);
    assert.doesNotMatch(answer,/I am (?:a large language model|not developed by HR-Presents)/);
  }
});

test('agent identity and visible roster share the six real checkpoint names',()=>{
  assert.deepEqual(agentNames,agents.map(agent=>agent.name));
  const answer=productIdentityAnswer('How many agents do you have?');
  for(const name of agentNames)assert(answer.includes(name));
  assert.match(answer,/six specialized agents/);
  assert.match(answer,/before an investigation starts/);
});

test('model attribution distinguishes the underlying model from product ownership',()=>{
  const answer=productIdentityAnswer('Aren’t you developed by Alibaba?');
  assert.match(answer,/UNICRON is developed and owned by HR-Presents/);
  assert.match(answer,/Qwen model family is developed by Alibaba/);
});

test('case analysis and agent findings are not intercepted as identity questions',()=>{
  for(const question of ['Assess AI agents handling UAE healthcare data.','What did your agents find in this investigation?','Compare Qwen and another model for healthcare governance.']){
    assert.equal(productIdentityAnswer(question),null);
  }
});

test('identity answers remain correct despite previous mistaken model messages',async()=>{
  const gateway=createGateway({UNICRON_API_URL:'https://backend.example',UNICRON_API_TOKEN:'test',UNICRON_MODEL_VIA_BACKEND:'1'}, {fetcher:()=>{throw Error('Identity must not be guessed by a model');}});
  const request=(path,body)=>new Request('https://site.example/api/unicron'+path,{
    method:'POST',headers:{'Content-Type':'application/json','oai-authenticated-user-id':'owner'},body:JSON.stringify(body),
  });
  const context=[{role:'assistant',content:'I am developed by Alibaba and do not have agents.'}];
  const route=await (await gateway(request('/chat/route',{question:'Who developed you?'}))).json();
  assert.equal(route.route,'chat');
  for(const path of ['/chat','/cases/CIV-1/desk']){
    const response=await gateway(request(path,{question:'arent you developed by HR-Presents',context,mode:'synthesis'}));
    assert.equal(response.status,200);
    const result=await response.json();
    assert.match(result.answer,/developed and owned by HR-Presents/);
    assert.deepEqual(result.citations,[]);
    assert.equal(result.answer_origin,'product_configuration');
  }
});

test('ordinary conversation receives canonical identity in its system context',async()=>{
  let captured;
  const gateway=createGateway({UNICRON_API_URL:'https://backend.example',UNICRON_API_TOKEN:'test',UNICRON_MODEL_VIA_BACKEND:'1'}, {fetcher:async(url,options)=>{
    assert(url.endsWith('/model/completion'));
    captured=JSON.parse(options.body);
    return Response.json({model:'qwen-local',choices:[{message:{content:'Evidence-grounded means statements are supported by identifiable sources.'}}]});
  }});
  const response=await gateway(new Request('https://site.example/api/unicron/chat',{
    method:'POST',headers:{'Content-Type':'application/json','oai-authenticated-user-id':'owner'},
    body:JSON.stringify({question:'What does evidence-grounded mean?',context:[]}),
  }));
  assert.equal(response.status,200);
  assert(captured.messages[0].content.includes(productIdentityPrompt));
  for(const name of agentNames)assert(captured.messages[0].content.includes(name));
});
