# PROJECT_STATE | 18 Oct 2026 IST

## Current review checkpoint | 18 Oct 2026
- This ZIP includes an additional review in a separate Linux runtime with working package downloads. Earlier environment restrictions below describe the original authoring session.
- **Actual FalkorDB now tested:** official FalkorDBLite native binaries, engine 4.18.3, standard FalkorDB SDK 1.8.0, loopback TCP; no graph substitute. Docker execution itself remains untested.
- Full test suite with `RUN_LIVE_FALKOR=1`: **31 passed**. Real seed/traversal, active dependency mutation, missing observations, renamed worker/reseed, and independent-client audit persistence passed.
- Fixed the live acceptance script's dependency on system IANA timezone data (important for Windows), and `/api/history` now returns HTTP 503 for stale/incomplete graph evidence. Regression tests reproduced both failures before the fixes and pass afterward.
- Evidence: `evidence/real-graph-review-results.json` and `evidence/review-pytest-output.txt`. The persistence check is explicitly non-model and creates no agent-verified recommendation.
- **Remaining:** real LLM inference and the complete `scripts/live_end_to_end.py` run require a privately configured key. Actual Windows/Docker launch, full demo recording, public source publication, and submission remain undone.
- Participant next step: follow `START_HERE_WINDOWS.md` from this updated package. Preserve the current implementation; no rebuild is needed.

## Milestone 0: Environment inspection (6:34 PM IST)
- Initial workspace `/mnt/data/` had no supplied project, so created `/mnt/data/schemaguard/`.
- Authoring runtime: Python 3.13.5, SQLite 3.46.1, FastAPI/Uvicorn, pytest, httpx and OpenAI SDK available. Docker command, FalkorDB Python SDK, FalkorDB service, and `OPENAI_API_KEY` were unavailable. Local shell DNS was unavailable, so could not install/start FalkorDB or call a model.
- Official WeMakeDevs rules, FalkorDB SDK documentation, GitHub August 2025 incident and Liquibase 2026 report were read via web. Source links are in README.
- Attempted `python -m schemaguard.cli check`; result `ModuleNotFoundError: No module named 'falkordb'`. **No real Cypher execution in this environment.**

## Milestone 1: Actual disposable SQL replay (completed)
- `schemaguard/sqlcheck.py` implements SQLite schema/fixture, query execution, authorizer read capture, strict disabled DQS, output contracts, exact retained-row/value check, column-dropped check, per-step checks and a bounded allowlist.
- Verified drop-only breaks `web-v2` + `digest-worker-v1`; patch-only-one breaks worker; repairing both before drop passes. Unused `retired_flag` passes. Target-required output fixture returns unsafe/unresolved requirement.
- All replays use fresh `:memory:` SQLite DBs, real SQL, captured errors. Evidence at `evidence/verification-results.json`.

## Milestone 2: Graph / model implementation (code complete, live-connection blocked)
- `schemaguard/queries.py` has all executed Cypher for seeded graph, provenance, path retrieval, coverage, investigations, attempts and verification history.
- `schemaguard/graph.py` requires FalkorDB, checks coverage drift/observations, and makes graph read paths the UI graph source; no runtime fake graph.
- `schemaguard/agent.py` has one bounded OpenAI tool-calling agent with `inspect_change`, `find_affected_consumers`, `test_plan`, `record_recommendation`, limited rounds, restricted tools, deterministic verifier and graph result persistence. No live LLM was executed due absent credentials and network.
- `tests/test_graph_contract.py` uses **unit-only test doubles** and includes a mocked-model orchestration test. Real graph checks in opt-in `tests/test_live_falkor.py` are skipped until FalkorDB exists.

## Milestone 3: UI / run/verification (completed offline)
- `schemaguard/app.py` serves small HTML/CSS/JS investigation dashboard with allowlisted input, real graph SVG source paths, affected consumers, tool log, before/after SQL checks, recommendation, blocked/unsafe/unresolved/verified states and demo reset.
- `/api/demo/sql` is explicitly labelled non-agent offline diagnostic; graph-based `/api/investigate` fails closed when FalkorDB/model missing.
- HTTP server started at `127.0.0.1:8777` (test port), `/` returned 200, `/api/health` returned 200 with honest unavailable status, SQL endpoint returned `[unsafe,unsafe,verified]`, `/api/graph` returned 503 as required.
- The actual UI was browser-rendered in Chromium using the real source files plus an HTTP proxy to the running backend because the container forbids browser navigation. Screenshot captures and **offline-only** diagnostic recording are in `evidence/`; this is NOT proof of a live graph/LLM and not an acceptable full submission video.
- `python -m pytest -q`: **21 passed, 1 skipped**; `node --check schemaguard/static/app.js` passed. Exact results in `evidence/pytest-output.txt`.

