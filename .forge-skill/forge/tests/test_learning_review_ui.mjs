import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const html = readFileSync(new URL('../../skills/learning-collector/assets/review.html', import.meta.url), 'utf8');
const handlers = html.slice(html.indexOf('function renderSummaryJob('), html.indexOf(';load();loadHookStatus();')) + ';';
const scopeHandlers = ['project', 'skill'].map(id => html.match(
  new RegExp(`\\$\\('${id}'\\)\\.onchange=\\(\\)=>\\{.*?\\};`),
)[0]).join('\n');
const estimate = {sourceCount: 2, evidenceBytes: 1024, estimatedMapBatches: 1, limits: {maxGenerationBatches: 128}};
const job = {jobId: 'job-a', submissionId:'submission-a', projectId: 'a', skill: 'plan', status: 'PENDING', sourceCount: 2};
const response = value => ({ok: true, json: async () => value});
for(const language of ['en','zh-CN'])for(const status of ['DRAFT','REVIEWED','ARCHIVED'])for(const withWindow of [false,true]) {
  test(`full Summary render: ${language}, ${status}, window=${withWindow}`,()=>{
    const source=readFileSync(new URL('../../skills/learning-collector/assets/versions.html',import.meta.url),'utf8');
    const elements={versions:{innerHTML:''},message:{textContent:'',className:''}};
    const context=vm.createContext({
      window:{ForgeI18n:{language}},$ : id=>elements[id],
      document:{querySelectorAll:()=>[]},syncOverlayButton:()=>{},
    });
    vm.runInContext(`const esc=value=>String(value??'');const text=JSON.stringify;let projects=[{projectId:'p',name:'Project P'}],values=[];`,context);
    vm.runInContext(source.slice(source.indexOf('function metrics('),source.indexOf('function evidenceRows(')),context);
    context.version={project_id:'p',skill:'plan',version:1,source_count:1,created_at:'now',lifecycle_status:status,
      summary:{format:'forge-skill-training-summary-v6',sourceCount:1,
        ...(withWindow?{window:{months:6,classicRecords:2}}:{}),
        rules:[{id:'rule-1',stage:'PRE_CHECK',status:status==='DRAFT'?'PENDING':'CONFIRMED',title:'Validate input',instruction:'Check input',trigger:'Before execution',verification:'Verify input',supportCount:1,sourceRecordIds:['r1']}]},
    };
    vm.runInContext('values=[version];render()',context);
    const output=elements.versions.innerHTML;
    assert.match(output,/Project P/);assert.match(output,/Check input/);assert.match(output,/data-decisions/);
    assert.equal(output.includes('窗口 6 个月'),withWindow);
    assert.equal(output.includes('经典 2 条'),withWindow);
    assert.equal(output.includes('data-save'),status==='DRAFT');
    assert.equal(output.includes('data-overlay-select'),status==='REVIEWED');
    if(status!=='DRAFT'){
      assert.match(output,/<textarea data-field="instruction" disabled>/);
      assert.match(output,/<select data-field="stage" disabled>/);
      assert.match(output,/<select data-field="status" disabled>/);
    }else{
      assert.match(output,/<textarea data-field="instruction" >/);
      assert.match(output,/<select data-field="stage" >/);
      assert.match(output,/<select data-field="status" >/);
    }
    if(status==='REVIEWED')assert.match(output,language==='en'?/Rules are read-only/:/规则为只读/);
    assert.equal(elements.message.textContent,'1 个汇总版本');
  });
}
const deferred = () => {
  let resolve;
  const promise = new Promise(done => {resolve = done;});
  return {promise, resolve};
};
function page(fetch, confirmed = true, storage = new Map()) {
  const elements = Object.fromEntries(['project', 'skill', 'summarize', 'summary-retry', 'summary-resend', 'summary-message'].map(id => [id, {}]));
  elements['summary-resend'].hidden=true;
  elements.project.value = 'a';
  elements.project.selectedOptions = [{textContent: 'Project A'}];
  elements.skill.value = 'plan';
  const confirmations = [], polls = [], timers=new Map();let timerId=0,summaryLoads=0,submissionNumber=0;
  const context = vm.createContext({
    $: id => elements[id], window: {ForgeI18n: {language: 'en'}}, URLSearchParams,
    crypto:{randomUUID:()=> ++submissionNumber===1?'submission-a':`submission-${submissionNumber}`},
    sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},
    fetch: (url, options) => {polls.push({url, options});return fetch(url, options);},
    confirm: message => {confirmations.push(message);return confirmed;},
    tr: value => value, setTimeout: (callback,delay) => {timers.set(++timerId,{callback,delay});return timerId},clearTimeout:id=>timers.delete(id),loadSummaries: async () => {summaryLoads++},
    load: () => {}, syncProjectAction: () => {},
  });
  vm.runInContext('let summaryPollSequence=0,currentSummaryJob=null,currentPage=1;\n' + handlers + scopeHandlers, context);
  function switchScope(id, value) {
    elements[id].value = value;
    if(id === 'project')elements.project.selectedOptions = [{textContent: 'Project B'}];
    elements[id].onchange();
  }
  return {elements, confirmations, polls, context, switchScope,timers,summaryLoads:()=>summaryLoads,
    nextPoll:async()=>{const [id,timer]=timers.entries().next().value;timers.delete(id);await timer.callback()},
  };
}

for(const [id, value] of [['project', 'b'], ['skill', 'debug']]) {
  test(`scope change during estimate cancels generation: ${id}`, async () => {
    const waiting = deferred();
    const ui = page(() => waiting.promise);
    const generating = ui.elements.summarize.onclick();
    assert.equal(ui.elements.summarize.disabled, true);
    ui.switchScope(id, value);
    waiting.resolve(response(estimate));
    await generating;
    assert.deepEqual(ui.confirmations, []);
    assert.equal(ui.polls.length, 1);
  });
}

test('returning to the original project still discards the old estimate', async () => {
  const waiting = deferred(), ui = page(() => waiting.promise);
  const generating = ui.elements.summarize.onclick();
  ui.switchScope('project', 'b');
  ui.switchScope('project', 'a');
  waiting.resolve(response(estimate));
  await generating;
  assert.equal(ui.confirmations.length, 0);
});

test('scope change after submission cannot overwrite the new scope or poll the old job', async () => {
  const waiting = deferred(), submitted = deferred();
  const ui = page((_url, options) => {
    if(options){submitted.resolve();return waiting.promise;}
    return Promise.resolve(response(estimate));
  });
  const generating = ui.elements.summarize.onclick();
  await submitted.promise;
  ui.switchScope('project', 'b');
  ui.elements['summary-message'].textContent = 'Project B status';
  waiting.resolve(response(job));
  await generating;
  assert.equal(ui.elements['summary-message'].textContent, 'Project B status');
  assert.equal(ui.polls.length, 2);
  assert.match(ui.confirmations[0], /Project A \/ plan/);
  assert.equal(JSON.parse(ui.polls[1].options.body).projectId, 'a');
});

