import os
from fastapi.testclient import TestClient
from schemaguard.app import app

client=TestClient(app)

def test_home_served():
    r=client.get('/')
    assert r.status_code==200 and 'SchemaGuard' in r.text and 'app.js' in r.text

def test_sql_baseline_endpoint_with_no_graph():
    r=client.post('/api/demo/sql',json={'target':'users.legacy_status'})
    assert r.status_code==200
    d=r.json(); assert d['mode']=='deterministic-sql-replay-not-an-agent'
    assert [s['status'] for s in d['scenarios']]==['unsafe','unsafe','verified']

def test_health_does_not_leak_secrets(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','TOP_SECRET_TEST_KEY_DO_NOT_ECHO')
    data=client.get('/api/health').json()
    assert 'TOP_SECRET_TEST_KEY_DO_NOT_ECHO' not in str(data)

def test_unsupported_target_rejected():
    r=client.post('/api/demo/sql',json={'target':'payments.credit_card'})
    assert r.status_code==422
    r=client.post('/api/demo/sql',json={'target':'users.id'})
    assert r.status_code==422


def test_summary_counts_sql_reference_without_calling_it_agent():
    data=client.get('/api/summary?target=users.legacy_status').json()
    assert data['source']=='deterministic-sql-reference'
    assert data['sql_reference_plans_passed']==1
    assert data['agent_verified_recommendations'] is None
    assert len(data['reference_results'])==3
    assert data['reference_results'][0]['failed_consumers']==['web-v2','digest-worker-v1']

def test_invalid_audit_id_rejected():
    assert client.get('/api/investigations/evil-injection').status_code==422

def test_real_agent_blocks_without_graph_service(monkeypatch):
    from schemaguard import app as module
    from schemaguard.graph import GraphUnavailable
    class MissingGraph:
        def context(self,*args):raise GraphUnavailable('unavailable')
    monkeypatch.setattr(module,'GraphStore',lambda:MissingGraph())
    r=client.post('/api/investigate',json={'target':'users.legacy_status'})
    assert r.status_code==503


def test_unused_field_summary_is_one_real_verified_reference_plan():
    r=client.get('/api/summary?target=users.retired_flag')
    assert r.status_code==200
    d=r.json()
    assert d['sql_reference_plans_passed']==1
    assert len(d['reference_results'])==1
    assert d['reference_results'][0]['verified']


def test_history_reports_incomplete_graph_as_unavailable(monkeypatch):
    from schemaguard import app as module
    from schemaguard.graph import GraphEvidenceIncomplete

    class StaleGraph:
        def query(self, *args, **kwargs):
            return []

        def verified_recommendations(self, *args, **kwargs):
            raise GraphEvidenceIncomplete('Missing/stale graph seed')

    monkeypatch.setattr(module, 'GraphStore', StaleGraph)
    response = client.get('/api/history')
    assert response.status_code == 503
    assert 'Missing/stale graph seed' in response.json()['detail']
