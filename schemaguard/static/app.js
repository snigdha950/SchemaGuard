'use strict';
const $ = id => document.getElementById(id);
const svgns='http://www.w3.org/2000/svg';
function node(tag,cls,text){const e=document.createElement(tag); if(cls)e.className=cls; if(text!==undefined)e.textContent=String(text); return e;}
function svgNode(tag,attrs,txt){const e=document.createElementNS(svgns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));if(txt!==undefined)e.textContent=String(txt);return e;}
function empty(id){$(id).replaceChildren();}
function setState(type,title,message){const s=$('state');s.className='notice '+type; s.replaceChildren(node('span','notice-dot'));const d=node('div');d.append(node('strong','',title),node('p','',message));s.append(d);}
function busy(flag){['run','replay','reset','challenge','compare','repro'].forEach(id=>$(id).disabled=flag)}
let latestInvestigationId=null;
async function request(path,method='GET',payload=null){const res=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:payload?JSON.stringify(payload):undefined});const data=await res.json();if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:`HTTP ${res.status}`);return data;}
function badgeText(s){return s==='verified'?'VERIFIED':s==='unsafe'?'UNSAFE':'INCOMPLETE'}
function renderGraph(context){
 const graph=context.graph; empty('graphArea');const nodes=graph.nodes,edges=graph.edges;
 const layer={deployment:0,consumer:1,query:2,column:3};const cols=['deployment','consumer','query','column'];
 const grouped=Object.fromEntries(cols.map(k=>[k,nodes.filter(n=>n.type===k).sort((a,b)=>a.label.localeCompare(b.label))]));
 const count=Math.max(...cols.map(k=>grouped[k].length),1),height=Math.max(480,100+count*113),width=1060;
 const svg=svgNode('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'FalkorDB graph of deployments, consumers, queries, and columns'});
 const pos={};cols.forEach((name,i)=>{const arr=grouped[name];arr.forEach((n,j)=>{pos[n.id]={x:68+i*258,y:88+(j+1)*((height-120)/(arr.length+1))};});
 svg.append(svgNode('text',{x:68+i*258,y:43,fill:'#8faab8','font-size':13,'font-weight':700},name.toUpperCase()));});
 edges.forEach(e=>{const a=pos[e.source],b=pos[e.target];if(!a||!b)return;const color=e.affected?'#7befba':'#324656';const path=svgNode('path',{d:`M ${a.x+78} ${a.y} C ${a.x+156} ${a.y}, ${b.x-110} ${b.y}, ${b.x-30} ${b.y}`,stroke:color,'stroke-width':e.affected?3.5:1.35,fill:'none','stroke-opacity':e.affected?1:.65});svg.append(path);});
 nodes.forEach(n=>{const p=pos[n.id];if(!p)return;const x=p.x-48,y=p.y-22;const active=n.active!==false;const fill=n.type==='column'&&n.affected?'#24473c':n.affected?'#1c3c36':'#1c2b39';const stroke=n.affected?'#61b998':'#365166';
 svg.append(svgNode('rect',{x,y,width:160,height:44,rx:9,fill,stroke,'stroke-width':n.affected?2:1,opacity:active?1:.43}));const short=n.label.length>20?n.label.slice(0,19)+'…':n.label;
 svg.append(svgNode('text',{x:x+10,y:y+26,fill:active?'#e4f0f2':'#8396a4','font-size':12,'font-family':'system-ui, sans-serif'},short));});
 $('graphArea').append(svg);
}
function renderContext(context){renderGraph(context); $('depCount').textContent=context.coverage.read_edges;$('affectedCount').textContent=context.affected.length;$('version').textContent=context.fixture_version;empty('consumers');
 const affectedById=new Map(context.affected.map(c=>[c.consumer,c]));
 if(!context.active_consumers?.length)$('consumers').append(node('div','placeholder','No active deployed consumers in graph. Check observation coverage.'));
 for(const item of (context.active_consumers||[])){
  const c=affectedById.get(item.consumer);const d=node('div','consumer-item'+(c?' affected':''));const header=node('div','name');
  header.append(node('span','',item.consumer),node('small','',c?'AFFECTED':'NOT READING TARGET'));
  d.append(header,node('div','meta',`${item.kind} · tested version ${item.version} · ${item.environment}`),
   node('div','path',`${item.deployment} → ${item.consumer} → ${item.query}${c?' → '+context.target:''}`),
   node('div','meta',`${c?.source||'Probe: sqlite.authorizer'} · ${c?.observation||item.probe_observation||'NO EVIDENCE'}`));
  $('consumers').append(d);
 }
 $('coverage').textContent=context.coverage.issues.length?context.coverage.issues.join('; '):`${context.coverage.probed_consumers.length} active consumers have passing configuration-bound SQL authorizer probes.`;}
function renderAttempts(attempts){empty('attempts');
 attempts.forEach((a,i)=>{const card=node('article','attempt '+(a.verified?'verified':'unsafe'));const title=node('h3','',`${i+1}. ${a.name||('Agent attempt '+(i+1))} · ${badgeText(a.status)}`);card.append(title,node('div','subtitle',`${a.scope||'llm-selected plan'} · SQLite ${a.duration_ms} ms · fixture ${a.fixture_version}`));
 const ordered=node('ol');if(a.actions.length===0){ordered.append(node('li','','No actions tested'));}for(const step of a.actions){ordered.append(node('li','',step.type==='drop_column'?`ALTER TABLE ${step.target.replace('.',' DROP COLUMN ')}`:`Update ${step.consumer_id} SELECT projection: remove ${step.remove_column}`));}card.append(ordered);
 if(a.scope==='baseline' && i===0 && a.latest_only_would_pass){card.append(node('div','pass','LATEST-VERSION-ONLY GATE: PASS (false negative)'));}
 const kept=(a.checks||[]).filter(x=>x.check?.startsWith('output:')&&x.passed).map(x=>x.check.slice(7));
 card.append(node('div','preserved','Preserved required outputs: '+(kept.join(', ')||'none confirmed')));
 const errors=a.affected_sql_failures||[];card.append(node('div',errors.length?'problem':'pass',errors.length?`SQL FAILED: ${errors.join(', ')}`:a.verified?'All required outputs and retained records preserved.':'No consumer SQL errors; review incomplete schema/contract checks.'));
 if(a.unresolved_required_outputs?.length){card.append(node('div','problem','UNRESOLVED REQUIRED OUTPUT: '+a.unresolved_required_outputs.join(', ')));}
 if(errors.length){const failing=errors.map(id=>a.after?.[id]?.error).filter(Boolean);card.append(node('div','problem',failing.join(' | ')));}
 const details=node('details');details.append(node('summary','','Show actual before/after checks and SQL'),node('pre','',JSON.stringify({checks:a.checks,step_checks:a.step_checks,baseline:a.baseline,after:a.after,sql_errors:a.sql_errors},null,2)));card.append(details);$('attempts').append(card);});
}
function renderActivity(events,rec){empty('activity');for(const event of events){const box=node('div','event');box.append(node('strong','',`${event.ok===false?'✗':'→'} ${event.tool} [step ${event.step}]`));const details=node('details');details.append(node('summary','','Show actual tool arguments and result'),node('pre','',JSON.stringify({input:event.input,result:event.result},null,2)));box.append(details);$('activity').append(box);}empty('recommendation');if(rec){$('recommendation').append(node('strong','',rec.verified?'Verifier-approved recommendation':'Unverified / unsafe recommendation'),node('p','',rec.text),node('p','',`Linked to ${rec.attempt_id} · ${rec.status}`));}}
function clearGraphForBlocker(message){empty('graphArea');$('graphArea').append(node('div','placeholder',message));empty('consumers');$('depCount').textContent='—';$('affectedCount').textContent='—';$('coverage').textContent='No verified current graph evidence.';}
async function refreshSummary(){
 try{
  const data=await request('/api/summary?target='+encodeURIComponent($('target').value));
  $('sqlPassedCount').textContent=data.sql_reference_plans_passed;
  const cases=data.reference_results;
  const bad=cases.filter(c=>c.failed_consumers.length).map(c=>`${c.name}: ${c.failed_consumers.join(', ')}`);
  const success=cases.filter(c=>c.verified).map(c=>c.name);
  $('resultSummary').textContent=`SQL reference, ${cases.length} executed plans: ${bad.join(' | ')||'no failing consumers'}; passed: ${success.join(', ')||'none'}. This is not an agent result.`;
 }catch(e){$('resultSummary').textContent='SQLite summary unavailable: '+e.message;$('sqlPassedCount').textContent='—';}
}
async function refreshAgentCount(){
 try{const data=await request('/api/history?target='+encodeURIComponent($('target').value));$('agentVerifiedCount').textContent=data.agent_verified_recommendations;}
 catch(_){$('agentVerifiedCount').textContent='—';}
}
async function refreshHealth(){
 try{
  const data=await request('/api/health');
  const connected=data.falkordb.startsWith('connected');
  $('connection').className='status-pill '+(connected?'good':'bad');
  $('connection').textContent='Graph: '+data.falkordb;
  const configured=data.model==='key_configured_not_tested';
  $('modelStatus').className='status-pill '+(configured?'checking':'bad');
  $('modelStatus').textContent='Model: '+(configured?'key present, untested':'key missing');
  if(connected){try{const ctx=await request('/api/graph?target='+encodeURIComponent($('target').value));renderContext(ctx);if(ctx.state!=='complete')setState('blocked','Graph evidence incomplete',ctx.coverage.issues.join('; '));await refreshAgentCount();}
      catch(err){clearGraphForBlocker(err.message);setState('blocked','Graph evidence incomplete',err.message);}}
  else {clearGraphForBlocker('FalkorDB unavailable. Start Docker, seed graph, and reload. No graph is fabricated.');$('agentVerifiedCount').textContent='—';}
 }catch(e){$('connection').className='status-pill bad';$('connection').textContent='Graph: backend unavailable';clearGraphForBlocker(e.message);}
}
$('target').addEventListener('change',async()=>{empty('attempts');empty('activity');empty('recommendation');$('agentStatus').textContent='Agent: not run';try{const ctx=await request('/api/graph?target='+encodeURIComponent($('target').value));renderContext(ctx);if(ctx.state!=='complete')setState('blocked','Graph evidence incomplete',ctx.coverage.issues.join('; '));}catch(e){clearGraphForBlocker(e.message);setState('blocked','Graph context unavailable',e.message);}await refreshSummary();await refreshAgentCount();});
$('replay').addEventListener('click',async()=>{busy(true);setState('idle','Running disposable SQLite copies','These reference plans are controlled deterministic diagnostics, not an agent.');try{const data=await request('/api/demo/sql','POST',{target:$('target').value});renderAttempts(data.scenarios);await refreshSummary();$('sqlMode').textContent='OFFLINE SQL BASELINES';$('version').textContent=data.fixture_version;const status=data.scenarios.at(-1)?.verified?'verified':'unsafe';setState(status,'SQLite reference comparison complete',`${data.scenarios.length} real SQL attempts in fresh databases. These results do not imply FalkorDB connectivity or a working LLM.`);}catch(e){setState('blocked','Replay failed',e.message);}finally{busy(false)}});
$('run').addEventListener('click',async()=>{busy(true);setState('idle','Investigating graph-backed change','Querying real FalkorDB and invoking bounded LLM tools.');try{const data=await request('/api/investigate','POST',{target:$('target').value});renderContext(data.context);renderAttempts(data.attempts);renderActivity(data.activity,data.recommendation);latestInvestigationId=data.recommendation?.verified?data.investigation_id:null;$('receipt').disabled=!latestInvestigationId;$('agentStatus').className='status-pill '+(data.status==='verified'?'good':'bad');$('agentStatus').textContent='Agent: '+data.status;await refreshAgentCount();$('sqlMode').textContent='AGENT-SELECTED TESTS';setState(data.status,data.status==='verified'?'Verified change sequence':data.status==='unsafe'?'Unsafe change sequence':data.status==='unresolved'?'Unresolved required-output contract':'Investigation incomplete',data.recommendation?.text||data.limitation||'Verifier did not establish a safe plan.');}catch(e){$('agentStatus').className='status-pill bad';$('agentStatus').textContent='Agent: blocked';setState('blocked','Investigation blocked',e.message);}finally{busy(false)}});
$('reset').addEventListener('click',async()=>{if(!confirm('Restore only SchemaGuard synthetic fixture and reseed only schemaguard_* FalkorDB graph?'))return;busy(true);try{const v=await request('/api/reset','POST');$('target').value='users.legacy_status';latestInvestigationId=null;$('receipt').disabled=true;empty('attempts');empty('activity');empty('recommendation');$('agentStatus').textContent='Agent: not run';renderContext(await request('/api/graph'));await refreshSummary();await refreshAgentCount();setState('verified','Demo reset complete',`FalkorDB reseeded from SQLite authorizer observations at version ${v.fixture_version}.`);}catch(e){setState('blocked','Reset incomplete',e.message);}finally{busy(false)}});
refreshSummary();refreshHealth();

$('compare').addEventListener('click',async()=>{busy(true);try{const c=await request('/api/compare?target='+encodeURIComponent($('target').value));const best=c.smallest_passing_plan;$('comparisonResult').className='meta-short '+(best?'ok':'problem');$('comparisonResult').textContent=best?`${c.candidates_tested} SQL plans tested; smallest passing plan: ${c.minimum_operations} operations within bounded action subsets.`:`${c.candidates_tested} tested; no passing repair within bounded actions.`;setState(best?'verified':'unresolved','Deterministic bounded SQL comparison (NOT AGENT)',c.limitation);}catch(e){setState('blocked','Comparison failed',e.message)}finally{busy(false)}});
$('repro').addEventListener('click',async()=>{busy(true);try{const target=$('target').value;const response=await fetch('/api/reproduction',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target,actions:[{type:'drop_column',target}]})});if(!response.ok){const d=await response.json();throw new Error(d.detail||'Unable to reproduce')}const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='schemaguard-sql-reproduction.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),12000);setState('unsafe','Captured baseline SQL failure','ZIP includes independently runnable repro.py, exact SQL, fixture, expected outputs and observed failure.');}catch(e){setState('blocked','Reproduction unavailable',e.message)}finally{busy(false)}});
$('challenge').addEventListener('click',async()=>{busy(true);try{const name=$('challengeName').value.trim();if(!name)throw new Error('Enter a new unique worker ID');const old=latestInvestigationId;const result=await request('/api/challenge','POST',{consumer_id:name,reads_target:$('challengeReads').checked,required_target:$('challengeRequires').checked,active:true});renderContext(await request('/api/graph'));await refreshSummary();await refreshAgentCount();empty('attempts');empty('activity');empty('recommendation');if(old){latestInvestigationId=old;$('receipt').disabled=false;$('receiptState').textContent='Configuration changed. Recheck the old receipt.';}setState('verified','Judge challenge reobserved',`Added ${name}; new fixture ${result.fixture_version}. Run agent to investigate changed dependencies.`);}catch(e){setState('blocked','Challenge not committed',e.message)}finally{busy(false)}});
$('receipt').addEventListener('click',async()=>{if(!latestInvestigationId)return;try{const r=await request('/api/receipt/'+encodeURIComponent(latestInvestigationId));$('receiptState').className='meta-short '+(r.fresh_verified?'ok':'problem');$('receiptState').textContent=r.fresh_verified?'CURRENT VERIFIED':'STALE/NOT VERIFIED: '+r.freshness_reasons.join('; ');setState(r.fresh_verified?'verified':'blocked','Current receipt validation',r.fresh_verified?'Persisted graph evidence and verifier still match.':'Previous status withdrawn until fresh verification.');const blob=new Blob([JSON.stringify(r,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='schemaguard-verification-receipt.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),12000);}catch(e){setState('blocked','Receipt unavailable',e.message)}});