test('normal generation polls the same project and skill', async () => {
  const ui = page((url, options) => Promise.resolve(response(
    url.includes('estimate') ? estimate : job,
  )));
  await ui.elements.summarize.onclick();
  await Promise.resolve();
  const polling = new URL(ui.polls[2].url, 'http://localhost');
  assert.equal(polling.searchParams.get('project'), 'a');
  assert.equal(polling.searchParams.get('skill'), 'plan');
  assert.equal(polling.searchParams.get('submission'), 'submission-a');
});

test('declining confirmation sends no records and restores the button', async () => {
  const ui = page(() => Promise.resolve(response(estimate)), false);
  await ui.elements.summarize.onclick();
  assert.equal(ui.confirmations.length, 1);
  assert.equal(ui.polls.length, 1);
  assert.equal(ui.elements.summarize.disabled, false);
});

function failedSummaryJob(ui){
  vm.runInContext("renderSummaryJob({jobId:'previous-failed',projectId:'a',skill:'plan',status:'FAILED',retryable:true,sourceCount:2})",ui.context);
}

for(const action of ['summarize','summary-retry'])for(const failure of ['network','json'])for(const status of ['RUNNING','SUCCEEDED'])test(`${action} recovers accepted POST after ${failure} response loss, status=${status}`,async()=>{
  let committedJobs=0;
  const ui=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options){
      committedJobs++;
      if(failure==='network')throw new TypeError('response lost after commit');
      return {ok:true,json:async()=>{throw new SyntaxError('invalid response JSON')}};
    }
    return response({...job,jobId:'accepted-job',status,version:5,retryable:false});
  });
  if(action==='summary-retry')failedSummaryJob(ui);
  await ui.elements[action].onclick();
  assert.equal(committedJobs,1);
  assert.equal(vm.runInContext('currentSummaryJob.jobId',ui.context),'accepted-job');
  assert.equal(ui.elements.summarize.disabled,status==='RUNNING');
  assert.equal(ui.elements['summary-retry'].hidden,true);
  assert.equal(ui.timers.size,status==='RUNNING'?1:0);
  if(status==='RUNNING')await ui.nextPoll();
  else {assert.match(ui.elements['summary-message'].textContent,/v5/);assert.equal(ui.summaryLoads(),1)}
  assert.equal(committedJobs,1);
  const queries=ui.polls.filter(request=>!request.options&&!request.url.includes('estimate'));
  assert.ok(queries.length>0);
  assert.ok(queries.every(request=>request.url.includes('project=a')&&request.url.includes('skill=plan')&&!request.url.includes('job=')));
  assert.ok(queries.every(request=>request.url.includes('submission=submission-a')));
});

for(const action of ['summarize','summary-retry'])test(`${action} keeps submission disabled until failed recovery GET succeeds`,async()=>{
  let committedJobs=0,queries=0;
  const ui=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options){committedJobs++;throw new TypeError('response lost after commit')}
    if(queries++===0)throw new TypeError('status offline');
    return response({...job,jobId:'accepted-job',status:'RUNNING',retryable:false});
  });
  if(action==='summary-retry')failedSummaryJob(ui);
  await ui.elements[action].onclick();
  assert.equal(ui.elements.summarize.disabled,true);assert.equal(ui.elements['summary-retry'].hidden,true);
  assert.match(ui.elements['summary-message'].textContent,/retrying/);
  assert.equal(ui.timers.size,1);assert.equal([...ui.timers.values()][0].delay,3000);
  await ui.nextPoll();
  assert.equal(committedJobs,1);assert.equal(ui.elements.summarize.disabled,true);
  assert.equal(vm.runInContext('currentSummaryJob.jobId',ui.context),'accepted-job');
});

for(const action of ['summarize','summary-retry'])test(`${action} retains uncertainty before reservation and tracks the later prepared job`,async()=>{
  let posts=0,queries=0;
  const ui=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options){posts++;throw new TypeError('submission connection lost')}
    if(queries++===0)return {ok:false,status:404,json:async()=>({code:'SUMMARY_SUBMISSION_NOT_FOUND',error:'submission not yet registered'})};
    return response({...job,status:queries===2?'PREPARING':'RUNNING',retryable:false});
  });
  if(action==='summary-retry')failedSummaryJob(ui);
  await ui.elements[action].onclick();
  assert.equal(posts,1);assert.equal(ui.elements.summarize.disabled,true);
  assert.equal(ui.elements['summary-retry'].hidden,true);assert.equal(ui.timers.size,1);
  assert.match(ui.elements['summary-message'].textContent,/retrying/);
  await ui.nextPoll();assert.equal(vm.runInContext('currentSummaryJob.status',ui.context),'PREPARING');
  assert.equal(ui.elements.summarize.disabled,true);assert.equal(ui.timers.size,1);
  await ui.nextPoll();assert.equal(vm.runInContext('currentSummaryJob.status',ui.context),'RUNNING');
  assert.equal(posts,1);assert.equal(ui.elements.summarize.disabled,true);
});

for(const action of ['summarize','summary-retry'])test(`${action} recovery response cannot overwrite a changed scope`,async()=>{
  const waiting=deferred(),discovering=deferred();
  const ui=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options)throw new TypeError('response lost');
    discovering.resolve();return waiting.promise;
  });
  if(action==='summary-retry')failedSummaryJob(ui);
  const running=ui.elements[action].onclick();await discovering.promise;
  ui.switchScope('project','b');ui.elements['summary-message'].textContent='Project B status';
  waiting.resolve(response({...job,status:'RUNNING'}));await running;
  assert.equal(ui.elements['summary-message'].textContent,'Project B status');
  assert.equal(ui.timers.size,0);
});

test('preflight failure restores generation without starting submission recovery',async()=>{
  const ui=page(async()=>{throw new TypeError('preflight unavailable')});
  await ui.elements.summarize.onclick();
  assert.equal(ui.polls.length,1);assert.equal(ui.elements.summarize.disabled,false);
  assert.equal(ui.timers.size,0);assert.match(ui.elements['summary-message'].textContent,/preflight unavailable/);
});

for(const action of ['summarize','summary-retry'])test(`${action} preserves explicit rejection when discovery returns an older terminal job`,async()=>{
  const ui=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options)return {ok:false,json:async()=>({error:'LLM configuration unavailable'})};
    return response({...job,status:'FAILED',retryable:true});
  });
  if(action==='summary-retry')failedSummaryJob(ui);
  await ui.elements[action].onclick();
  assert.equal(ui.elements.summarize.disabled,false);assert.equal(ui.elements['summary-retry'].hidden,false);
  assert.equal(ui.elements['summary-message'].textContent,'LLM configuration unavailable');
  assert.equal(ui.timers.size,0);assert.equal(ui.polls.filter(request=>request.options).length,1);
});

