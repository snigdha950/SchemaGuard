"""HTML contract checks for the existing frontend; not a browser integration claim."""
from pathlib import Path
from fastapi.testclient import TestClient
from schemaguard.app import app

STATIC = Path(__file__).parents[1] / 'schemaguard' / 'static'

def test_migration_workbench_keeps_real_controls():
    markup = (STATIC / 'index.html').read_text(encoding='utf8')
    for field in ('target', 'run', 'replay', 'reset', 'graphArea', 'consumers',
                  'attempts', 'activity', 'recommendation', 'comparisonResult',
                  'challengeName', 'challenge', 'repro', 'compare', 'receipt'):
        assert f'id="{field}"' in markup, field
    assert markup.index('id="verification"') < markup.index('id="impact"')
    assert markup.index('id="impact"') < markup.index('id="demo-tools"')
    assert '<details class="advanced-tools"' in markup
    assert '<div class="stats"' not in markup
    assert 'Reference checks' in markup

def test_summary_is_real_sql_not_agent_recommendation():
    body = TestClient(app).get('/api/summary').json()
    assert body['source'] == 'deterministic-sql-reference'
    assert body['agent_verified_recommendations'] is None
    assert body['reference_results'][0]['failed_consumers']
    assert body['reference_results'][2]['verified']
