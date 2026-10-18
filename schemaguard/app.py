"""Single-process local demo UI + JSON API. No credentials sent to browsers."""
from __future__ import annotations
import json
import time
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .agent import AgentBlocked,run_agent
from .cli import ROOT,load_env,load_fixture
from .fixtures import fixture_copy,version_of
from .graph import GraphStore,GraphUnavailable,GraphEvidenceIncomplete
from .sqlcheck import execute_plan,example_plans
from . import queries

load_env()
app=FastAPI(title="SchemaGuard",version="0.1.0",description="Graph-grounded synthetic schema change agent")
app.mount('/static',StaticFiles(directory=Path(__file__).parent/'static'),name='static')

class ChangeRequest(BaseModel):
    target:str = 'users.legacy_status'

def validated_target(target: str, f: dict) -> str:
    if target not in ('users.'+x for x in f['schema']['users']):
        raise HTTPException(422,"Unsupported or unknown target. Choose an existing users column.")
    if target in ('users.id','users.name'):
        raise HTTPException(422,"Protected core contract column cannot be dropped by prototype")
    return target

@app.get('/')
def index():
    return FileResponse(Path(__file__).parent/'static'/'index.html')

@app.get('/api/health')
def health():
    out={"service":"schemaguard", "sqlite":"available", "falkordb":"unavailable",
         "model":"key_configured_not_tested" if __import__('os').getenv('OPENAI_API_KEY') else "missing_api_key",
         "agent_execution":"not_run_in_this_request",
         "mode":"synthetic-sandbox", "fixture_version":version_of(load_fixture())}
    try:
        g=GraphStore()
        if g.ping():
            out['falkordb']='connected_real_cypher'
            try:
                ctx=g.context(load_fixture(),'users.legacy_status')
                out['graph_context']=ctx['state']
            except GraphEvidenceIncomplete:
                out['graph_context']='needs_seed'
    except Exception as exc:
        out['falkordb_error']=f"{type(exc).__name__}: check docker compose up -d; pip install -r requirements.txt"
    return out

@app.get('/api/graph')
def graph_context(target:str='users.legacy_status'):
    f=load_fixture()
    validated_target(target,f)
    try:
        return GraphStore().context(f,target)
    except (GraphUnavailable,GraphEvidenceIncomplete,ImportError,ConnectionError) as exc:
        raise HTTPException(503,str(exc)) from exc

@app.post('/api/investigate')
async def investigate(payload:ChangeRequest):
    f=load_fixture()
    target=validated_target(payload.target,f)
    try:
        return await run_in_threadpool(run_agent,f,target,GraphStore())
    except (AgentBlocked,GraphUnavailable,GraphEvidenceIncomplete,ImportError) as exc:
        raise HTTPException(503,str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc

@app.post('/api/demo/sql')
def sql_diagnostics(payload:ChangeRequest):
    """DETERMINISTIC OFFLINE DIAGNOSTIC, not an agent, not a FalkorDB investigation."""
    f=load_fixture()
    target=validated_target(payload.target,f)
    scenarios=[]
    for item in example_plans(target,f):
        result=execute_plan(f,target,item['actions'])
        scenarios.append({"name":item['label'],"scope":item['scope'],**result})
    return {"mode":"deterministic-sql-replay-not-an-agent","target":target,
            "fixture_version":version_of(f),"scenarios":scenarios}

@app.get('/api/summary')
def summary(target:str='users.legacy_status'):
    f=load_fixture()
    validated_target(target,f)
    results=[]
    for item in example_plans(target,f):
        r=execute_plan(f,target,item['actions'])
        results.append({"name":item['label'],"scope":item['scope'],"status":r['status'],
                        "verified":r['verified'],"failed_consumers":r['affected_sql_failures'],
                        "preserved_outputs":[x['check'].replace('output:','') for x in r['checks']
                            if x['check'].startswith('output:') and x['passed']],
                        "steps":[x['action'] for x in r['step_checks']]})
    return {"source":"deterministic-sql-reference", "fixture_version":version_of(f),
            "target":target, "sql_reference_plans_passed":sum(x['verified'] for x in results),
            "agent_verified_recommendations":None,
            "agent_count_note":"Call /api/history for graph-persisted verified agent recommendations",
            "reference_results":results}

@app.get('/api/history')
def history(target:str='users.legacy_status'):
    f=load_fixture()
    validated_target(target,f)
    try:
        rows=GraphStore().query(queries.RECENT_ATTEMPTS,{"version":version_of(f),"target":target},read=True)
        count=GraphStore().verified_recommendations(f,target)
        return {"source":"FalkorDB","fixture_version":version_of(f),
                "agent_verified_recommendations":count,"attempts":[
            {"investigation_id":r[0],"attempt_id":r[1],"status":r[2],
             "actions":json.loads(r[3]),"verified":r[4]} for r in rows]}
    except (GraphUnavailable,GraphEvidenceIncomplete,ImportError) as exc:
        raise HTTPException(503,str(exc)) from exc

@app.get('/api/investigations/{investigation_id}')
def investigation_audit(investigation_id:str):
    import re
    if not re.fullmatch(r'inv:[a-f0-9]{12}',investigation_id):
        raise HTTPException(422,"Invalid investigation ID")
    try:
        rows=GraphStore().query(queries.INVESTIGATION_AUDIT,{'id':investigation_id},read=True)
    except (GraphUnavailable,ImportError) as exc:
        raise HTTPException(503,str(exc)) from exc
    if not rows:raise HTTPException(404,'Investigation not found')
    r=rows[0]
    return {"source":"FalkorDB", "investigation_id":investigation_id,"target":r[0],
            "fixture_version":r[1],"state":r[2],"model":r[3],
            "activity":json.loads(r[4] or '[]'),"recommendation":r[5],"completed_at":r[6]}

@app.post('/api/reset')
def reset():
    """Local demo-only reset; wipes ONLY project-scoped graph and demo fixture."""
    original=fixture_copy()
    dest=ROOT/'fixtures'/'demo.json'
    dest.write_text(json.dumps(original,indent=2)+'\n',encoding='utf8')
    try:
        seeded=GraphStore().seed(original)
        return {"status":"reset_and_reseeded","graph":"real FalkorDB",**seeded}
    except Exception as exc:
        raise HTTPException(503,f"Fixture restored; FalkorDB reset NOT completed ({type(exc).__name__}). Start FalkorDB and run seed.") from exc