test('uncertain submission survives page reload and only clears after its terminal result',async()=>{
  const storage=new Map();
  const original=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options)throw new TypeError('response lost before reservation');
    return {ok:false,json:async()=>({code:'SUMMARY_SUBMISSION_NOT_FOUND',error:'not registered yet'})};
  },true,storage);
  await original.elements.summarize.onclick();
  assert.equal(storage.size,1);assert.equal(original.elements.summarize.disabled,true);
  let queries=0;
  const reloaded=page(async()=>response({...job,status:queries++===0?'PREPARING':'SUCCEEDED',version:7}),true,storage);
  await vm.runInContext('loadSummaryJob()',reloaded.context);
  assert.match(reloaded.polls[0].url,/submission=submission-a/);
  assert.equal(reloaded.elements.summarize.disabled,true);assert.equal(storage.size,1);
  await reloaded.nextPoll();
  assert.equal(reloaded.elements.summarize.disabled,false);assert.equal(storage.size,0);
  assert.match(reloaded.elements['summary-message'].textContent,/v7/);
  assert.ok(reloaded.polls.every(request=>!request.options));
});

test('receipt query refuses an older failed job with a different submission identity',async()=>{
  const ui=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options)throw new TypeError('response lost');
    return response({...job,submissionId:'old-submission',status:'FAILED',retryable:true});
  });
  await ui.elements.summarize.onclick();
  assert.equal(ui.elements.summarize.disabled,true);assert.equal(ui.elements['summary-retry'].hidden,true);
  assert.equal(ui.timers.size,1);assert.match(ui.elements['summary-message'].textContent,/identity does not match/);
});

for(const status of ['FAILED','INTERRUPTED'])test(`preparation receipt ${status} permits a new submission without a job retry`,async()=>{
  const storage=new Map();
  const ui=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options)throw new TypeError('response lost');
    return response({...job,jobId:null,status,retryable:false,errorCode:'PREPARATION_FAILED'});
  },true,storage);
  await ui.elements.summarize.onclick();
  assert.equal(ui.elements.summarize.disabled,false);assert.equal(ui.elements['summary-retry'].hidden,true);
  assert.equal(ui.timers.size,0);assert.equal(storage.size,0);
  assert.match(ui.elements['summary-message'].textContent,/PREPARATION_FAILED/);
});

for(const action of ['summarize','summary-retry'])test(`${action} can resend a never-delivered request after reload using identical payload and ID`,async()=>{
  const storage=new Map(),sent=[];
  const missing=()=>({ok:false,status:404,json:async()=>({code:'SUMMARY_SUBMISSION_NOT_FOUND',error:'not delivered'})});
  const original=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options){sent.push({url,body:options.body});throw new TypeError('lost before delivery')}
    return missing();
  },true,storage);
  if(action==='summary-retry')failedSummaryJob(original);
  await original.elements[action].onclick();
  assert.equal(original.elements['summary-resend'].hidden,false);
  assert.equal(sent.length,1);
  let accepted=false,committedJobs=0;
  const reloaded=page(async(url,options)=>{
    if(options){
      assert.equal(url,sent[0].url);assert.equal(options.body,sent[0].body);
      if(!accepted){accepted=true;committedJobs++}
      return response({...job,status:'RUNNING'});
    }
    return accepted?response({...job,status:'RUNNING'}):missing();
  },true,storage);
  await vm.runInContext('loadSummaryJob()',reloaded.context);
  assert.equal(reloaded.elements['summary-resend'].hidden,false);
  await reloaded.elements['summary-resend'].onclick();
  assert.equal(committedJobs,1);assert.equal(reloaded.elements['summary-resend'].hidden,true);
  assert.equal(reloaded.elements.summarize.disabled,true);assert.equal(reloaded.timers.size,1);
  assert.equal(vm.runInContext('currentSummaryJob.jobId',reloaded.context),'job-a');
});

test('resending while the original request arrives late retains one committed job and prevents concurrent resends',async()=>{
  const waiting=deferred();let saved,committedJobs=0,resent=0,arrived=false;
  const ui=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options){
      if(!saved){saved=options.body;throw new TypeError('original response lost')}
      assert.equal(options.body,saved);resent++;
      if(!arrived){arrived=true;committedJobs++}
      return waiting.promise;
    }
    return arrived?response({...job,status:'RUNNING'}):{ok:false,json:async()=>({code:'SUMMARY_SUBMISSION_NOT_FOUND',error:'not yet delivered'})};
  });
  await ui.elements.summarize.onclick();
  // The original server request arrives just before the user resends.
  arrived=true;committedJobs++;
  const resending=ui.elements['summary-resend'].onclick();
  await ui.elements['summary-resend'].onclick();assert.equal(resent,1);
  waiting.resolve(response({...job,status:'RUNNING'}));await resending;
  assert.equal(committedJobs,1);assert.equal(ui.elements['summary-resend'].hidden,true);
  assert.equal(ui.polls.filter(request=>request.options).length,2);
});

test('failed resend retains original request and offers another same-ID resend',async()=>{
  const bodies=[];
  const ui=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options){bodies.push(options.body);throw new TypeError('offline')}
    return {ok:false,json:async()=>({code:'SUMMARY_SUBMISSION_NOT_FOUND',error:'not delivered'})};
  });
  await ui.elements.summarize.onclick();await ui.elements['summary-resend'].onclick();
  assert.equal(bodies.length,2);assert.equal(bodies[0],bodies[1]);
  assert.equal(ui.elements['summary-resend'].hidden,false);assert.equal(ui.elements['summary-resend'].disabled,false);
  assert.equal(ui.elements.summarize.disabled,true);assert.equal(ui.timers.size,1);
});

test('resend is isolated from a scope change while its response is pending',async()=>{
  const waiting=deferred();let posts=0;
  const ui=page(async(url,options)=>{
    if(url.includes('estimate'))return response(estimate);
    if(options){if(++posts===1)throw new TypeError('offline');return waiting.promise}
    return {ok:false,json:async()=>({code:'SUMMARY_SUBMISSION_NOT_FOUND',error:'not delivered'})};
  });
  await ui.elements.summarize.onclick();const resending=ui.elements['summary-resend'].onclick();
  ui.switchScope('project','b');ui.elements['summary-message'].textContent='Project B';
  await ui.elements['summary-resend'].onclick();assert.equal(posts,2);
  waiting.resolve(response(job));await resending;
  assert.equal(ui.elements['summary-message'].textContent,'Project B');
  assert.equal(ui.polls.filter(request=>request.options).length,2);
});

test('legacy pending IDs remain queryable but cannot resend an unknown payload',async()=>{
  const storage=new Map([['forge-summary-submission:'+JSON.stringify(['a','plan']),'legacy-id']]);
  const ui=page(async()=>({ok:false,json:async()=>({code:'SUMMARY_SUBMISSION_NOT_FOUND',error:'unknown'})}),true,storage);
  await vm.runInContext('loadSummaryJob()',ui.context);
  assert.match(ui.polls[0].url,/submission=legacy-id/);
  assert.equal(ui.elements['summary-resend'].hidden,true);assert.equal(ui.elements.summarize.disabled,true);
});

