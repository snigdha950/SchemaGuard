"""Unit doubles are ONLY tests; live application never uses an in-memory graph substitute."""
import os
import pytest
from schemaguard.fixtures import fixture_copy,version_of
from schemaguard.graph import GraphStore,GraphUnavailable,GraphEvidenceIncomplete
from schemaguard.agent import run_agent,AgentBlocked
from schemaguard import queries as Q

class FailingConnector:
    def query(self,*a,**k): raise OSError('FalkorDB offline')
    ro_query=query

class Result:
    def __init__(self,result):self.result_set=result

class FakeGraphForUnitTests:
    def __init__(self,f):
        self.f=f;self.version=version_of(f);self.on=True;self.remove_observation=False
    def query(self,q,params=None,timeout=None):return Result(self.out(q,params))
    def ro_query(self,q,params=None,timeout=None):return Result(self.out(q,params))
    def out(self,q,params):
        if q==Q.PING:return [[1]]
        if q==Q.GET_VERSION:return [[self.version,self.f['fixture_name']]]
        if q==Q.ALL_COLUMNS:return [['users.'+c] for c in self.f['schema']['users']]
        if q==Q.ALL_PATHS:
            rows=[]
            for c in self.f['consumers']:
                for col in c['projection']:
                    rows.append(['deployment:'+c['id'],c['active'] and self.on,'synthetic-demo',c['id'],c['kind'],c['version'],'query:'+c['id'],'users.'+col])
            return rows
        if q==Q.AFFECTED:
            return [['deployment:'+c['id'],'synthetic-demo',c['id'],c['kind'],c['version'],'query:'+c['id'],
                     None if self.remove_observation else 'read:'+self.version+':'+c['id']+':'+params['target'],
                     'sqlite.authorizer',self.version] for c in self.f['consumers'] if c['active'] and self.on and params['target'].split('.')[1] in c['projection']]
        if q==Q.OBSERVATION_COVERAGE:
            return [[c['id'],'query:'+c['id'],'probe:'+c['id'],True,''] for c in self.f['consumers'] if c['active'] and self.on]
        if q==Q.READ_EVIDENCE:
            return [[c['id'],'users.'+col,'read:'+c['id']+':'+col] for c in self.f['consumers'] if c['active'] and self.on for col in c['projection']]
        raise AssertionError('Unexpected query')

def test_no_falkor_blocks_investigation():
    store=GraphStore(connector=FailingConnector())
    with pytest.raises(GraphUnavailable):store.context(fixture_copy(),'users.legacy_status')

def test_active_dependency_changes_affected_result_and_coverage_blocks_drift():
    f=fixture_copy();stub=FakeGraphForUnitTests(f);store=GraphStore(connector=stub)
    first=store.context(f,'users.legacy_status')
    assert first['state']=='complete'
    assert {x['consumer'] for x in first['active_consumers']}=={'web-v3','web-v2','digest-worker-v1'}
    assert next(x for x in first['active_consumers'] if x['consumer']=='web-v3')['affected'] is False
    assert {x['consumer'] for x in first['affected']}=={'web-v2','digest-worker-v1'}
    stub.on=False  # simulates changed graph Deployment.active, missing active evidence
    second=store.context(f,'users.legacy_status')
    assert len(second['affected'])==0 and second['state']=='incomplete'

def test_missing_observation_not_safe():
    f=fixture_copy();stub=FakeGraphForUnitTests(f);stub.remove_observation=True
    context=GraphStore(connector=stub).context(f,'users.legacy_status')
    assert context['state']=='incomplete'
    assert any('no matching current-version' in x for x in context['coverage']['issues'])

