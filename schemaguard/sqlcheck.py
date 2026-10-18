"""Deterministic SQL verifier independent of LLM and graph. Every attempt gets fresh SQLite."""
from __future__ import annotations
import copy
import sqlite3
import time
from typing import Any
from .fixtures import validate_fixture, version_of

# Controlled identifiers come exclusively from validated fixture schema (never raw model SQL).
ALLOWED_ACTIONS = {"update_projection", "drop_column"}

def connection(f: dict) -> sqlite3.Connection:
    validate_fixture(f)
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.setconfig(sqlite3.SQLITE_DBCONFIG_DQS_DML, False)  # reject missing quoted columns; never convert them into string literals
    cols = f["schema"]["users"]
    ddl = ", ".join(f'"{x}" ' + ("INTEGER PRIMARY KEY" if x == "id" else "INTEGER" if x == "retired_flag" else "TEXT") for x in cols)
    db.execute(f'CREATE TABLE users ({ddl})')
    db.executemany('INSERT INTO users (' + ', '.join(f'"{x}"' for x in cols) + ') VALUES (' + ','.join('?' for _ in cols) + ')', [tuple(r[x] for x in cols) for r in f["rows"]])
    return db

def run_consumer(db: sqlite3.Connection, c: dict) -> dict:
    sql = 'SELECT ' + ', '.join('"' + p + '"' for p in c["projection"]) + ' FROM "users" ORDER BY "id"'
    reads: set[tuple[str, str]] = set()
    def authorizer(action, table, column, database, trigger):
        if action == sqlite3.SQLITE_READ and table and column:
            reads.add((str(table), str(column)))
        return sqlite3.SQLITE_OK
    db.set_authorizer(authorizer)
    try:
        cursor = db.execute(sql)  # fresh prepare; no reused cursor or cached statement
        labels = [x[0] for x in cursor.description]
        raw_rows = cursor.fetchall()
        projected = [{k: row[k] for k in c["required_output"]} for row in raw_rows]
        return {"id": c["id"], "ok": True, "sql": sql, "output": projected,
                "reads": sorted(f"{t}.{col}" for t, col in reads), "error": None, "selected": labels}
    except sqlite3.Error as e:
        return {"id": c["id"], "ok": False, "sql": sql, "output": None,
                "reads": sorted(f"{t}.{col}" for t, col in reads), "error": f"{type(e).__name__}: {e}", "selected": []}
    finally:
        db.set_authorizer(None)

def observations(f: dict) -> list[dict]:
    """Probe active and inactive consumers with SQLite authorizer; record errors as missing evidence."""
    db = connection(f)
    try:
        return [dict(run_consumer(db, c), active=c["active"], kind=c["kind"], version=c["version"]) for c in f["consumers"]]
    finally:
        db.close()

def _snapshot(db: sqlite3.Connection, columns: list[str]) -> list[dict]:
    return [dict(row) for row in db.execute('SELECT ' + ', '.join('"'+c+'"' for c in columns) + ' FROM users ORDER BY id').fetchall()]