function startPolling(ui){
  vm.runInContext("summaryPollSequence=1;renderSummaryJob({jobId:'job-a',projectId:'a',skill:'plan',status:'RUNNING',sourceCount:2})",ui.context);
  return vm.runInContext("pollSummaryJob('job-a',1,'a','plan')",ui.context);
}

for(const failure of ['network','json','http'])test(`Summary polling recovers after ${failure} failure without reposting generation`,async()=>{
  let attempt=0;
  const ui=page(()=>{
    if(attempt++===0){
      if(failure==='network')return Promise.reject(new TypeError('Failed to fetch'));
      if(failure==='json')return Promise.resolve({ok:true,json:async()=>{throw new SyntaxError('Invalid JSON')}});
      return Promise.resolve({ok:false,json:async()=>({error:'service unavailable'})});
    }
    return Promise.resolve(response({...job,status:'SUCCEEDED',version:3}));
  });
  await startPolling(ui);
  assert.equal(ui.elements.summarize.disabled,true);assert.match(ui.elements['summary-message'].textContent,/retrying/);
  assert.equal(ui.timers.size,1);assert.equal([...ui.timers.values()][0].delay,3000);
  await ui.nextPoll();
  assert.equal(ui.timers.size,0);assert.equal(ui.elements.summarize.disabled,false);
  assert.match(ui.elements['summary-message'].textContent,/v3/);assert.equal(ui.summaryLoads(),1);
  assert.equal(ui.polls.length,2);assert.ok(ui.polls.every(request=>!request.options));
  assert.match(ui.polls[1].url,/job=job-a/);
});

test('repeated polling failures retain one retry timer and job identity',async()=>{
  const ui=page(()=>Promise.reject(new TypeError('offline')));await startPolling(ui);
  for(let index=0;index<3;index++){await ui.nextPoll();assert.equal(ui.timers.size,1)}
  assert.equal(ui.polls.length,4);assert.equal(ui.elements.summarize.disabled,true);
  assert.ok(ui.polls.every(request=>request.url.includes('job=job-a')&&!request.options));
});

for(const id of ['project','skill'])test(`old polling retry stops after ${id} changes away and back`,async()=>{
  const ui=page(()=>Promise.reject(new TypeError('offline')));await startPolling(ui);
  const original=ui.elements[id].value;ui.switchScope(id,id==='project'?'b':'debug');ui.switchScope(id,original);
  ui.elements['summary-message'].textContent='new scope';await ui.nextPoll();
  assert.equal(ui.polls.length,1);assert.equal(ui.timers.size,0);
  assert.equal(ui.elements['summary-message'].textContent,'new scope');
});

test('duplicate poll calls do not create overlapping requests or timers',async()=>{
  const waiting=deferred(),ui=page(()=>waiting.promise),first=startPolling(ui);
  await vm.runInContext("pollSummaryJob('job-a',1,'a','plan')",ui.context);
  assert.equal(ui.polls.length,1);
  waiting.resolve(response({...job,status:'RUNNING'}));await first;assert.equal(ui.timers.size,1);
  await vm.runInContext("pollSummaryJob('job-a',1,'a','plan')",ui.context);
  assert.equal(ui.timers.size,1);assert.equal(ui.polls.length,2);
});

for(const failure of ['network','json','http'])for(const existing of [true,false])test(`Summary discovery recovers from ${failure}, existing job=${existing}`,async()=>{
  let attempt=0;
  const ui=page(()=>{
    if(attempt++===0){
      if(failure==='network')return Promise.reject(new TypeError('offline'));
      if(failure==='json')return Promise.resolve({ok:true,json:async()=>{throw new SyntaxError('invalid JSON')}});
      return Promise.resolve({ok:false,json:async()=>({error:'busy'})});
    }
    return Promise.resolve(response({...job,status:'SUCCEEDED',version:4}));
  });
  if(existing)vm.runInContext("summaryPollSequence=1;renderSummaryJob({...job,status:'RUNNING'});scheduleSummaryPoll('job-a',1,'a','plan')",Object.assign(ui.context,{job}));
  await vm.runInContext('loadSummaryJob()',ui.context);
  assert.equal(ui.elements.summarize.disabled,true);assert.match(ui.elements['summary-message'].textContent,/retrying/);
  if(existing)assert.equal(vm.runInContext('currentSummaryJob.jobId',ui.context),'job-a');
  assert.equal(ui.timers.size,1);await ui.nextPoll();
  assert.equal(ui.timers.size,0);assert.equal(ui.elements.summarize.disabled,false);
  assert.match(ui.elements['summary-message'].textContent,/v4/);assert.equal(ui.polls.length,2);
  assert.ok(ui.polls.every(request=>!request.options&&!request.url.includes('job=')));
});

test('explicit missing-job status ends discovery without retrying',async()=>{
  const ui=page(()=>Promise.resolve({ok:false,status:404,json:async()=>({code:'SUMMARY_JOB_NOT_FOUND',error:'no job'})}));
  await vm.runInContext('loadSummaryJob()',ui.context);
  assert.equal(Boolean(ui.elements.summarize.disabled),false);assert.equal(ui.timers.size,0);
  assert.equal(vm.runInContext('currentSummaryJob',ui.context),null);
});

test('discovery retry cannot resume after changing project away and back',async()=>{
  const ui=page(()=>Promise.reject(new TypeError('offline')));await vm.runInContext('loadSummaryJob()',ui.context);
  ui.switchScope('project','b');ui.switchScope('project','a');ui.elements['summary-message'].textContent='new session';
  await ui.nextPoll();assert.equal(ui.polls.length,1);assert.equal(ui.timers.size,0);
  assert.equal(ui.elements['summary-message'].textContent,'new session');
});

test('retry response cannot overwrite a newly selected project', async () => {
  const waiting = deferred(), ui = page(() => waiting.promise);
  vm.runInContext("currentSummaryJob={jobId:'old-job',projectId:'a',skill:'plan',retryable:true,status:'FAILED'}", ui.context);
  const retrying = ui.elements['summary-retry'].onclick();
  ui.switchScope('project', 'b');
  ui.elements['summary-message'].textContent = 'Project B status';
  waiting.resolve(response(job));
  await retrying;
  assert.equal(ui.elements['summary-message'].textContent, 'Project B status');
  assert.equal(ui.polls.length, 1);
  assert.equal(JSON.parse(ui.polls[0].options.body).jobId, 'old-job');
});

