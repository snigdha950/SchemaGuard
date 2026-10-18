"""Adversarial offline regressions. No model or graph integration claims."""
import io,json,subprocess,sys,zipfile
from fastapi.testclient import TestClient
import pytest
from schemaguard.fixtures import fixture_copy,version_of
from schemaguard.challenges import challenge_fixture,compare_bounded_plans,failure_reproduction,assess_receipt,evidence_digest,VERIFIER_VERSION
from schemaguard.sqlcheck import execute_plan
from schemaguard.app import app
T='users.legacy_status'

def test_bounded_minimum():
 f=fixture_copy();c=compare_bounded_plans(f,T)
 assert c['candidates_tested']==4 and c['minimum_operations']==3
 assert sum(x['verified'] for x in c['candidates'])==1
 assert all(x['failed_consumers'] for x in c['candidates'] if not x['verified'])

def test_judge_unseen_name_and_contracts():
 f=fixture_copy()
 changed=challenge_fixture(f,'zeta-surprise-802')
 assert version_of(changed)!=version_of(f)
 assert compare_bounded_plans(changed,T)['minimum_operations']==4
 assert compare_bounded_plans(challenge_fixture(f,'ghost-consumer',active=False),T)['minimum_operations']==3
 assert compare_bounded_plans(challenge_fixture(f,'invoice-process',reads_target=False),T)['minimum_operations']==3
 assert compare_bounded_plans(challenge_fixture(f,'output-contract',required_target=True),T)['minimum_operations'] is None
 with pytest.raises(ValueError):challenge_fixture(f,'web-v3')
 with pytest.raises(ValueError):challenge_fixture(f,'bad name!')

def test_unsafe_step_order():
 f=fixture_copy();r=execute_plan(f,T,[{'type':'drop_column','target':T},{'type':'update_projection','consumer_id':'web-v2','remove_column':'legacy_status'}])
 assert not r['verified'] and len(r['step_checks'])==1
 assert set(r['affected_sql_failures'])=={'web-v2','digest-worker-v1'}

def test_portable_repro_executes_sql(tmp_path):
 f=fixture_copy()
 z=failure_reproduction(f,T,[{'type':'drop_column','target':T}])
 with zipfile.ZipFile(io.BytesIO(z)) as archive:
  b=json.loads(archive.read('bundle.json'))
  assert 'no such column' in b['captured_errors']['web-v2'].lower()
  archive.extractall(tmp_path)
 r=subprocess.run([sys.executable,str(tmp_path/'repro.py')],text=True,capture_output=True)
 assert r.returncode==0,r.stderr
 assert 'REPRODUCED' in r.stdout

def test_receipt_staleness_and_unavailable_graph():
 f=fixture_copy();ctx={'fixture_version':version_of(f),'affected':[],'active_consumers':[],'coverage':{'issues':[]},'graph':{'nodes':[],'edges':[]},'state':'complete'}
 rec={'fixture_version':version_of(f),'verifier_version':VERIFIER_VERSION,'graph_evidence_digest':evidence_digest(ctx),'state':'verified','final_status':'verified','deterministic_verified':True}
 assert assess_receipt(rec,ctx,current_version=version_of(f))['fresh_verified']
 mutated=json.loads(json.dumps(ctx));mutated['graph']['edges'].append({'source':'new','target':'old'})
 assert not assess_receipt(rec,mutated,current_version=version_of(f))['fresh_verified']
 assert not assess_receipt(rec,None,current_version=version_of(f),evidence_error='graph down')['fresh_verified']
 assert not assess_receipt({**rec,'final_status':'pending_commit'},ctx,current_version=version_of(f))['fresh_verified']
 assert not assess_receipt(rec,ctx,current_version=version_of(challenge_fixture(f,'fresh-worker')))['fresh_verified']

def test_api_fail_closed_and_download():
 api=TestClient(app)
 assert api.get('/api/compare').json()['mode']=='deterministic-sql-comparison-not-agent'
 assert api.post('/api/challenge',json={'consumer_id':'web-v3'}).status_code==422
 assert api.post('/api/challenge',json={'consumer_id':'new-worker'}).status_code==503
 assert api.post('/api/reproduction',json={'actions':[{'type':'drop_column','target':T}]}).content[:2]==b'PK'
 assert api.get('/api/receipt/invalid').status_code==422

def test_graph_write_failure_blocks_fixture_commit(monkeypatch):
 import schemaguard.app as module
 f=fixture_copy();monkeypatch.setattr(module,'load_fixture',lambda:f)
 class BrokenGraph:
  def seed(self,fixture):raise RuntimeError('injected write failure')
 monkeypatch.setattr(module,'GraphStore',lambda:BrokenGraph())
 response=TestClient(app).post('/api/challenge',json={'consumer_id':'new-worker'})
 assert response.status_code==503
 assert all(c['id']!='new-worker' for c in f['consumers'])