def test_agent_missing_key_is_blocked_only_after_graph_available(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    f=fixture_copy()
    with pytest.raises(AgentBlocked,match='OPENAI_API_KEY'):
        run_agent(f,'users.legacy_status',GraphStore(connector=FakeGraphForUnitTests(f)))

def test_bounded_llm_tool_loop_with_test_only_model_stub(monkeypatch):
    """Orchestrator UNIT TEST: model responses mocked; not a real LLM call."""
    import json, sys, types
    f=fixture_copy()
    class PersistableGraph(FakeGraphForUnitTests):
        def __init__(self,f): super().__init__(f); self.saved=[]
        def create_investigation(self,*args):self.saved.append(('investigation',args))
        def record_attempt(self,*args):self.saved.append(('attempt',args))
        def recommendation(self,*args):self.saved.append(('recommendation',args))
        def save_audit(self,*args):self.saved.append(('audit',args))
    graph=PersistableGraph(f)
    from schemaguard.sqlcheck import example_plans
    plans=example_plans('users.legacy_status',f)
    class Message:
        def __init__(self,name,arguments):
            self.name=name;self.arguments=arguments;self.content=None
            self.tool_calls=[types.SimpleNamespace(id='call-'+name,function=types.SimpleNamespace(name=name,arguments=json.dumps(arguments)))]
        def model_dump(self,exclude_none=True):
            return {'role':'assistant','tool_calls':[{'id':'call-'+self.name,'type':'function',
                    'function':{'name':self.name,'arguments':json.dumps(self.arguments)}}]}
    class Completer:
        def __init__(self): self.iter=0
        def create(self,**kwargs):
            i=self.iter;self.iter+=1
            if i==0:call=Message('inspect_change',{'target':'users.legacy_status'})
            elif i==1:call=Message('find_affected_consumers',{'target':'users.legacy_status'})
            elif i==2:call=Message('test_plan',{'actions':plans[2]['actions']})
            else:
                last_result=json.loads(kwargs['messages'][-1]['content'])
                call=Message('record_recommendation',{'attempt_id':last_result['attempt_id'], 'recommendation':'All active projections repaired before DROP; SQLite passes.'})
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=call)])
    completer=Completer()
    monkeypatch.setitem(sys.modules,'openai',types.SimpleNamespace(OpenAI=lambda **kwargs:types.SimpleNamespace(chat=types.SimpleNamespace(completions=completer))))
    monkeypatch.setenv('OPENAI_API_KEY','UNIT_TEST_MODEL_STUB_NOT_CREDENTIAL')
    store=GraphStore(connector=graph)
    store.create_investigation=graph.create_investigation
    store.record_attempt=graph.record_attempt
    store.recommendation=graph.recommendation
    store.save_audit=graph.save_audit
    store.confirm_recommendation=lambda *args: True # unit-only fake
    result=run_agent(f,'users.legacy_status',store)
    assert result['mode']=='real-llm-agent' # mode name is code-path label, stub is test-only
    assert result['status']=='verified'
    assert [e['tool'] for e in result['activity']]==['inspect_change','find_affected_consumers','test_plan','record_recommendation']
    assert {x[0] for x in graph.saved}=={'investigation','attempt','recommendation','audit'}


def test_changed_worker_identity_and_dependency_changes_graph_context_unit_only():
    # Test double only, NOT evidence of a live FalkorDB reseed.
    f=fixture_copy()
    worker=next(c for c in f['consumers'] if c['kind']=='worker')
    worker['id']='alerts-job-v9'
    worker['version']='9.0'
    worker['projection']=['id','name']  # no longer reads legacy_status
    store=GraphStore(connector=FakeGraphForUnitTests(f))
    ctx=store.context(f,'users.legacy_status')
    assert ctx['state']=='complete'
    assert {x['consumer'] for x in ctx['affected']}=={'web-v2'}
    assert 'alerts-job-v9' in ctx['coverage']['active_consumers']


def test_compromised_graph_with_missing_both_read_edge_and_observation_is_incomplete():
    f=fixture_copy()
    class OmissionGraph(FakeGraphForUnitTests):
        def out(self,q,params):
            r=super().out(q,params)
            if q==Q.ALL_PATHS:
                return [p for p in r if not(p[3]=='web-v2' and p[7]=='users.legacy_status')]
            if q==Q.READ_EVIDENCE:
                return [p for p in r if not(p[0]=='web-v2' and p[1]=='users.legacy_status')]
            if q==Q.AFFECTED:
                return [p for p in r if p[2]!='web-v2']
            return r
    ctx=GraphStore(connector=OmissionGraph(f)).context(f,'users.legacy_status')
    assert ctx['state']=='incomplete'
    assert any('fresh SQLite authorizer' in issue for issue in ctx['coverage']['issues'])


def test_affected_query_must_match_graph_reads():
    f=fixture_copy()
    class InconsistentTraversal(FakeGraphForUnitTests):
        def out(self,q,params):
            rows=super().out(q,params)
            return [r for r in rows if r[2]!='web-v2'] if q==Q.AFFECTED else rows
    ctx=GraphStore(connector=InconsistentTraversal(f)).context(f,'users.legacy_status')
    assert ctx['state']=='incomplete'
    assert any('Affected-traversal' in x for x in ctx['coverage']['issues'])