// Execute the real list loaders; only their DOM rendering dependencies are stubbed.
function listPage() {
  const elements = {};
  const element = id => elements[id] ??= {value: '', innerHTML: '', textContent: '', selectedOptions: [{textContent: 'Project A'}]};
  element('project').value = 'a';element('skill').value = 'plan';
  const requests = [], jobs = [];
  let context;
  context = vm.createContext({
    $: element, URLSearchParams, esc: String, text: JSON.stringify, tr: key => key,
    fetch: url => {const waiting = deferred();requests.push({url, ...waiting});return waiting.promise;},
    syncProjectAction: () => {}, updateScope: () => {},
    render: () => {element('records').innerHTML = vm.runInContext('JSON.stringify(records)', context);},
    loadSummaryJob: async () => {jobs.push(element('project').value);},
  });
  const loader = html.slice(html.indexOf('let recordsLoadSequence='), html.indexOf('function card('));
  const summaries = html.slice(html.indexOf('async function loadSummaries()'), html.indexOf('\n</script>', html.indexOf('async function loadSummaries()')));
  vm.runInContext('let currentPage=1,records=[],projectItems=[];\n' + loader + summaries, context);
  function select(id, value) {
    if(id === 'page')vm.runInContext(`currentPage=${Number(value)}`, context);
    else element(id).value = value;
    element('project').selectedOptions = [{textContent: `Project ${element('project').value.toUpperCase()}`}];
  }
  return {element, select, requests, jobs, context, run: name => vm.runInContext(`${name}()`, context)};
}
const summaryRows = label => [{version: 1, lifecycle_status: 'DRAFT', source_count: 1, created_at: 'now', summary: {label}}];
const recordRows = label => ({
  projects: [{projectId: 'a', name: 'Project A', status: 'ACTIVE', databases: {plan: 'a', debug: 'a'}},
    {projectId: 'b', name: 'Project B', status: 'ACTIVE', databases: {plan: 'b', debug: 'b'}}],
  items: [{id: label}], total: 1, hasMore: false,
});
const flush = async () => {for(let index=0;index<6;index++)await Promise.resolve();};

for(const [id, value] of [['project', 'b'], ['skill', 'debug']]) {
  test(`real Summary loader rejects out-of-order responses after ${id} change`, async () => {
    const ui = listPage(), old = ui.run('loadSummaries');
    ui.select(id, value);
    const current = ui.run('loadSummaries');
    ui.requests[1].resolve(response(summaryRows('new-scope')));
    await current;
    const rendered = ui.element('summaries').innerHTML, scope = ui.element('summary-scope').textContent;
    ui.requests[0].resolve(response(summaryRows('old-scope')));
    await old;
    assert.equal(ui.element('summaries').innerHTML, rendered);
    assert.equal(ui.element('summary-scope').textContent, scope);
    assert.match(rendered, /new-scope/);
  });
}

for(const [id, value] of [['project', 'b'], ['skill', 'debug'], ['status', 'EXCLUDED'], ['q', 'new query'], ['page', 2]]) {
  test(`real records loader rejects out-of-order responses after ${id} change`, async () => {
    const ui = listPage(), old = ui.run('load');
    ui.select(id, value);
    const current = ui.run('load');
    ui.requests[1].resolve(response(recordRows('new-scope')));
    await flush();
    assert.equal(ui.requests.length, 3); // Only the current records request starts Summary loading.
    ui.requests[2].resolve(response(summaryRows('new-scope')));
    await current;
    const rendered = ui.element('records').innerHTML, options = ui.element('project').innerHTML;
    ui.requests[0].resolve(response(recordRows('old-scope')));
    await old;
    assert.equal(ui.element('records').innerHTML, rendered);
    assert.equal(ui.element('project').innerHTML, options);
    assert.match(rendered, /new-scope/);
    assert.equal(ui.requests.length, 3);
    assert.equal(ui.jobs.length, 1);
  });
}

test('real list loaders discard old A responses after switching A to B to A', async () => {
  const ui = listPage(), oldSummary = ui.run('loadSummaries'), oldRecords = ui.run('load');
  ui.select('project', 'b');
  const middle = ui.run('load');
  ui.select('project', 'a');
  const current = ui.run('load');
  // New records are still pending when the original A responses arrive.
  ui.element('records').innerHTML = 'current records';ui.element('summaries').innerHTML = 'current summary';
  ui.requests[0].resolve(response(summaryRows('old-a')));
  ui.requests[1].resolve(response(recordRows('old-a')));
  await Promise.all([oldSummary, oldRecords]);
  assert.equal(ui.element('records').innerHTML, 'current records');
  assert.equal(ui.element('summaries').innerHTML, 'current summary');
  ui.requests[2].resolve(response(recordRows('middle-b')));
  await middle;
  ui.requests[3].resolve(response(recordRows('latest-a')));
  await flush();
  ui.requests[4].resolve(response(summaryRows('latest-a')));
  await current;
  assert.match(ui.element('records').innerHTML, /latest-a/);
  assert.match(ui.element('summaries').innerHTML, /latest-a/);
});

for(const loader of ['load', 'loadSummaries']) {
  test(`stale ${loader} errors cannot overwrite the current message`, async () => {
    const ui = listPage(), old = ui.run(loader);
    ui.select('project', 'b');
    ui.element('message').textContent = 'Project B status';
    ui.requests[0].resolve({ok: false, json: async () => {throw new Error('old request error');}});
    await old;
    assert.equal(ui.element('message').textContent, 'Project B status');
  });
}

test('current list errors are still visible', async () => {
  const ui = listPage(), loading = ui.run('load');
  ui.requests[0].resolve({ok: false, json: async () => ({error: 'current request failed'})});
  await loading;
  assert.equal(ui.element('message').textContent, 'current request failed');
});

function managementPage(kind) {
  const source = readFileSync(new URL(`../../skills/learning-collector/assets/${kind}.html`, import.meta.url), 'utf8');
  const elements = Object.fromEntries(['project', 'skill', 'status', 'message'].map(id => [id, {value: '', innerHTML: '', textContent: ''}]));
  elements.project.value = 'a';elements.skill.value = 'plan';
  const requests = [], renders = [];
  let context;
  context = vm.createContext({
    $: id => elements[id], URLSearchParams, esc: String, tr: key => key,
    fetch: url => {const waiting=deferred();requests.push({url,...waiting});return waiting.promise;},
    show: message => {elements.message.textContent=message;},
    render: () => {renders.push(vm.runInContext(kind==='versions'?'JSON.stringify(values)':'JSON.stringify(allOverlays)',context));},
    populateFilters: () => {},
  });
  const start = source.indexOf(kind==='versions'?'let versionLoadSequence=':'let overlayLoadSequence=');
  const end = source.indexOf(kind==='versions'?'function metrics(':'function identity(',start);
  vm.runInContext("let projects=[],values=[],allOverlays=[];const initial=new URLSearchParams();\n"+source.slice(start,end),context);
  const run = () => vm.runInContext('load()',context);
  function complete(index, label, ok=true) {
    requests[index].resolve(response([{projectId:'a',name:'A'},{projectId:'b',name:'B'}]));
    requests[index+1].resolve({ok,json:async()=>ok?[{label,skill:elements.skill.value}]:{error:label}});
  }
  return {elements,requests,renders,run,complete,context,source};
}

