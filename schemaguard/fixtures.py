"""Small, owned, synthetic fixtures; not a repository scanner or full ORM."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from copy import deepcopy

DEFAULT = {
    "fixture_name": "legacy_status_hidden_consumer",
    "schema": {
        "users": ["id", "name", "email", "legacy_status", "retired_flag"],
    },
    "rows": [
        {"id": 1, "name": "Asha", "email": "asha@example.test", "legacy_status": "old", "retired_flag": 0},
        {"id": 2, "name": "Dev", "email": "dev@example.test", "legacy_status": "new", "retired_flag": 1},
        {"id": 3, "name": "Mira", "email": "mira@example.test", "legacy_status": "old", "retired_flag": 0},
    ],
    "consumers": [
        {"id": "web-v3", "kind": "web", "version": "3.0", "active": True,
         "projection": ["id", "name", "email"], "required_output": ["id", "name"],
         "note": "latest web version; reads no legacy_status"},
        {"id": "web-v2", "kind": "orm-style-simulation", "version": "2.4", "active": True,
         "projection": ["id", "name", "email", "legacy_status"], "required_output": ["id", "name"],
         "note": "older deployed version; SELECT list generated from model projection"},
        {"id": "digest-worker-v1", "kind": "worker", "version": "1.3", "active": True,
         "projection": ["id", "name", "legacy_status"], "required_output": ["id", "name"],
         "note": "background job with stale SELECT"},
        {"id": "preview-v4", "kind": "web", "version": "4.0", "active": False,
         "projection": ["id", "legacy_status"], "required_output": ["id"],
         "note": "inactive experimental preview; not required"},
    ],
}

def fixture_copy() -> dict:
    return deepcopy(DEFAULT)

def version_of(fixture: dict) -> str:
    return hashlib.sha256(json.dumps({"fixture":fixture, "sqlite_version":sqlite3.sqlite_version,
        "verifier_policy":"bounded-projection-v2-per-step-dqs-strict"},sort_keys=True,separators=(",", ":")).encode()).hexdigest()[:16]

def validate_fixture(f: dict) -> None:
    if set(f.get("schema", {})) != {"users"}:
        raise ValueError("Only one synthetic 'users' table is allowed")
    columns = f["schema"]["users"]
    if not isinstance(columns, list) or not columns or len(columns) != len(set(columns)):
        raise ValueError("Invalid users columns")
    allowed = {"id", "name", "email", "legacy_status", "retired_flag"}
    if set(columns) - allowed or not {"id", "name"}.issubset(columns):
        raise ValueError("Unsupported column definitions")
    if not f.get("rows") or any(set(r) != set(columns) for r in f["rows"]):
        raise ValueError("Records must have the entire declared schema")
    names = [c["id"] for c in f["consumers"]]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate consumer ID")
    import re
    for c in f["consumers"]:
        if not re.fullmatch(r"[a-zA-Z][\w-]{0,63}", c["id"]):
            raise ValueError("Unsafe consumer ID")
        if not set(c["required_output"]).issubset(c["projection"]) or not set(c["projection"]).issubset(columns):
            raise ValueError("Invalid consumer projection or output")
        if not isinstance(c["active"], bool):
            raise ValueError("active must be boolean")
