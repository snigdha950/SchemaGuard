# Team rehearsal | 20–30 minutes

## Roles to understand, not merely memorize

One person explains the SQL fixture and output contracts. Another traces the FalkorDB Cypher path (Deployment → ConsumerVersion → Query → Column) and the read Observation. Another explains the LLM-selected tool interface, failure gating and why the verifier is separate. Anyone should be able to answer all of these.

## Walk through the bug

1. Read `fixtures/demo.json`. Identify latest `web-v3`, active older `web-v2`, and active `digest-worker-v1`. Say which fields each selects, and which outputs must remain identical (`id` and `name`).
2. Read `schemaguard/sqlcheck.py`: `connection`, `run_consumer`, `execute_plan`. Explain `SQLITE_READ`, the quote safety flag, fresh databases and per-step checks.
3. Run `python -m schemaguard.cli sql-demo`. Find the two real `OperationalError` failures from dropping `legacy_status`. Find the one remaining worker failure after patching only web-v2.
4. Examine `schemaguard/queries.py`: `ALL_PATHS`, `AFFECTED`, `OBSERVATION_COVERAGE`, `SAVE_AUDIT`. Observe the real graph with `python -m schemaguard.cli check` after `seed` (requires Docker). Point to an Observation and the matched configuration version.
5. Read `schemaguard/agent.py`: the LLM chooses tool calls, but `test_plan` invokes `sqlcheck` and never uses model-authored unrestricted SQL. Find where missing model key produces an explicit blocked state.
6. Use the UI to show the graph (requires FalkorDB), affected consumers, tool activity and recommended steps. Explain that SQL proof is a deterministic, separate baseline.

## Required hands-on fixture edit

Copy `fixtures/demo.json` to a backup. Change the worker's `id` from `digest-worker-v1` to `weekly-export-v6` (only the fixture, not hardcoded code). Run:

```bash
python -m schemaguard.cli sql-demo
python -m schemaguard.cli seed
python -m schemaguard.cli check
```

Expected: the failing consumer is now named `weekly-export-v6`; the graph's affected path changes after reseeding. The configuration hash changes. Now remove `legacy_status` from that worker's `projection`, reseed, and observe that only the older web deployment is affected. Restore `fixtures/demo.json` and reseed.

A teammate should make one actual source/test change and record it in `AI_ASSISTANCE.md`. Example: add a new fixture consumer selecting `legacy_status` without using it publicly, demonstrate the naive/partial/full results, and write a focused test for the changed fixture. This is a suggestion, not a claim that the change happened.

## Questions judges may ask

- **Why a graph?** The answer depends on a multi-hop active deployment → consumer version → query → column relationship and provenance; the live agent is blocked without it. This isn't a graphical decoration of Python data.
- **Where do edges come from?** Controlled SQL is executed with SQLite authorizer reads. The fixture declares deployments/projections; dynamic project-wide discovery is not claimed.
- **Can missing observation mean safe?** No. Current-version probe and read-edge reconciliation must pass.
- **What if output needs the column?** The bounded projection repair is forbidden, so a migration requirement remains unresolved.
- **What if the LLM makes up a patch?** The verifier validates action schema, reruns every required consumer after each step, compares outputs/data and checks schema; an unsafe action cannot become a verified recommendation.
- **Can this touch production?** No. Synthetic SQLite in-memory only, local project graph only, with allowlisted operations.

## Continuation-specific team acceptance (run live, not with mocked tools)
1. Read `evidence/verification-results.json` and explain why 28 offline passes do **not** imply an operational FalkorDB server or LLM.
2. Run `python scripts/live_end_to_end.py` on a connected machine. Open the generated real evidence file and locate the tool events, original affected graph paths, SQL results and renamed-worker paths. This exercise has NOT been performed in the authoring environment.
3. In the UI, explain the two different numeric counters: SQL reference successes vs FalkorDB-persisted agent successes. Disconnect the graph briefly and show that the agent fails closed rather than using fixture topology as a substitute.
4. For a meaningful hands-on contribution, add a new required active consumer in `fixtures/demo.json` that reads the target but doesn't expose it. Write and run a new assertion; reseed graph and confirm that the agent's needed projection update changes, then document the personal code change in `AI_ASSISTANCE.md`.