## Milestone 4: Handoff files (completed)
- README, GRAPH_MODEL, VERIFICATION, SECURITY, AI_ASSISTANCE, TEAM_WALKTHROUGH, DEMO_SCRIPT, SUBMISSION, compose, .env.example, LICENSE, GitHub offline CI workflow, requirements and fixture variants created.
- Still blocked: live FalkorDB Cypher query (Docker/service/sdk missing), real LLM tool call (key absent), opt-in live graph persistence test, full contest video, public repository publication and actual portal submission.
- **Next concrete human action** on Windows: unzip, `docker compose up -d`, create venv, `pip install -r requirements.txt`, privately set `OPENAI_API_KEY` in `.env`, `python -m schemaguard.cli seed`, `python -m schemaguard.cli check`, `python -m pytest -q`, `python -m schemaguard.cli serve`. Then run investigation, review tool activity, record real full demo, publish repo and submit before 11:59 PM IST.
- Deadline target 11:00 PM IST to preserve final 59-minute submission buffer.

## Continuation checkpoint | 18 Oct 2026, 8:42 PM IST
- Resumed the existing ZIP in `/mnt/data/SchemaGuard`; original 21 passed / 1 skipped reproduced on this runtime.
- Confirmed `docker` absent, `127.0.0.1:6379` connection refused, `falkordb` SDK not installed; `pip install falkordb` could not resolve packages (no package network). No OPENAI_API_KEY present. No real graph traversal or model execution is possible **in this runtime without external services**.
- Read source, previous verification report, submission notes and UI. Planned targeted improvements: evidence-drift verification, persisted agent audits, separate UI counts, tighter live tests, refreshed report. Do not promote offline SQL reference plans into agent successes.

## Continuation milestone A | approximately 8:50 PM IST
- Implemented targeted modifications in original `schemaguard/{queries,graph,agent,app}.py` and `schemaguard/static/{app.js,index.html,styles.css}`. No interface rebuild.
- FalkorDB context now cross-checks current SQLite authorizer probe reads against both graph READS edges and graph-supported observation reads; omitted matched evidence cannot be interpreted as unused. UI active consumer list and path use Cypher-returned path rows.
- `Investigation` audit can persist actual bounded tool arguments/results and be read via `/api/investigations/{id}`. `/api/history` calculates graph-persisted verified agent recommendations for the exact fixture and target. These paths are NOT proven live here.
- `/api/summary` executes deterministic reference SQL cases for independent attribution. Dashboard shows separate `SQL REFERENCE PLANS PASSED` and `AGENT-VERIFIED RECOMMENDATIONS` counters, separate Graph/Model/Agent statuses, smaller hero, preservation summary, and clear fail-closed graph state.
- 26 passed, 1 skipped using test-only graph/model doubles; `node --check` passed. Local FastAPI `/api/health` and `/api/summary` returned real successful HTTP responses; summary shows two unsafe SQL reference attempts and one verified.
- Chromium local navigation is administratively blocked (`ERR_BLOCKED_BY_ADMINISTRATOR`), so browser UI was inspected using unmodified HTML/CSS/JS with API calls proxied from Playwright's Python host to real local FastAPI (no mocked API responses). It showed 3 actual SQL cards, SQL count 1, agent count unavailable and the correct blocked agent state. Screenshots in `evidence/ui-continuation-*.png`. This does not prove full graph/agent execution.
- Added `scripts/live_end_to_end.py` for real graph + two actual model investigations, changed worker/reseed, graph-persisted audit. Did NOT run complete path because OPENAI_API_KEY missing, and real graph service/sdk unavailable. Script exited 2 with truthful blocker.

## Continuation milestone B | approximately 9:00 PM IST
- New checks in graph context compare AFFECTED result vs active READS paths and re-probe evidence. `run_agent` rechecks graph freshness before SQLite testing and before saving a recommendation; availability loss blocks verification claims.
- Browser UI screenshot visually reviewed: compact layout, separate graph/model/agent status indicators; 1 SQL reference plan passed, agent verified count unavailable, graph empty with a truthful blocker. Browser navigation to localhost is forbidden here; host proxy routed unmodified frontend API requests to real FastAPI. Recorded a NEW short offline-only WebM after making local Playwright FFmpeg executable available; this is NOT acceptable as full graph/LLM demo proof.
- SQL reference plan for genuinely unused column now produces one actual direct-drop test instead of three misleading duplicate baselines.
- New acceptance script `scripts/live_end_to_end.py` performs original+renamed worker real graph and real LLM investigations and records actual results, or records a blocked attempt if one occurred. Both prerequisites absent here. `OPENAI_API_KEY=UNIT_TEST_ONLY python scripts/live_end_to_end.py` failed closed with `ModuleNotFoundError: falkordb`; no fake proof file created.
- Test suite now 28 passed, 1 skipped. Final report regenerated with 28 passed, 1 skipped; cleaned source ZIP prepared. Public repo and full working video still absent.
- Next action on Docker-enabled Windows participant machine: install requirements; privately set key; `docker compose up -d`; `python -m schemaguard.cli seed`; `check`; `python scripts/live_end_to_end.py`; open the dashboard and make genuine full screen recording; publish/submit.

