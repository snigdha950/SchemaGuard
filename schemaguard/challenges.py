"""Bounded challenge, comparison, and portable SQL reproduction utilities.
Deterministic diagnostics, not simulated agent actions. No graph fallback.
"""
from __future__ import annotations
import copy
import hashlib
import io
import itertools
import json
import re
import zipfile
from .fixtures import validate_fixture, version_of
from .sqlcheck import execute_plan

VERIFIER_VERSION='sqlite-contract-v3-stepwise'

def challenge_fixture(f, consumer_id, *, reads_target=True, required_target=False, active=True, target='users.legacy_status'):
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,47}',consumer_id):
        raise ValueError('Consumer ID must have 1-48 safe characters and start with a letter')
    if any(c['id']==consumer_id for c in f['consumers']):raise ValueError('Consumer ID already exists; reset or pick another')
    if len(f['consumers'])>=9:raise ValueError('Challenge consumer limit reached; reset the demo')
    column=target.split('.',1)[1]
    if target!='users.legacy_status' or column not in f['schema']['users']:raise ValueError('Challenge only supports users.legacy_status')
    if required_target and not reads_target:raise ValueError('Required target must be in selected projection')
    updated=copy.deepcopy(f)
    updated['consumers'].append({'id':consumer_id,'kind':'judge-worker','version':'challenge-1','active':active,
      'projection':['id','name']+([column] if reads_target else []),
      'required_output':['id','name']+([column] if required_target else []),
      'note':'Judge-controlled deployment/contract; actual reads reobserved using SQLite authorizer'})
    validate_fixture(updated)
    return updated

def compare_bounded_plans(f, target, *, max_candidates=32):
    """Exhaust subsets of <=5 repairable active target readers, exactly one final drop."""
    column=target.split('.',1)[1]
    impacted=[c for c in f['consumers'] if c['active'] and column in c['projection']]
    repairable=[c for c in impacted if column not in c['required_output']]
    if len(repairable)>5:raise ValueError('Bounded candidate comparison supports up to 5 repairable consumers')
    candidates=[]
    for n in range(len(repairable)+1):
        for group in itertools.combinations(repairable,n):
            actions=[{'type':'update_projection','consumer_id':c['id'],'remove_column':column} for c in group]+[{'type':'drop_column','target':target}]
            result=execute_plan(f,target,actions,expected_version=version_of(f))
            candidates.append({'actions':actions,'operations':len(actions),'verified':result['verified'],
               'status':result['status'],'failed_consumers':result['affected_sql_failures'],
               'failed_steps':[x for x in result['step_checks'] if not x['passed']],
               'unresolved_required_outputs':result['unresolved_required_outputs'],'duration_ms':result['duration_ms']})
            if len(candidates)>max_candidates:raise ValueError('Bounded search budget exceeded')
    winners=[c for c in candidates if c['verified']]
    minimum=min((c['operations'] for c in winners),default=None)
    best=next((c for c in winners if c['operations']==minimum),None)
    return {'scope':'exhaustive within subsets of active target-read projection updates, then one drop',
      'mode':'deterministic-sql-comparison-not-agent','target':target,'fixture_version':version_of(f),
      'candidates_tested':len(candidates),'minimum_operations':minimum,
      'smallest_passing_plan':best,'candidates':candidates,
      'limitation':'Does not prove global minimum across arbitrary SQL, deployments, or scheduling'}