for(const kind of ['versions','overlays']) {
  test(`${kind} management loader rejects late A after B`,async()=>{
    const ui=managementPage(kind),old=ui.run();
    ui.elements.project.value='b';const current=ui.run();
    ui.complete(2,'new-b');await current;
    ui.complete(0,'old-a');await old;
    assert.equal(ui.elements.project.value,'b');
    assert.equal(ui.renders.length,1);assert.match(ui.renders[0],/new-b/);
  });
  test(`${kind} management loader rejects original A after A-B-A`,async()=>{
    const ui=managementPage(kind),old=ui.run();
    ui.elements.project.value='b';const middle=ui.run();
    ui.elements.project.value='a';const current=ui.run();
    ui.complete(4,'latest-a');await current;
    ui.complete(0,'old-a');ui.complete(2,'middle-b');await Promise.all([old,middle]);
    assert.equal(ui.renders.length,1);assert.match(ui.renders[0],/latest-a/);
  });
  test(`${kind} management loader ignores stale failure`,async()=>{
    const ui=managementPage(kind),old=ui.run();
    ui.elements.project.value='b';const current=ui.run();
    ui.complete(2,'new-b');await current;
    ui.elements.message.textContent='current status';ui.complete(0,'stale error',false);await old;
    assert.equal(ui.elements.message.textContent,'current status');
  });
}

test('Summary management loader isolates Skill changes',async()=>{
  const ui=managementPage('versions'),old=ui.run();
  ui.elements.skill.value='debug';const current=ui.run();
  ui.complete(2,'debug');await current;ui.complete(0,'old-plan');await old;
  assert.equal(ui.elements.skill.value,'debug');assert.equal(ui.renders.length,1);
});

