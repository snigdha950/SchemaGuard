"""Windows-compatible CLI. Usage python -m schemaguard.cli [check|seed|sql-demo|serve]"""
import argparse
import json
import os
import sys
from pathlib import Path
from .fixtures import fixture_copy,validate_fixture,version_of
from .sqlcheck import execute_plan,example_plans,observations

ROOT=Path(__file__).resolve().parent.parent

def load_env():
    env=ROOT/'.env'
    if env.exists():
        for raw in env.read_text(encoding='utf8').splitlines():
            line=raw.strip()
            if not line or line.startswith('#') or '=' not in line:continue
            key,value=line.split('=',1)
            os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))

def load_fixture(path=None):
    loc=Path(path) if path else ROOT/'fixtures'/'demo.json'
    obj=json.loads(loc.read_text(encoding='utf8')) if loc.exists() else fixture_copy()
    validate_fixture(obj)
    return obj

def main():
    p=argparse.ArgumentParser()
    p.add_argument('command',choices=['check','seed','sql-demo','serve','status'])
    p.add_argument('--fixture',default=None)
    p.add_argument('--target',default='users.legacy_status')
    a=p.parse_args()
    load_env()
    f=load_fixture(a.fixture)
    if a.command=='serve':
        import uvicorn
        uvicorn.run('schemaguard.app:app',host='127.0.0.1',port=8000,reload=False)
        return
    if a.command=='sql-demo':
        for plan in example_plans(a.target,f):
            result=execute_plan(f,a.target,plan['actions'])
            print(json.dumps({"label":plan['label'],"status":result['status'],"failed":result['affected_sql_failures'],
                "checks":result['checks'],"actions":result['actions']},indent=2))
        return
    if a.command=='status':
        print('fixture_version:',version_of(f),'API key configured:',bool(os.getenv('OPENAI_API_KEY')))
    try:
        from .graph import GraphStore
        g=GraphStore()
        print('FalkorDB real Cypher traversal/ping:',g.ping())
        if a.command=='seed': print('Seed result:',json.dumps(g.seed(f)))
        elif a.command=='check':
            from . import queries
            traversal=g.query(queries.ALL_PATHS,read=True)
            print('Real Cypher traversal rows:',len(traversal))
            print(json.dumps(g.context(f,a.target)['coverage'],indent=2))
    except Exception as exc:
        print('BLOCKED FalkorDB:',type(exc).__name__,str(exc)[:220],file=sys.stderr)
        if a.command in ('check','seed'): sys.exit(2)
    if a.command=='status':
        print('SQLite observed active consumers:',len([o for o in observations(f) if o['active']]))

if __name__=='__main__': main()
