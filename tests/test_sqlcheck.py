import copy
import pytest
from schemaguard.fixtures import fixture_copy,version_of
from schemaguard.sqlcheck import execute_plan,example_plans,observations

TARGET='users.legacy_status'

def test_authorizer_captures_actual_columns():
    results={o['id']:o for o in observations(fixture_copy())}
    assert 'users.legacy_status' not in results['web-v3']['reads']
    assert 'users.legacy_status' in results['web-v2']['reads']
    assert 'users.legacy_status' in results['digest-worker-v1']['reads']

def test_latest_only_is_false_negative():
    f=fixture_copy()
    r=execute_plan(f,TARGET,example_plans(TARGET,f)[0]['actions'])
    assert r['status']=='unsafe' and set(r['affected_sql_failures'])=={'web-v2','digest-worker-v1'}
    assert r['after']['web-v2']['error'].startswith('OperationalError: no such column')
    assert any(c['check']=='target-column-dropped' and c['passed'] for c in r['checks'])

def test_partial_repair_fails_other_active_consumer():
    f=fixture_copy()
    r=execute_plan(f,TARGET,example_plans(TARGET,f)[1]['actions'])
    assert r['status']=='unsafe'
    assert r['affected_sql_failures']==['digest-worker-v1']
    assert r['after']['web-v2']['ok']

def test_full_repair_preserves_contracts_records():
    f=fixture_copy()
    r=execute_plan(f,TARGET,example_plans(TARGET,f)[2]['actions'])
    assert r['verified'] and not r['affected_sql_failures']
    assert all(c['passed'] for c in r['checks'])
    assert 'legacy_status' not in r['schema_after']
    assert all(r['baseline'][c]['output']==r['after'][c]['output'] for c in r['all_required_consumers'])

def test_unused_column_safe_without_projection_changes():
    r=execute_plan(fixture_copy(),'users.retired_flag',[{'type':'drop_column','target':'users.retired_flag'}])
    assert r['verified']

def test_change_consumer_names_not_hardcoded():
    f=fixture_copy()
    f['consumers'][1]['id']='legacy-gateway-v8'
    f['consumers'][2]['id']='weekly-export-v6'
    r=execute_plan(f,TARGET,[{'type':'drop_column','target':TARGET}])
    assert set(r['affected_sql_failures'])=={'legacy-gateway-v8','weekly-export-v6'}
    fix=example_plans(TARGET,f)[2]
    assert execute_plan(f,TARGET,fix['actions'])['verified']

def test_change_dependency_changes_failure():
    f=fixture_copy()
    f['consumers'][2]['projection'].remove('legacy_status')
    r=execute_plan(f,TARGET,example_plans(TARGET,f)[0]['actions'])
    assert r['affected_sql_failures']==['web-v2']

def test_required_output_depends_on_column_unresolved():
    f=fixture_copy()
    f['consumers'][2]['required_output'].append('legacy_status')
    suggested=example_plans(TARGET,f)[2]['actions']
    assert not any(a.get('consumer_id')=='digest-worker-v1' for a in suggested)
    assert not execute_plan(f,TARGET,suggested)['verified']
    with pytest.raises(ValueError,match='Required output'):
        execute_plan(f,TARGET,[{'type':'update_projection','consumer_id':'digest-worker-v1','remove_column':'legacy_status'}])

def test_fresh_database_per_attempt():
    f=fixture_copy()
    assert not execute_plan(f,TARGET,[{'type':'drop_column','target':TARGET}])['verified']
    assert execute_plan(f,TARGET,example_plans(TARGET,f)[2]['actions'])['verified']

def test_version_binding_and_no_arbitrary_sql():
    f=fixture_copy()
    with pytest.raises(ValueError,match='Stale'):
        execute_plan(f,TARGET,[],expected_version='old-fixture')
    with pytest.raises(ValueError,match='Unsupported'):
        execute_plan(f,TARGET,[{'type':'raw_sql','sql':'DROP TABLE users'}])
    with pytest.raises(ValueError,match='Unknown or inactive'):
        execute_plan(f,TARGET,[{'type':'update_projection','consumer_id':'preview-v4','remove_column':'legacy_status'}])


def test_repair_must_precede_drop_to_avoid_intermediate_outage():
    f=fixture_copy()
    correct=example_plans(TARGET,f)[2]['actions']
    inverted=[correct[-1]]+correct[:-1]
    r=execute_plan(f,TARGET,inverted)
    assert not r['verified']
    assert r['step_checks'][0]['passed'] is False
    assert len(r['applied'])==1  # stopped before post-failure patch


def test_latest_only_comparison_not_tied_to_consumer_name():
    f=fixture_copy()
    f['consumers'][0]['id']='current-frontend-v9'
    r=execute_plan(f,TARGET,[{'type':'drop_column','target':TARGET}])
    assert r['latest_only_would_pass']
    assert r['latest_checked_consumer']=='current-frontend-v9'
    assert not r['verified']