function overlayActionPage(realRenderer=false){
  const source=readFileSync(new URL('../../skills/learning-collector/assets/overlays.html',import.meta.url),'utf8');
  const elements=Object.fromEntries(['project','skill','status','message','overlays','refresh','stats'].map(id=>[id,{value:'',textContent:'',className:''}]));
  elements.project.value='a';elements.skill.value='plan';
  let click;
  let cards=[];
  elements.overlays.querySelectorAll=()=>cards;
  Object.defineProperty(elements.overlays,'innerHTML',{set(markup){
    cards=[...markup.matchAll(/<article[^>]*data-overlay-id="([^"]+)"[^>]*data-project="([^"]+)"[^>]*data-skill="([^"]+)"[^>]*>([\s\S]*?)<\/article>/g)].map(match=>{
      const card={dataset:{overlayId:match[1],project:match[2],skill:match[3],hasEvaluation:'false'}};
      const buttons=[...match[4].matchAll(/<button\b([^>]*)>/g)].map(tag=>({dataset:{action:tag[1].match(/data-action="([^"]+)"/)[1]},disabled:/\bdisabled\b/.test(tag[1]),closest:()=>card}));
      card.querySelectorAll=()=>buttons;card.querySelector=()=>({value:'content'});card.buttons=buttons;return card;
    });
  }});
  elements.overlays.addEventListener=(_event,handler)=>{click=handler};
  const requests=[],loads=[],rendered=[],context=vm.createContext({$:id=>elements[id],URLSearchParams,confirm:()=>true,loads,requests,
    tr:(key,values)=>values?`${key}:${JSON.stringify(values)}`:key,
    fetch:(url,options)=>{const waiting=deferred();requests.push({url,options,...waiting});return waiting.promise;},
    history:{replaceState:()=>{}},esc:String,
    populateFilters:()=>{},render:()=>{rendered.push(vm.runInContext('JSON.stringify(allOverlays)',context));elements.message.textContent='current list';elements.message.className='message sub';},
  });
  vm.runInContext('let projects=[],allOverlays=[];const initial=new URLSearchParams();\n'+source.slice(source.indexOf('const pendingOverlayOperations='),source.indexOf('function render('))+source.slice(source.indexOf('let overlayLoadSequence='),source.indexOf('async function loadLlm(')),context);
  if(realRenderer)vm.runInContext(source.slice(source.indexOf('function displayState('),source.indexOf('const pendingOverlayOperations='))+source.slice(source.indexOf('function render('),source.indexOf('let overlayLoadSequence=')),context);
  const handlers=source.slice(source.lastIndexOf("$('project').onchange="),source.indexOf('\n</script>',source.lastIndexOf("$('project').onchange=")));
  vm.runInContext(handlers.slice(0,handlers.indexOf("$('llm-save').onclick=")),context);
  vm.runInContext('const realLoad=load;load=(options)=>{const index=requests.length,promise=realLoad(options);loads.push({index,promise});return promise}',context);
  function action(name='copy',id='overlay-a'){
    const card=cards.find(item=>item.dataset.overlayId===id)||{dataset:{overlayId:id,project:'a',skill:'plan',hasEvaluation:'false'},querySelector:()=>({value:'content'})};
    const button=card.buttons?.find(item=>item.dataset.action===name)||{dataset:{action:name},disabled:false,closest:()=>card};
    return {button,done:click({target:{closest:()=>button}})};
  }
  function select(id,value){elements[id].value=value;elements[id].onchange()}
  async function refresh(index,ok=true,rows=[]){
    requests[index].resolve(response([{projectId:elements.project.value}]));
    requests[index+1].resolve(ok?response(rows):{ok:false,json:async()=>({error:'refresh failed'})});
    await loads.find(item=>item.index===index).promise;
  }
  return {elements,requests,action,select,refresh,rendered,card:id=>cards.find(item=>item.dataset.overlayId===id),run:code=>vm.runInContext(code,context)};
}

const overlayRow=(id,ready=true)=>({id,project_id:'a',skill:'plan',status:'REVIEWED',version:1,sourceSummaryIds:['s'],content:'original',manifest:{origin:{type:'SUMMARY_GENERATED'}},evaluationReadiness:{ready}});
test('actual Overlay card rendering retains pending state after independent copy refresh',async()=>{
  const ui=overlayActionPage(true),evaluation=ui.action('evaluate','one'),copy=ui.action('copy','two');
  ui.requests[1].resolve(response({version:2}));await flush();await ui.refresh(2,true,[overlayRow('one'),overlayRow('other',false)]);await copy.done;
  assert.ok(ui.card('one').buttons.every(button=>button.disabled));
  assert.equal(ui.card('other').buttons.find(button=>button.dataset.action==='copy').disabled,false);
  await ui.action('evaluate','one').done;assert.equal(ui.requests.length,4);
  // Even a stale/new DOM button that is incorrectly enabled cannot bypass the identity guard.
  ui.card('one').buttons.find(button=>button.dataset.action==='evaluate').disabled=false;
  await ui.action('evaluate','one').done;assert.equal(ui.requests.length,4);
  ui.requests[0].resolve({ok:false,json:async()=>({error:'evaluation failed'})});await flush();
  await ui.refresh(4,true,[overlayRow('one'),overlayRow('other',false)]);await evaluation.done;
  assert.equal(ui.card('one').buttons.find(button=>button.dataset.action==='evaluate').disabled,false);
  assert.equal(ui.card('other').buttons.find(button=>button.dataset.action==='evaluate').disabled,true);
});

test('pending Overlay state survives actual filter and manual refresh rendering',async()=>{
  const ui=overlayActionPage(true),evaluation=ui.action('evaluate','one');
  ui.elements.refresh.onclick();await ui.refresh(1,true,[overlayRow('one')]);
  ui.select('status','DRAFT');ui.select('status','');
  assert.ok(ui.card('one').buttons.every(button=>button.disabled));
  await ui.action('evaluate','one').done;assert.equal(ui.requests.length,3);
  ui.requests[0].resolve({ok:false,json:async()=>({error:'old failure'})});await evaluation.done;
  assert.equal(ui.card('one').buttons.find(button=>button.dataset.action==='evaluate').disabled,false);
});

for(const order of [[0,1],[1,0]])test(`independent Overlay mutations both refresh in completion order ${order}`,async()=>{
  const ui=overlayActionPage(),operations=[ui.action('review','one'),ui.action('copy','two')];
  const first=order[0],last=order[1];
  ui.requests[first].resolve(response({version:2}));await flush();
  await ui.refresh(2,true,[{id:'one',status:first===0?'REVIEWED':'DRAFT'}]);await operations[first].done;
  const latestMessage=ui.elements.message.textContent;
  ui.requests[last].resolve(response({version:2}));await flush();
  assert.equal(ui.requests.length,6);
  await ui.refresh(4,true,[{id:'one',status:'REVIEWED'},{id:'two',status:'DRAFT'}]);await operations[last].done;
  assert.match(ui.rendered.at(-1),/REVIEWED/);
  if(last===0)assert.equal(ui.elements.message.textContent,latestMessage);
  else assert.match(ui.elements.message.textContent,/overlayCopied/);
  assert.equal(operations[0].button.disabled,false);assert.equal(operations[1].button.disabled,false);
});

for(const action of ['copy','review','activate','disable','delete','evaluate']){
  test(`Overlay ${action} retains normal success after refreshing`,async()=>{
    const ui=overlayActionPage(),operation=ui.action(action);
    assert.equal(operation.button.disabled,true);
    ui.requests[0].resolve(response({version:2}));await flush();
    assert.equal(ui.requests.length,3);await ui.refresh(1);await operation.done;
    assert.match(ui.elements.message.textContent,action==='evaluate'?/evaluationPublished/:/overlay/);
    assert.equal(ui.elements.message.className,'message sub');assert.equal(operation.button.disabled,false);
  });
}

for(const action of ['copy','evaluate'])for(const ok of [true,false]){
  test(`late ${action} ${ok?'success':'error'} cannot affect another project`,async()=>{
    const ui=overlayActionPage(),operation=ui.action(action);
    ui.select('project','b');await ui.refresh(1);
    ui.elements.message.textContent='Project B status';
    ui.requests[0].resolve({ok,json:async()=>ok?{version:2}:{error:'old failure'}});await operation.done;
    assert.equal(ui.elements.message.textContent,'Project B status');assert.equal(ui.requests.length,3);
    assert.equal(operation.button.disabled,false);
  });
  test(`late ${action} ${ok?'success':'error'} is discarded after A-B-A`,async()=>{
    const ui=overlayActionPage(),operation=ui.action(action);
    ui.select('project','b');ui.select('project','a');ui.select('skill','plan');
    await ui.refresh(3);await ui.refresh(1);
    ui.elements.message.textContent='new A status';
    ui.requests[0].resolve({ok,json:async()=>ok?{version:2}:{error:'old failure'}});await operation.done;
    assert.equal(ui.elements.message.textContent,'new A status');assert.equal(ui.requests.length,5);
  });
}

for(const action of ['copy','evaluate']){
  test(`${action} success does not hide a failed list refresh`,async()=>{
    const ui=overlayActionPage(),operation=ui.action(action);
    ui.requests[0].resolve(response({version:2}));await flush();await ui.refresh(1,false);await operation.done;
    assert.equal(ui.elements.message.textContent,'refresh failed');assert.equal(ui.elements.message.className,'message error');
    assert.equal(operation.button.disabled,false);
  });
  test(`${action} cannot overwrite a project switch during its refresh`,async()=>{
    const ui=overlayActionPage(),operation=ui.action(action);
    ui.requests[0].resolve(response({version:2}));await flush();
    ui.select('project','b');await ui.refresh(3);
    ui.elements.message.textContent='Project B status';await ui.refresh(1);await operation.done;
    assert.equal(ui.elements.message.textContent,'Project B status');
  });
}

for(const id of ['skill','status'])test(`Overlay operation is discarded after ${id} changes away and back`,async()=>{
  const ui=overlayActionPage(),operation=ui.action(),original=ui.elements[id].value;
  ui.select(id,id==='skill'?'debug':'DRAFT');ui.select(id,original);
  ui.elements.message.textContent='new filter status';ui.requests[0].resolve(response({version:2}));await operation.done;
  assert.equal(ui.elements.message.textContent,'new filter status');assert.equal(ui.requests.length,1);
});

test('manual refresh supersedes a pending Overlay operation',async()=>{
  const ui=overlayActionPage(),operation=ui.action();ui.elements.refresh.onclick();await ui.refresh(1);
  ui.elements.message.textContent='manual refresh status';ui.requests[0].resolve(response({version:2}));await operation.done;
  assert.equal(ui.elements.message.textContent,'manual refresh status');assert.equal(ui.requests.length,3);
});

test('evaluation rejection refreshes its evidence and shows the failed gates',async()=>{
  const ui=overlayActionPage(),operation=ui.action('evaluate');
  ui.requests[0].resolve({ok:false,json:async()=>({evaluation:{behavior:{gates:[{id:'quality',passed:false}]}}})});
  await flush();await ui.refresh(1);await operation.done;
  assert.match(ui.elements.message.textContent,/evaluationRejected.*quality/);assert.equal(ui.elements.message.className,'message error');
});

test('published Overlay recovery explanation appears on the card',()=>{
  const ui=managementPage('overlays');
  const start=ui.source.indexOf('function evaluationMeta('),end=ui.source.indexOf('function overlayCard(',start);
  vm.runInContext(ui.source.slice(start,end),ui.context);
  assert.match(vm.runInContext("evaluationMeta({published_at:'now',evaluation:{behavior:{gates:[]}}})",ui.context),/publishedRecoveryHint/);
  assert.doesNotMatch(vm.runInContext("evaluationMeta({evaluation:{behavior:{gates:[]}}})",ui.context),/publishedRecoveryHint/);
});

test('Summary decisions render conflicts, phases, reasons and all source IDs safely',()=>{
  const source=readFileSync(new URL('../../skills/learning-collector/assets/versions.html',import.meta.url),'utf8');
  const context=vm.createContext({window:{ForgeI18n:{language:'en'}},esc:value=>String(value??'').replaceAll('<','&lt;').replaceAll('>','&gt;')});
  vm.runInContext(source.slice(source.indexOf('function decisionPanel('),source.indexOf('function versionCard(')),context);
  const result=vm.runInContext("decisionRows([{phase:'REDUCE',level:1,inputId:'candidate',decision:'CONFLICT',reason:'<unsafe>',sourceRecordIds:['r1','r2']}])",context);
  assert.match(result,/Conflict/);assert.match(result,/REDUCE 1/);
  assert.match(result,/&lt;unsafe&gt;/);assert.match(result,/r1, r2/);
  assert.match(vm.runInContext("decisionPanel({format:'forge-skill-training-summary-v6',candidateDecisions:[],rules:[]})",context),/data-decisions/);
});

function evidencePage(){
  const source=readFileSync(new URL('../../skills/learning-collector/assets/versions.html',import.meta.url),'utf8');
  let button=null;
  const requests=[],container={innerHTML:'',textContent:'',querySelector:()=>button,
    insertAdjacentHTML:(_position,rows)=>{
      container.innerHTML+=rows;
      if(rows.includes('data-evidence-more'))button={disabled:false,textContent:'more',remove:()=>{button=null}};
    },
  };
  const details={open:true,dataset:{},closest:()=>({dataset:{project:'p',skill:'plan',version:'1'}}),querySelector:()=>container};
  const context=vm.createContext({window:{ForgeI18n:{language:'en'}},esc:String,text:JSON.stringify,URLSearchParams,
    fetch:url=>{const waiting=deferred();requests.push({url,...waiting});return waiting.promise;},
  });
  vm.runInContext(source.slice(source.indexOf('function evidenceRows('),source.indexOf(' async function loadLlm(')),context);
  context.details=details;
  return {details,container,requests,button:()=>button,load:page=>vm.runInContext(`loadEvidence(details,${page})`,context)};
}
const evidenceResult=(page,id,hasMore)=>response({records:[{recordId:id,effectiveContent:'evidence'}],page,pageSize:20,total:21,hasMore});

test('evidence pagination prevents concurrent and already rendered page requests',async()=>{
  const ui=evidencePage(),first=ui.load(1);
  await ui.load(1);assert.equal(ui.requests.length,1);
  ui.requests[0].resolve(evidenceResult(1,'record-one',true));await first;
  const more=ui.button(),second=more.onclick();
  assert.equal(more.disabled,true);
  await more.onclick();assert.equal(ui.requests.length,2);
  ui.details.open=false;await ui.load(1);
  ui.details.open=true;await ui.load(1);assert.equal(ui.requests.length,2);
  ui.requests[1].resolve(evidenceResult(2,'record-two',false));await second;
  await ui.load(2);assert.equal(ui.requests.length,2);
  assert.equal(ui.container.innerHTML.split('record-two').length-1,1);
  assert.match(ui.container.innerHTML,/record-one/);assert.equal(ui.button(),null);
  await ui.load(1);assert.equal(ui.requests.length,2);
});

test('later evidence failure retains rows and retries the same page',async()=>{
  const ui=evidencePage(),first=ui.load(1);
  ui.requests[0].resolve(evidenceResult(1,'record-one',true));await first;
  const original=ui.container.innerHTML,more=ui.button(),failed=more.onclick();
  ui.requests[1].resolve({ok:false,json:async()=>({error:'temporary failure'})});await failed;
  assert.equal(ui.container.innerHTML,original);assert.equal(ui.container.textContent,'');
  assert.equal(more.disabled,false);assert.match(more.textContent,/temporary failure.*Retry/);
  assert.equal(ui.details.dataset.evidencePage,'1');
  ui.details.open=false;await ui.load(1);ui.details.open=true;await ui.load(1);
  assert.equal(ui.requests.length,2);
  const retry=more.onclick();assert.match(ui.requests[2].url,/page=2/);
  ui.requests[2].resolve(evidenceResult(2,'record-two',false));await retry;
  assert.match(ui.container.innerHTML,/record-one/);assert.match(ui.container.innerHTML,/record-two/);
  assert.equal(ui.button(),null);assert.equal(ui.details.dataset.loading,undefined);
});

test('first evidence failure can be retried by reopening the panel',async()=>{
  const ui=evidencePage(),failed=ui.load(1);
  ui.requests[0].resolve({ok:false,json:async()=>({error:'first page failed'})});await failed;
  assert.equal(ui.container.textContent,'first page failed');
  assert.equal(ui.details.dataset.loaded,undefined);assert.equal(ui.details.dataset.loading,undefined);
  ui.details.open=false;await ui.load(1);assert.equal(ui.requests.length,1);
  ui.details.open=true;const retry=ui.load(1);
  assert.match(ui.requests[1].url,/page=1/);
  ui.requests[1].resolve(evidenceResult(1,'recovered',false));await retry;
  assert.match(ui.container.innerHTML,/recovered/);assert.equal(ui.details.dataset.evidencePage,'1');
});

test('Summary decision loader paginates and retries failures without losing existing rows',async()=>{
  const source=readFileSync(new URL('../../skills/learning-collector/assets/versions.html',import.meta.url),'utf8');
  let button=null,requests=[],container={innerHTML:'',textContent:'',
    querySelector:()=>button,
    insertAdjacentHTML:(_position,rows)=>{
      container.innerHTML+=rows;
      if(rows.includes('data-decisions-more'))button={textContent:'more',remove:()=>{button=null}};
    },
  };
  const details={open:true,dataset:{},closest:()=>({dataset:{project:'p',skill:'plan',version:'1'}}),querySelector:()=>container};
  const context=vm.createContext({window:{ForgeI18n:{language:'en'}},esc:String,URLSearchParams,
    fetch:url=>{let waiting=deferred();requests.push({url,...waiting});return waiting.promise;},
  });
  vm.runInContext(source.slice(source.indexOf('function decisionRows('),source.indexOf('function versionCard(')),context);
  context.details=details;
  const first=vm.runInContext('loadDecisions(details)',context);
  await vm.runInContext('loadDecisions(details)',context); // duplicate toggle while loading
  assert.equal(requests.length,1);
  requests[0].resolve(response({decisions:[{phase:'MAP',decision:'CONFLICT',reason:'contradiction',sourceRecordIds:['r1']}],hasMore:true,page:1,pageSize:20,total:21}));
  await first;
  const original=container.innerHTML;
  const failed=button.onclick();requests[1].resolve({ok:false,json:async()=>({error:'temporary failure'})});await failed;
  assert.equal(container.innerHTML,original);assert.equal(button.textContent,'temporary failure');
  const retry=button.onclick();requests[2].resolve(response({decisions:[{phase:'FINAL',decision:'DISCARD',reason:'too specific',sourceRecordIds:['r2']}],hasMore:false,page:2,pageSize:20,total:21}));await retry;
  assert.match(container.innerHTML,/contradiction/);assert.match(container.innerHTML,/too specific/);
  assert.equal(button,null);
  assert.match(requests[2].url,/page=2/);
});
