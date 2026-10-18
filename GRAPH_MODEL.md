# FalkorDB graph model and query/evidence walkthrough

This product never uses a fake runtime graph. `schemaguard/queries.py` is the executed, parameterized Cypher source file. `GraphStore` uses FalkorDB's official Python client with `graph.query` and `graph.ro_query`.

## Nodes

- `Table {id}`: `users`.
- `Column {fqname, name}`: `users.legacy_status`, `users.retired_flag`, etc.
- `Deployment {id, active, environment}`: e.g. `deployment:web-v2`.
- `ConsumerVersion {id, version, kind, contract_json}`: versioned web/worker configurations.
- `Query {id, sql, projection_json}`: synthetic SQL generated from the version's declared projection.
- `Observation {id, kind, source, config_version, column?, ok?, error?}`: actual SQLite authorizer reads or complete SQL probe results; `source=sqlite.authorizer`.
- `Fixture {id, version, fixture_name}`: an SHA-derived binding to source manifest/records.
- `Investigation {id, target, config_version, state, created_at, model?, audit_json?, final_status?, completed_at?}`: query, actual bounded tool transcript (when model called), outcome and provenance.
- `Attempt {id, actions_json, fixture_version, status}` and `Verification {id, verified, result_json, fixture_version}`: persisted tested history.

## Directed relationships

`(Table)-[:HAS_COLUMN]->(Column)`

`(Deployment)-[:RUNS]->(ConsumerVersion)-[:EXECUTES]->(Query)-[:READS]->(Column)`

`(Observation)-[:SUPPORTS]->(Query)`

`(Investigation)-[:HAS_ATTEMPT]->(Attempt)-[:HAS_VERIFICATION]->(Verification)`

Observation's `column` property is set for the query-level read witness. A separately recorded passing `probe` observation proves the synthetic consumer was executed for the specified configuration, but **does not prove** dependencies on non-exercised branches of arbitrary code. No such branches are supported by the fixture.

## Critical retrieval

1. `PING`: `RETURN 1 AS ok`, executed through real FalkorDB. No automatic substitution if unavailable.
2. `ALL_PATHS`: follows `Deployment RUNS ConsumerVersion EXECUTES Query` then optionally `Query READS Column`. Used to create the frontend SVG and validate graph coverage.
3. `AFFECTED`: restricts active deployments to paths ending in `Column {fqname:$target}`, looks for matching current-version `Observation` and returns provenance.
4. `OBSERVATION_COVERAGE` + `READ_EVIDENCE`: ensure a current-version probe for every required active consumer and check that graph READS edges match recorded read observations. Fresh SQLite authorizer reads independently cross-check BOTH of those sets; an omitted read edge plus omitted observation still blocks a safe decision.
5. `RECENT_ATTEMPTS`: retrieves persisted tested attempts only for the exact target/configuration version; a new version must be reverified. `SAVE_AUDIT` stores the actual model tool events and result flags, and `INVESTIGATION_AUDIT` retrieves them. `VERIFIED_AGENT_RECOMMENDATIONS` counts distinct recommended+verified graph-linked investigations, independently from scripted SQL baselines. These Cypher paths still need live service execution.

Parameters are supplied to the SDK, never string-spliced from prompts. Identifiers and column names are allowlisted in `fixtures.py` and `sqlcheck.py`. The only data reset is to the explicitly named `schemaguard_*` graph.

## Evidence capture

`sqlite3.Connection.set_authorizer` records `SQLITE_READ` events while controlled SELECT statements are prepared/executed, using a fresh connection for probes. `SQLITE_DBCONFIG_DQS_DML=False` ensures a missing `"column"` cannot silently be interpreted as a string literal in SQLite. Observations are seeded with a configuration hash from `version_of`.

A `READS` edge is evidence-backed, but absence of an edge is not automatically negative evidence. A passing probe for each required consumer, hash matching, matching graph nodes/observations and expected active deployments is required. Missing or inconsistent evidence sets `state=incomplete` and blocks the agent. An altered active deployment in the graph changes the AFFECTED response but causes a fixture drift warning, not a false safe conclusion.

## Useful Cypher for the local FalkorDB Browser

```cypher
MATCH (d:Deployment {active:true})-[:RUNS]->(v:ConsumerVersion)-[:EXECUTES]->(q:Query)-[:READS]->(c:Column {fqname:'users.legacy_status'})
RETURN d.id, v.id, q.id, c.fqname
```

```cypher
MATCH (o:Observation)-[:SUPPORTS]->(q:Query)-[:READS]->(c:Column)
RETURN o.source, o.config_version, q.id, c.fqname LIMIT 20
```

Warning: `python -m schemaguard.cli seed` erases **only** the named project graph so the observations and version are consistent; do not place unrelated data in that graph.
