"""FalkorDB only. Unavailable graph means no new investigation or false success."""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from .fixtures import version_of, validate_fixture
from .sqlcheck import observations
from . import queries as Q

class GraphUnavailable(RuntimeError):
    pass

class GraphEvidenceIncomplete(RuntimeError):
    pass

class GraphStore:
    def __init__(self, connector=None):
        if connector is not None:
            self.graph = connector
            return
        from falkordb import FalkorDB
        params = {"host": os.getenv("FALKORDB_HOST", "127.0.0.1"),
                  "port": int(os.getenv("FALKORDB_PORT", "6379")),
                  "socket_timeout": 3, "socket_connect_timeout": 3}
        if os.getenv("FALKORDB_PASSWORD"):
            params["password"] = os.getenv("FALKORDB_PASSWORD")
        if os.getenv("FALKORDB_USERNAME"):
            params["username"] = os.getenv("FALKORDB_USERNAME")
        if os.getenv("FALKORDB_SSL", "false").lower() in ("true", "1", "yes"):
            params["ssl"] = True
        self.db = FalkorDB(**params)
        graph_id = os.getenv("FALKORDB_GRAPH", "schemaguard_demo")
        if not graph_id.startswith("schemaguard_") or not graph_id.replace("_", "").isalnum():
            raise ValueError("FALKORDB_GRAPH must be named schemaguard_<safe-id>")
        self.graph = self.db.select_graph(graph_id)

    def query(self, statement: str, params: dict | None = None, read: bool = False):
        try:
            run = self.graph.ro_query if read else self.graph.query
            return run(statement, params or {}, timeout=3000).result_set
        except Exception as exc:
            raise GraphUnavailable(f"FalkorDB query unavailable ({type(exc).__name__}): check host/port, service, and graph module") from exc

    def ping(self):
        return self.query(Q.PING)[0][0] == 1

    def seed(self, fixture: dict) -> dict:
        """Explicit reset for graph named schemaguard_* only. Real probe results used for READS edges."""
        validate_fixture(fixture)
        self.ping()
        version = version_of(fixture)
        probes = observations(fixture)
        if any(not p["ok"] for p in probes):
            raise GraphEvidenceIncomplete("Seed probe has SQL error; do not claim complete dependency evidence")
        self.query(Q.CLEAR_SCOPED_GRAPH)
        self.query(Q.META, {"version": version, "fixture_name": fixture["fixture_name"]})
        self.query(Q.SEED_TABLE)
        for column in fixture["schema"]["users"]:
            self.query(Q.SEED_COLUMN, {"fqname": "users." + column, "name": column})
        for c, probe in zip(fixture["consumers"], probes):
            cid = c["id"]
            qid = "query:" + cid
            self.query(Q.SEED_CONSUMER, {
                "deployment_id": "deployment:" + cid, "active": c["active"],
                "environment": "synthetic-demo", "consumer_id": cid, "kind": c["kind"],
                "consumer_version": c["version"], "contract_json": json.dumps(c["required_output"]),
                "query_id": qid, "projection_json": json.dumps(c["projection"]), "sql": probe["sql"]})
            self.query(Q.SEED_PROBE, {"query_id": qid, "observation_id": f"probe:{version}:{cid}",
                       "config_version": version, "ok": probe["ok"], "error": probe["error"] or ""})
            for column in probe["reads"]:
                self.query(Q.SEED_READ, {"query_id": qid, "fqname": column,
                           "observation_id": f"read:{version}:{cid}:{column}", "config_version": version})
        return {"fixture_version": version, "consumer_count": len(probes),
                "observed_reads": sum(len(p["reads"]) for p in probes)}

    def context(self, f: dict, target: str) -> dict:
        """Graph returns all paths + impacted nodes; guards observe completeness and fixture drift."""
        self.ping()
        version = version_of(f)
        meta = self.query(Q.GET_VERSION, read=True)
        if len(meta) != 1 or meta[0][0] != version:
            raise GraphEvidenceIncomplete("Missing/stale graph seed: run python -m schemaguard.cli seed and retry")
        paths = self.query(Q.ALL_PATHS, read=True)
        columns = [r[0] for r in self.query(Q.ALL_COLUMNS, read=True)]
        impact = self.query(Q.AFFECTED, {"target": target, "version": version}, read=True)
        coverage = self.query(Q.OBSERVATION_COVERAGE, {"version": version}, read=True)
        reads = self.query(Q.READ_EVIDENCE, {"version": version}, read=True)
        expected_active = {c["id"] for c in f["consumers"] if c["active"]}
        active_graph = {p[3] for p in paths if bool(p[1])}
        issues = []
        if set(columns) != {"users."+col for col in f["schema"]["users"]}:
            issues.append("Column nodes disagree with fixture schema; evidence incomplete")
        if active_graph != expected_active:
            issues.append("Active consumer set differs between graph deployments and fixture; refresh/review evidence")
        coverage_ids = {r[0] for r in coverage if r[2] is not None and bool(r[3])}
        if coverage_ids != expected_active or len(coverage) != len(expected_active):
            issues.append("Missing/failed SQLite probe observation for an active consumer")
        graph_reads = {(p[3], p[7]) for p in paths if bool(p[1]) and p[7] is not None}
        observed_reads = {(r[0], r[1]) for r in reads if r[1] is not None and r[2] is not None}
        if graph_reads != observed_reads:
            issues.append("Graph READS edges disagree with stored authorizer evidence; graph mutation requires re-observation")
        # Current fixture probes are an independent anti-omission guard. Their results
        # never construct the UI graph or impacted consumer list, which use only Cypher.
        current_probes = observations(f)
        expected_reads = {(p["id"], col) for p in current_probes if p["active"] for col in p["reads"]}
        if any(not p["ok"] for p in current_probes if p["active"]):
            issues.append("Current SQLite active consumer probe failed")
        if graph_reads != expected_reads or observed_reads != expected_reads:
            issues.append("FalkorDB read evidence does not match fresh SQLite authorizer probes for this configuration")
        expected_impact = {cid for cid, col in graph_reads if col == target}
        actual_impact = {r[2] for r in impact}
        if expected_impact != actual_impact:
            issues.append("Affected-traversal result disagrees with active graph READS paths")
        if any(r[6] is None or r[7] != 'sqlite.authorizer' or r[8] != version for r in impact):
            issues.append("Affected edge has no matching current-version read observation")
        # Graph-based path visualization, never rebuilt from the manifest.
        nodes: dict[str, dict] = {}
        links: dict[tuple[str,str], dict] = {}
        impacted = {r[2] for r in impact}
        for d_id, active, env, v_id, kind, v_ver, q_id, col in paths:
            dn, vn, qn = "d:"+str(d_id), "v:"+str(v_id), "q:"+str(q_id)
            nodes[dn] = {"id": dn, "label": str(d_id).replace("deployment:", ""), "type": "deployment", "active": active}
            nodes[vn] = {"id": vn, "label": str(v_id), "type": "consumer", "active": active, "affected": v_id in impacted}
            nodes[qn] = {"id": qn, "label": str(q_id).replace("query:", "SELECT "), "type": "query", "active": active, "affected": v_id in impacted}
            for a, b, rel in [(dn, vn, "RUNS"), (vn, qn, "EXECUTES")]:
                links[(a,b)] = {"source":a, "target":b, "type":rel, "affected":v_id in impacted and bool(active)}
            if col is not None:
                cn = "c:" + str(col)
                nodes[cn] = {"id":cn, "label":str(col), "type":"column", "affected":col == target}
                links[(qn,cn)] = {"source":qn, "target":cn, "type":"READS", "affected":v_id in impacted and col == target and bool(active)}
        for column_name in columns:
            cid = "c:" + column_name
            nodes.setdefault(cid, {"id":cid, "label":column_name, "type":"column", "affected": column_name == target})
        affected = [{"deployment":r[0],"environment":r[1],"consumer":r[2],"kind":r[3],"version":r[4],
                     "query":r[5],"observation":r[6],"source":r[7],"config_version":r[8]} for r in impact]
        seen_consumers = {}
        probe_by_id = {r[0]:r[2] for r in coverage if r[2] is not None}
        for d_id, active, env, v_id, kind, v_ver, q_id, _ in paths:
            if bool(active):
                seen_consumers[v_id] = {"deployment":d_id,"environment":env,
                    "consumer":v_id,"kind":kind,"version":v_ver,"query":q_id,
                    "affected":v_id in impacted,"probe_observation":probe_by_id.get(v_id),
                    "config_version":version}
        return {"target":target,"fixture_version":version,"affected":affected,
                "active_consumers":sorted(seen_consumers.values(), key=lambda c:c['consumer']),
                "graph":{"nodes":list(nodes.values()),"edges":list(links.values())},
                "coverage":{"active_consumers":sorted(active_graph),"probed_consumers":sorted(coverage_ids),
                            "read_edges":len(graph_reads),"observed_reads":len(observed_reads),"issues":issues},
                "state":"incomplete" if issues else "complete"}

    def create_investigation(self, investigation_id: str, target: str, version: str, evidence_digest: str = "", verifier_version: str = ""):
        self.query(Q.CREATE_INVESTIGATION, {"id":investigation_id,"target":target,"version":version,
            "state":"investigating","created_at":datetime.now(timezone.utc).isoformat(),
            "evidence_digest":evidence_digest,"verifier_version":verifier_version})

    def record_attempt(self, investigation_id: str, attempt_id: str, result: dict):
        # Limit persisted results (actual errors/checks/paths, no secrets or raw user data).
        subset = {k:result[k] for k in ("status", "checks", "step_checks", "sql_errors",
            "affected_sql_failures", "unresolved_required_outputs", "schema_after", "all_required_consumers",
            "fixture_version", "duration_ms")}
        serialized=json.dumps(subset)
        if len(serialized)>64000:
            raise GraphEvidenceIncomplete("Verification evidence too large to store without truncation")
        self.query(Q.CREATE_ATTEMPT, {"investigation_id":investigation_id,"attempt_id":attempt_id,
            "actions_json":json.dumps(result["actions"]), "version":result["fixture_version"],
            "status":result["status"], "verification_id":"verification:"+attempt_id,
            "verified":result["verified"], "result_json":serialized})

    def recommendation(self, investigation_id: str, state: str, attempt_id: str, recommendation: str):
        self.query(Q.SAVE_RECOMMENDATION,{"id":investigation_id, "state":state,
            "attempt_id":attempt_id, "recommendation":recommendation[:1400]})

    def save_audit(self, investigation_id: str, model: str, status: str, events: list[dict]):
        # Never store credentials, full model prompts or raw secrets. Each event is
        # an actual bounded tool call/result, limited to the synthetic fixture.
        payload = json.dumps(events, default=str)
        if len(payload)>120000:
            raise GraphEvidenceIncomplete("Tool audit too large to store without losing evidence")
        self.query(Q.SAVE_AUDIT, {"id": investigation_id, "model": model, "status": status,
            "audit_json": payload, "completed_at": datetime.now(timezone.utc).isoformat()})

    def confirm_recommendation(self, investigation_id: str, state: str, attempt_id: str) -> bool:
        rows=self.query(Q.CONFIRM_RECOMMENDATION,{"id":investigation_id},read=True)
        return len(rows)==1 and rows[0][0]==state and rows[0][1]==state and rows[0][2]==attempt_id and bool(rows[0][3])

    def verified_recommendations(self, fixture: dict, target: str) -> int:
        # Fail closed when version/corroboration cannot be checked.
        ctx = self.context(fixture, target)
        if ctx["state"] != "complete":
            raise GraphEvidenceIncomplete("Graph coverage incomplete: verified recommendation count unavailable")
        from .challenges import evidence_digest, VERIFIER_VERSION
        rows = self.query(Q.VERIFIED_AGENT_RECOMMENDATIONS,
                          {"version": ctx["fixture_version"], "target": target, "evidence_digest":evidence_digest(ctx), "verifier_version":VERIFIER_VERSION}, read=True)
        return int(rows[0][0]) if rows else 0