## Continuation final checkpoint | 9:06 PM IST, 18 Oct 2026
- Restarted the FastAPI process after source changes (no hot reload), confirmed `/api/summary?target=users.retired_flag` returns ONE verified SQL reference plan (HTTP 200). `/api/summary?target=users.legacy_status` returns 1 of 3 reference plans passed. `/api/health` reports graph unavailable and model key missing.
- Final `python -m pytest -q`: 28 passed, 1 skipped; `node --check` passes; Python sources compiled; SQL reference cases executed; final `evidence/verification-results.json` regenerated. This is not real graph or model test evidence.
- FalkorDB still unavailable (no Docker/SDK, 6379 refused, PyPI inaccessible); `OPENAI_API_KEY` absent. Opt-in live SDK test skipped and real LLM agent call not performed. No public GitHub repository, no live deployment and no complete submission video.
- **For another session**: existing code is in `/mnt/data/SchemaGuard` (not only the old documentation-only `/mnt/data/schemaguard` directory). Latest ZIP is `/mnt/data/SchemaGuard_GraphHacks_2026_v2.zip`; the original old ZIP path has also been updated to current package. Next exact actions on Windows: `docker compose up -d`, install requirements, set local `.env` key, `python -m schemaguard.cli seed`, `check`, opt-in live test, `python scripts/live_end_to_end.py`, serve and record actual live agent UI, publish repository and submit.
- Do NOT claim live FalkorDB/model/agent-verified count in final demo until all those steps actually pass. When a future session receives new real evidence, update README/verification and ZIP, but do not rebuild the project.


## 10:30 PM onward, 18 Oct continuation
- Public repository work is on branch `evidence-challenge-2026-10-18` pending PR review; preserve unrelated main-branch work.
- Added a judge-controlled synthetic consumer, real-graph reseed guard, bounded exhaustive SQL candidate search, independent failure repro bundle, and staleness-aware persisted receipt.
- In local provided ZIP workspace, `python -m pytest -q`: **35 passed, 1 skipped** and JavaScript syntax checked. The live FalkorDB SDK, Docker, and OPENAI_API_KEY are missing from this runtime. The earlier 31-test real-graph result is historical evidence from a different environment.
- Still required: real FalkorDB run of newly changed queries, real model tool cycle, video capture, teammate review, portal submission. No invented live success.


## 18 October, 10:45 PM IST: final public integration checkpoint
- PR #1 merged into main: https://github.com/snigdha950/SchemaGuard/pull/1 ; merge commit `2c5459a8369b616298d1681cf802891a2cf91461`.
- **Real FalkorDB Docker service CI on the new source passed:** https://github.com/snigdha950/SchemaGuard/actions/runs/39148602558 . The new live receipt regression and previous real Cypher graph mutation test passed. This is graph and SQL integration, **not a live LLM**.
- GitHub offline CI also passed on the branch: https://github.com/snigdha950/SchemaGuard/actions/runs/39148605568 . Local executable check: 35 passed, 2 skipped (2 graph tests skipped locally without Docker).
- Downloadable source ZIP includes source, tests and instructions; full working-agent video remains unrecorded. Manual Actions workflow `Live graph and real model acceptance (manual only)` exists on main but has not run; it requires private repository Actions secret `OPENAI_API_KEY` and an approved tool-calling model.
- Next action before the demo: configure that secret, launch manual workflow, inspect real evidence artifact, open localhost interface to record authentic agent/tool graph interaction. Do not claim a working LLM until that run succeeds.


## 18 October, 11:05 PM IST: interface revision
- Existing FastAPI/HTML/JavaScript interface was refined rather than rebuilt. New warm off-white background, ink typography, muted green actions, quieter cards, readable diagnostic comparison, and judge challenge moved below graph and SQL findings.
- Corrected three misleading status treatments: completing deterministic SQL comparison, bounded candidate comparison, or demo reset no longer sets the overall notice to VERIFIED. An agent result remains separate.
- Local checks: 35 passed, 2 opt-in graph tests skipped; `node --check schemaguard/static/app.js` passed. Headless Chromium rendered desktop and phone layouts without JavaScript errors or 390px body overflow, using real FastAPI TestClient JSON injected because direct browser localhost navigation is administratively blocked in this environment.
- Screenshots are visual tests, not working FalkorDB/LLM recording. Live model execution and authentic browser demo remain pending.