def evidence_digest(ctx):
    subset={k:ctx[k] for k in ('fixture_version','affected','active_consumers','coverage')}
    subset['graph']=ctx['graph']
    return hashlib.sha256(json.dumps(subset,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

REPRO_CODE = r'''#!/usr/bin/env python3
"""Independent reproduction: python repro.py. Requires standard library only."""
import json,sqlite3
from pathlib import Path
b=json.loads(Path(__file__).with_name('bundle.json').read_text(encoding='utf8'))
f=b['fixture'];cols=f['schema']['users'];db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
if hasattr(sqlite3,'SQLITE_DBCONFIG_DQS_DML'):db.setconfig(sqlite3.SQLITE_DBCONFIG_DQS_DML,False)
if hasattr(sqlite3,'SQLITE_DBCONFIG_DQS_DDL'):db.setconfig(sqlite3.SQLITE_DBCONFIG_DQS_DDL,False)
db.execute('CREATE TABLE users ('+', '.join('"'+c+'" '+('INTEGER' if c in ('id','retired_flag') else 'TEXT') for c in cols)+')')
db.executemany('INSERT INTO users ('+', '.join('"'+c+'"' for c in cols)+') VALUES ('+','.join('?' for _ in cols)+')',[tuple(row[c] for c in cols) for row in f['rows']])
consumers={c['id']:dict(c) for c in f['consumers']}
def test():
  failures={}
  for cid,c in consumers.items():
    if not c['active']:continue
    sql='SELECT '+', '.join('"'+p+'"' for p in c['projection'])+' FROM "users" ORDER BY "id"'
    try:
      data=[{k:row[k] for k in c['required_output']} for row in db.execute(sql).fetchall()]
      failures[cid]={'sql':sql,'actual_output':data}
    except Exception as e:failures[cid]={'sql':sql,'error':str(e)}
  return failures
baseline=test()
for action in b['plan']:
  if action['type']=='update_projection':consumers[action['consumer_id']]['projection'].remove(action['remove_column'])
  elif action['type']=='drop_column':db.execute('ALTER TABLE "users" DROP COLUMN "'+action['target'].split('.')[1]+'"')
  after=test()
  print('Step:',json.dumps(action));print('Observed:',json.dumps(after,indent=2))
  failures={cid:val for cid,val in after.items() if 'error' in val or val.get('actual_output')!=baseline[cid].get('actual_output')}
  if failures:break
actual=sorted(failures);expected=sorted(b['expected_failed_consumers'])
print('Expected failed consumers:',expected)
print('Actually failed consumers:',actual)
assert actual==expected,'Reproduction did not match the captured SQLite failure'
print('REPRODUCED: actual SQL and broken consumer contract match captured case')
'''

def failure_reproduction(f,target,actions):
    result=execute_plan(f,target,actions)
    if result['verified']:raise ValueError('Cannot reproduce a verified plan')
    if not result['affected_sql_failures']:raise ValueError('No failing SQL consumer to reproduce')
    data={'fixture':f,'target':target,'plan':actions,'fixture_version':version_of(f),
      'expected_failed_consumers':result['affected_sql_failures'],
      'captured_sql':{cid:result['after'][cid]['sql'] for cid in result['affected_sql_failures']},
      'captured_errors':{cid:result['after'][cid]['error'] for cid in result['affected_sql_failures']},
      'expected_required_output':{cid:v['output'] for cid,v in result['baseline'].items()},
      'observed_after':{cid:v['output'] for cid,v in result['after'].items()},
      'actual_step_checks':result['step_checks'],'sql_errors':result['sql_errors'],
      'provenance':'actual SQLite execution, controlled synthetic fixture'}
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
      z.writestr('repro.py',REPRO_CODE)
      z.writestr('bundle.json',json.dumps(data,indent=2))
      z.writestr('README.txt','Run: python repro.py\nPython standard library only.\nExpected: REPRODUCED, exit 0.\nSynthetic data only.\n')
    return out.getvalue()

def assess_receipt(record,current_context,*,current_version,evidence_error=None):
    reasons=[]
    if record['fixture_version']!=current_version:reasons.append('Configuration/contract version changed')
    if record.get('verifier_version')!=VERIFIER_VERSION:reasons.append('Verifier version changed')
    if evidence_error:reasons.append('Current graph evidence unavailable/incomplete: '+evidence_error[:220])
    elif current_context is None or current_context['state']!='complete':reasons.append('Current graph evidence incomplete')
    elif record.get('graph_evidence_digest')!=evidence_digest(current_context):reasons.append('Connected deployment/query/read evidence changed')
    if record['state']!='verified' or record['final_status']!='verified' or not record['deterministic_verified']:
      reasons.append('No independently verified and durably audited recommendation')
    valid=not reasons
    return {**record,'fresh_verified':valid,'receipt_status':'verified_current' if valid else 'stale_or_unverified','freshness_reasons':reasons}
