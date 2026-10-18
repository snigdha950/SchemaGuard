"""Acceptance-script startup checks; these do not pretend a model was called."""
import importlib.util
from pathlib import Path
import zoneinfo

from schemaguard.graph import GraphUnavailable


def test_live_check_handles_missing_windows_timezone_data(monkeypatch, capsys):
    def unavailable_timezone(*args, **kwargs):
        raise zoneinfo.ZoneInfoNotFoundError('No system timezone database')

    monkeypatch.setattr(zoneinfo, 'ZoneInfo', unavailable_timezone)
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'live_end_to_end.py'
    spec = importlib.util.spec_from_file_location('live_acceptance_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def unavailable_graph():
        raise GraphUnavailable('Deliberately offline in this unit test')

    monkeypatch.setattr(module, 'load_env', lambda: None)
    monkeypatch.setattr(module, 'GraphStore', unavailable_graph)
    monkeypatch.setenv('OPENAI_API_KEY', 'UNIT_TEST_ONLY_NOT_A_CREDENTIAL')
    assert module.main() == 2
    assert 'GraphUnavailable' in capsys.readouterr().err