def execute_plan(f: dict, target: str, actions: list[dict], *, expected_version: str | None = None) -> dict[str, Any]:
    """Fresh SQLite per plan. Compare outputs and all retained column values, without swallowing errors."""
    started = time.perf_counter()
    validate_fixture(f)
    fixture_version = version_of(f)
    if expected_version is not None and expected_version != fixture_version:
        raise ValueError("Stale fixture/configuration version: re-observe and re-verify")
    if target not in ("users." + c for c in f["schema"]["users"]):
        raise ValueError("Unknown target in synthetic fixture")
    column = target.split(".", 1)[1]
    if column in ("id", "name"):
        raise ValueError("Protected critical identifier/contract field")
    if not isinstance(actions, list) or len(actions) > 8:
        raise ValueError("At most eight bounded actions")
    db = connection(f)
    latest_candidates=[c for c in f["consumers"] if c["active"] and c["kind"] == "web"]
    latest_id=max(latest_candidates,key=lambda c:tuple(int(x) if x.isdigit() else 0 for x in c["version"].split(".")))["id"] if latest_candidates else None
    try:
        original_cols = list(f["schema"]["users"])
        initial_rows = _snapshot(db, original_cols)
        baseline = {c["id"]: run_consumer(db, c) for c in f["consumers"] if c["active"]}
        consumers = copy.deepcopy(f["consumers"])
        sql_errors = []
        completed = []
        step_checks = []
        for action in actions:
            if not isinstance(action, dict) or action.get("type") not in ALLOWED_ACTIONS:
                raise ValueError("Unsupported plan action; no arbitrary SQL accepted")
            if action["type"] == "update_projection":
                if set(action) != {"type", "consumer_id", "remove_column"}:
                    raise ValueError("Invalid projection action shape")
                if action["remove_column"] != column:
                    raise ValueError("May only remove target column from projections")
                matching = [c for c in consumers if c["id"] == action["consumer_id"] and c["active"]]
                if len(matching) != 1:
                    raise ValueError("Unknown or inactive consumer in repair")
                consumer = matching[0]
                if column in consumer["required_output"]:
                    raise ValueError(f"Required output {consumer['id']}.{column} cannot be removed")
                if column not in consumer["projection"]:
                    raise ValueError(f"{consumer['id']} does not select {column}")
                consumer["projection"].remove(column)
                completed.append({"action": action, "detail": f"Updated controlled projection for {consumer['id']}"})
            elif action["type"] == "drop_column":
                if set(action) != {"type", "target"} or action["target"] != target:
                    raise ValueError("Invalid drop action or target")
                try:
                    db.execute(f'ALTER TABLE "users" DROP COLUMN "{column}"')
                    completed.append({"action": action, "detail": f"SQLite ALTER TABLE users DROP COLUMN {column} executed"})
                except sqlite3.Error as e:
                    sql_errors.append(f"{type(e).__name__}: {e}")
                    break
            # Check EVERY active contract after each individual step, not just final state.
            intermediate = {c["id"]: run_consumer(db, c) for c in consumers if c["active"]}
            step_passed = all(baseline[cid]["ok"] and intermediate[cid]["ok"]
                              and baseline[cid]["output"] == intermediate[cid]["output"] for cid in baseline)
            step_checks.append({"step": len(completed), "action": action, "passed": step_passed,
                                "failed_consumers": [cid for cid in baseline if not intermediate[cid]["ok"] or baseline[cid]["output"] != intermediate[cid]["output"]]})
            if not step_passed:
                break  # never endorse a plan that was unsafe between steps
        current_cols = [r[1] for r in db.execute("PRAGMA table_info('users')")]
        remaining_cols = [x for x in original_cols if x != column]
        after_rows = _snapshot(db, remaining_cols if column not in current_cols else original_cols)
        after = {c["id"]: run_consumer(db, c) for c in consumers if c["active"]}
        checks = []
        for cid, before in baseline.items():
            result = after[cid]
            ok = bool(before["ok"] and result["ok"] and before["output"] == result["output"])
            checks.append({"check": f"output:{cid}", "passed": ok, "before": before["output"],
                           "after": result["output"], "error": result["error"]})
        integrity = [{c: row[c] for c in remaining_cols} for row in initial_rows] == [{c: row[c] for c in remaining_cols} for row in after_rows]
        checks.append({"check": "all-records-and-unrelated-values", "passed": integrity,
                       "before": len(initial_rows), "after": len(after_rows)})
        change_applied = column not in current_cols
        checks.append({"check": "target-column-dropped", "passed": change_applied, "before": True, "after": change_applied})
        all_outputs = all(check["passed"] for check in checks if check["check"].startswith("output:"))
        required = [c["id"] for c in f["consumers"] if c["active"]]
        unresolved_outputs = [c["id"] for c in f["consumers"] if c["active"] and column in c["required_output"]]
        checks.append({"check": "no-intermediate-breakage", "passed": all(x["passed"] for x in step_checks),
                       "before": True, "after": all(x["passed"] for x in step_checks)})
        checks.append({"check": "all-required-consumers-executed", "passed": sorted(after) == sorted(required),
                       "before": required, "after": list(after)})
        verified = bool(all(c["passed"] for c in checks) and not sql_errors)
        return {"status": "verified" if verified else "unsafe", "verified": verified,
                "fixture_version": fixture_version, "target": target, "actions": actions, "applied": completed,
                "baseline": baseline, "after": after, "checks": checks, "step_checks": step_checks, "sql_errors": sql_errors,
                "duration_ms": round((time.perf_counter()-started)*1000, 2),
                "affected_sql_failures": [cid for cid in required if not after[cid]["ok"]],
                "all_required_consumers": required, "schema_after": current_cols,
                "unresolved_required_outputs": unresolved_outputs,
                "latest_only_would_pass": bool(latest_id and after.get(latest_id, {}).get("ok") and baseline.get(latest_id,{}).get("output")==after.get(latest_id,{}).get("output")),
                "latest_checked_consumer": latest_id,
                "blanket_reject": "No migration would be applied; cannot meet requested change"}
    finally:
        db.close()

def example_plans(target: str, f: dict) -> list[dict]:
    column = target.split(".")[-1]
    active = [c for c in f["consumers"] if c["active"] and column in c["projection"]]
    fixable = [c for c in active if column not in c["required_output"]]
    if not active:
        return [{"label":"Unused-field direct removal (SQL reference)",
                 "actions":[{"type":"drop_column","target":target}],"scope":"manual-reference"}]
    return [
        {"label": "Latest-version-only baseline (intentionally incomplete)", "actions": [{"type":"drop_column", "target":target}], "scope": "baseline"},
        {"label": "One-consumer repair (intentionally incomplete)", "actions": ([{"type":"update_projection", "consumer_id":fixable[0]["id"], "remove_column":column}] if fixable else []) + [{"type":"drop_column", "target":target}], "scope": "baseline"},
        {"label": "All repairable active consumers", "actions": [{"type":"update_projection", "consumer_id":c["id"], "remove_column":column} for c in fixable] + [{"type":"drop_column", "target":target}], "scope": "manual-reference"},
    ]
