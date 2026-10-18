"""Live, opt-in FalkorDB + model acceptance path. Never substitutes a test double.

Run AFTER Docker, dependencies, and OPENAI_API_KEY configuration:
    python scripts/live_end_to_end.py
Destructive scope: *only* configured schemaguard_* demo graph. Requires TWO real
model investigations and resets graph to the original fixture in finally.
"""
from __future__ import annotations
import json
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from schemaguard.cli import load_env, load_fixture
from schemaguard.fixtures import version_of
from schemaguard.graph import GraphStore
from schemaguard.agent import run_agent
from schemaguard.sqlcheck import execute_plan, example_plans
from schemaguard import queries as Q

TARGET='users.legacy_status'
EVIDENCE=ROOT/'evidence'/'live-falkordb-agent-results.json'
BLOCKED_EVIDENCE=ROOT/'evidence'/'live-acceptance-blocked.json'
# Windows does not include an IANA timezone database. IST has a fixed UTC+05:30
# offset, so report timestamps need no optional tzdata package or system files.
IST=timezone(timedelta(hours=5, minutes=30))

def main() -> int:
    load_env()
    f=load_fixture()
    if not os.getenv('OPENAI_API_KEY'):
        print('BLOCKED: Set OPENAI_API_KEY privately in .env. No live agent was run.')
        return 2
    graph=None
    model_attempted=False
    partial={"mode":"live-attempt-no-test-doubles",
             "generated_at_ist":datetime.now(IST).isoformat(),
             "status":"incomplete", "original_agent":None, "modified_agent":None}
    try:
        graph=GraphStore()
        assert graph.ping(), 'No real FalkorDB ping'
        g1=graph.seed(f)
        # Real Cypher traversal, no Python topology fallback.
        assert graph.query(Q.ALL_PATHS,read=True), 'No graph paths returned'
        original=graph.context(f,TARGET)
        assert original['state']=='complete', original['coverage']['issues']
        assert {x['consumer'] for x in original['affected']}=={'web-v2','digest-worker-v1'}
        baseline=[]
        for plan in example_plans(TARGET,f):
            result=execute_plan(f,TARGET,plan['actions'])
            baseline.append({'name':plan['label'],'scope':plan['scope'],'status':result['status'],
                             'verified':result['verified'],'failed_consumers':result['affected_sql_failures'],
                             'sql_errors':result['sql_errors'],'checks':result['checks'],
                             'step_checks':result['step_checks']})
        assert [x['verified'] for x in baseline]==[False,False,True]
        original_path_count=len(graph.query(Q.ALL_PATHS,read=True))
        model_attempted=True
        first=run_agent(f,TARGET,graph)  # Actual model calls required. No stubs.
        partial['original_agent']=first
        assert first['mode']=='real-llm-agent'
        assert first['recommendation'] and first['recommendation']['verified'], 'No model-selected verified plan'
        assert {'inspect_change','find_affected_consumers','test_plan','record_recommendation'} <= {x['tool'] for x in first['activity'] if x['ok']}
        # Fresh DB client, persisted run and audit query from the *real* graph.
        audit=GraphStore().query(Q.INVESTIGATION_AUDIT,{'id':first['investigation_id']},read=True)
        assert audit and audit[0][4], 'Live agent activity not persisted'
        # Change both name and dependency, and reobserve/reseed instead of hardcoding old worker.
        changed=json.loads(json.dumps(f))
        worker=next(c for c in changed['consumers'] if c['kind']=='worker')
        worker['id']='alert-worker-v9'
        worker['version']='9.0'
        worker['projection']=['id','name']
        new_seed=graph.seed(changed)
        updated=GraphStore().context(changed,TARGET)
        assert updated['state']=='complete'
        assert {x['consumer'] for x in updated['affected']}=={'web-v2'}
        second=run_agent(changed,TARGET,GraphStore())
        partial['modified_agent']=second
        assert second['recommendation'] and second['recommendation']['verified'], 'Changed worker investigation not verified'
        report={
            'generated_at_ist':datetime.now(IST).isoformat(),
            'mode':'ACTUAL_FALKORDB_AND_REAL_LLM_NO_STUBS',
            'original':{'seed':g1,'version':version_of(f),'cypher_paths':original_path_count,
                'affected_from_graph':original['affected'],'reference_sql':baseline,'agent':first,
                'persisted_audit_retrieved_from_new_client':bool(audit[0][4])},
            'changed_worker':{'seed':new_seed,'version':version_of(changed),
                'affected_from_graph':updated['affected'],'agent':second},
        }
        EVIDENCE.write_text(json.dumps(report,indent=2,default=str)+'\n',encoding='utf-8')
        if BLOCKED_EVIDENCE.exists():BLOCKED_EVIDENCE.unlink()
        print('LIVE PASSED: graph, changed dependency, model tools, SQLite, persisted audit.')
        print('Evidence:',EVIDENCE)
        return 0
    except Exception as exc:
        if model_attempted:
            partial['status']='blocked_or_failed'
            partial['blocker_type']=type(exc).__name__
            BLOCKED_EVIDENCE.write_text(json.dumps(partial,indent=2,default=str)+'\n',encoding='utf8')
            print('Partial REAL attempted tool evidence:',BLOCKED_EVIDENCE,file=sys.stderr)
        print('BLOCKED/FAILED, NOT VERIFIED:',type(exc).__name__,str(exc)[:350],file=sys.stderr)
        return 2
    finally:
        if graph is not None:
            try:
                # Prevent modified worker graph from remaining after acceptance test.
                graph.seed(f)
            except Exception as exc:
                print('WARNING: graph restoration failed:',type(exc).__name__,str(exc)[:200],file=sys.stderr)

if __name__=='__main__':raise SystemExit(main())
