# Verification record and interpretation

## Latest additional review | 18 Oct 2026

**31 passed with `RUN_LIVE_FALKOR=1`**, including the real graph integration test. The review runtime is Linux, Python 3.12.14, SQLite 3.53.1, FalkorDB SDK 1.8.0, and FalkorDB engine 4.18.3 bundled by the official FalkorDBLite 0.10.0 package. A loopback TCP server loaded the actual native graph module; no graph double was substituted for these integration checks. Docker itself and execution on Windows were not tested.

Actual checks passed for seed, multi-hop traversal, active deployment changes, missing read observations, renamed worker/dependency reseeding, and persisted investigations/attempts/verifications/audits read through independent clients. A non-model persistence test correctly remains excluded from the agent recommendation count. Real SQLite reference plans remain unsafe / unsafe / verified.

Two regressions were reproduced before fixing: missing IANA timezone data crashed the acceptance script before its error handler, and an incomplete graph made `/api/history` raise a server error. The updated script uses a fixed IST offset; the API returns HTTP 503 for incomplete evidence. Both regression tests pass. The timezone test simulates missing data; it is not a Windows deployment test.

Evidence: `evidence/real-graph-review-results.json`, `evidence/review-pytest-output.txt`. **No real model calls occurred.** Earlier records below describe the original restricted authoring runtime and remain historical. A complete graph-to-model-to-verifier run and final video are still required.

Tests are run using actual SQLite, not prewritten answer labels. Read the machine-readable local evidence in `evidence/verification-results.json` and `evidence/pytest-output.txt` after regeneration.

## Key functional differences

1. Latest-version-only inspection would consider `web-v3` compatible after dropping `users.legacy_status` (pass); this is a false negative because `web-v2` and `digest-worker-v1` then raise SQLite `OperationalError` when selecting the removed field. The full verifier correctly returns unsafe.
2. Updating only `web-v2` first and dropping still raises an error in `digest-worker-v1` (unsafe).
3. Updating both affected active projections to omit `legacy_status`, *then* dropping, preserves the unchanged public outputs of all three active consumers, all row IDs, all retained unrelated column values, and the requested schema effect (verified).
4. `users.retired_flag` has no observed reads and safe removal verifies in the complete controlled fixture; missing probe evidence would block a graph-based investigation.
5. Reversed repair order is unsafe due to a per-step compatibility gate. A forced attempt to remove an output-required column from a worker projection is rejected.

## Policy comparison

| Policy | Outcome | Interpretation |
|---|---|---|
| Check only newest `web-v3` | Pass (false negative) | Does not cover other active deployments |
| Blanket reject all column drops | No migration attempted | Avoids this outage but prevents a safe completed change |
| Correct human-designed plan | Verified in same SQLite verifier | Matches safe sequence; no unjustified superiority claim |
| Agent-selected bounded plan | **Not yet tested with live model in authoring environment** | Requires real FalkorDB + API key |

## Verified vs unverified

- **Executed:** Python's in-memory SQLite queries and `sqlite3` authorizer callbacks, independent fresh-copy plans, output/data/schema assertions, FastAPI test-client checks and HTTP server responses, browser-rendered local SQL replay.
- **Test-double unit checks (not FalkorDB integration):** changed graph active deployment affects retrieved consumer set, missing observation causes incomplete, absent graph raises a blocker, absent model key blocks real agent.
- **Not executed in authoring environment:** `GRAPH.QUERY` against real FalkorDB; live model tool calls; opt-in integration test; backend restart persistence; public hosting; full submission video.

## Repeat exact checks

```bash
python -m pytest -q
python -m schemaguard.cli sql-demo
python -m schemaguard.cli seed   # needs real FalkorDB
python -m schemaguard.cli check  # needs real FalkorDB
```

`pytest -q` without the interpreter path may select a different Python environment. Prefer `python -m pytest -q` inside the chosen venv. Python 3.12+ is needed to disable SQLite DQS correctly.

## Continuation evidence | 18 Oct 2026 after 9 PM IST
- 28 passed, 1 live integration test skipped when running `python -m pytest -q`; report refreshed by `python scripts/verify_and_report.py`.
- Added offline tests: changed worker name/dependency, omission of both read edge and observation, inconsistent AFFECTED traversal, SQL/agent counters and missing-FalkorDB fail-closed HTTP 503.
- Backend `/api/summary` ran actual SQLite baselines, observed unsafe/unsafe/verified for target; `/api/health` returned `falkordb=unavailable`, `model=missing_api_key` as expected.
- Chromium showed real HTML/CSS/JS with browser fetch requests proxied to the actual running localhost FastAPI server because direct browser local navigation was administratively blocked. Screenshots `evidence/ui-continuation-sql.png`, `evidence/ui-continuation-agent-blocked.png` and short `evidence/continuation-offline-only.webm` **only** demonstrate the offline SQL UI + fail-closed model/graph route, not a working full agent.
- FalkorDB Python SDK install failed due to missing package DNS. Docker command unavailable, port 6379 refused connection; real Cypher/Python SDK integration unverified. No `OPENAI_API_KEY` configured, so no live model call or verified agent recommendation exists here.
- `python scripts/live_end_to_end.py` is ready for Docker + model key; do not cite its existence as an execution result. The tool stores actual real evidence only when invoked with those prerequisites.


## Later bounded challenge verification
New offline adversarial tests cover unseen worker names, inactive deployment, changed contract, no-read consumer, unsafe ordering, stale graph evidence, receipt version mismatch, partial graph write, and a portable SQL reproduction executed as a Python subprocess. `python -m pytest -q` locally yielded 35 passed, 1 skipped. CI on feature branch should be checked independently. Actual full LLM agent and new Cypher queries are NOT verified here.


## Confirmed real-service verification after improvements
- Actual FalkorDB service container, GitHub Actions run https://github.com/snigdha950/SchemaGuard/actions/runs/39148602558 : **success**, with real Cypher graph mutation/observation/receipts tests.
- GitHub offline Actions https://github.com/snigdha950/SchemaGuard/actions/runs/39148605568 : **success**. Local pytest: 35 passed and 2 opt-in FalkorDB tests skipped. Deterministic SQL reproduction ran in a fresh Python subprocess.
- **NOT VERIFIED:** real model tool-calling sequence, its real persisted recommendation, or full contest demo video. GitHub manual secret-backed acceptance workflow is prepared, not executed.
