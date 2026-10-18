"""Opt-in DESTRUCTIVE-TO-THIS-DEMO-GRAPH integration test; needs live FalkorDB.
Run: RUN_LIVE_FALKOR=1 python -m pytest tests/test_live_falkor.py -v
"""
import os
import pytest
from schemaguard.fixtures import fixture_copy
from schemaguard.graph import GraphStore
from schemaguard import queries as Q

pytestmark=pytest.mark.skipif(os.getenv('RUN_LIVE_FALKOR')!='1',reason='Set RUN_LIVE_FALKOR=1 with a real FalkorDB instance')

def test_real_cypher_changes_results_and_memory_survives_new_connection():
    f=fixture_copy()
    g=GraphStore()
    assert g.ping()
    g.seed(f)
    try:
        before=g.context(f,'users.legacy_status')
        assert before['state']=='complete'
        assert {c['consumer'] for c in before['affected']}=={'web-v2','digest-worker-v1'}
        # Alter true graph fact: this is not a mock. Drift changes affected result and blocks verification.
        g.query("MATCH (d:Deployment {id:$id}) SET d.active=false",{'id':'deployment:digest-worker-v1'})
        changed=g.context(f,'users.legacy_status')
        assert {c['consumer'] for c in changed['affected']}=={'web-v2'}
        assert changed['state']=='incomplete'  # fixture still requires active worker
        g.seed(f)
        g.query("MATCH (o:Observation {id:$id}) DETACH DELETE o",{'id':f"read:{before['fixture_version']}:web-v2:users.legacy_status"})
        changed=g.context(f,'users.legacy_status')
        assert changed['state']=='incomplete'  # missing observation != unused
        g.seed(f)
        # Changed worker ID and dependency, then REAL reseed and new-connection lookup.
        import copy
        updated=copy.deepcopy(f)
        worker=next(c for c in updated['consumers'] if c['kind']=='worker')
        worker['id']='alerts-job-v9'
        worker['version']='9.0'
        worker['projection']=['id','name']
        g.seed(updated)
        renamed=GraphStore().context(updated,'users.legacy_status')
        assert renamed['state']=='complete'
        assert {c['consumer'] for c in renamed['affected']}=={'web-v2'}
        g.seed(f)
        # Real graph audit persistence across independent clients (not a mocked LLM).
        iid='inv:000000000001'
        g.create_investigation(iid,'users.legacy_status',before['fixture_version'])
        g.save_audit(iid,'integration-test-no-model','incomplete',[
            {'step':1,'tool':'test-only-persisted-graph-event','ok':True}])
        audit=GraphStore().query(Q.INVESTIGATION_AUDIT,{'id':iid},read=True)
        assert audit and 'test-only-persisted-graph-event' in audit[0][4]
        # A new client session reads graph-backed context again.
        reconnected=GraphStore()
        assert reconnected.context(f,'users.legacy_status')['state']=='complete'
    finally:
        g.seed(f)
