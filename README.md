# SchemaGuard

**Check what a database change will break before applying it.**

SchemaGuard investigates an allowlisted synthetic `ALTER TABLE users DROP COLUMN` operation. The graph of deployments, consumer versions, generated SQL queries and observed column reads resides in **real FalkorDB**. An LLM chooses bounded tools and proposes a repair sequence; a separate deterministic verifier executes actual SQL against fresh in-memory SQLite databases after *every* step and checks output contracts and retained data.

**Track:** Agents That Act on Connected Data (Graph Hacks: Context for AI Agents, WeMakeDevs × FalkorDB). **Not** entered in the Agent Memory and Coordination track.

**Source:** https://github.com/snigdha950/SchemaGuard · **Windows setup:** [START_HERE_WINDOWS.md](START_HERE_WINDOWS.md)

> **Latest review, 18 Oct 2026:** **31 tests passed with the actual FalkorDB integration test enabled.** A separate Linux runtime installed the official FalkorDBLite binaries and used the standard FalkorDB SDK over loopback TCP. Real Cypher traversal, dependency mutations, missing-evidence blocking, and audit persistence across independent clients passed. Two reproduced bugs were fixed: Windows startup without IANA timezone data and the history endpoint's incomplete-graph error. **Real model execution, Docker/Windows deployment, and a complete agent video remain unverified.** Configure a model key privately and run the full acceptance script before recording. Current evidence: `evidence/real-graph-review-results.json` and `evidence/review-pytest-output.txt`; earlier offline evidence remains historical. Start with `START_HERE_WINDOWS.md`.

## Quick start (Windows 11, PowerShell)

Prerequisites: Docker Desktop **with Linux containers**, Python **3.12+** (SQLite 3.35+), network access to install PyPI packages, and a permitted OpenAI API key for the live-agent feature. Docker Desktop need not be used for Python; the FastAPI app runs on your host.

```powershell
# Run from the extracted SchemaGuard directory
# Start Docker Desktop first. No Docker installed? Install Docker Desktop, reboot if requested.
docker compose up -d
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
# Set OPENAI_API_KEY=... privately in .env to enable model tools.
.\.venv\Scripts\python.exe -m schemaguard.cli seed
.\.venv\Scripts\python.exe -m schemaguard.cli check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m schemaguard.cli serve
```

Open **http://127.0.0.1:8000**. Select `legacy_status`, click **Replay SQL proof** (reference baselines), then **Run agent investigation** (requires connected graph + model). View FalkorDB Browser at http://127.0.0.1:3000 if desired. Do not put the key into chat or screenshots.

If `py -3.12` is not installed, use `py -3.13` or your Python 3.12+ executable. PowerShell activation policy can be avoided with ` .\.venv\Scripts\python.exe -m ... ` and ` .\.venv\Scripts\python.exe -m pip install -r requirements.txt `.

### macOS / Linux

```bash
docker compose up -d
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env to configure a private OPENAI_API_KEY
python -m schemaguard.cli seed
python -m schemaguard.cli check
python -m pytest -q
python -m schemaguard.cli serve
```

The app binds to `127.0.0.1:8000`, not a public interface. No live customer database is contacted or changed. The Docker graph service binds on host `127.0.0.1:6379` and is only a demo configuration, not hardened for untrusted networks. The `seed` and `reset` operations wipe only the named `schemaguard_*` graph. Never point them at valuable data.

### Without Docker / model credentials

```powershell
python -m schemaguard.cli sql-demo
python -m schemaguard.cli serve
```

The SQL replay still runs and the UI labels it **deterministic offline diagnostic**, not an agent or graph-backed investigation. `Run agent investigation` will return `503 blocked`; no Python adjacency-list fallback is used. For FalkorDB Cloud, set `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_PASSWORD` and `FALKORDB_SSL=true` (plus `FALKORDB_USERNAME` if specified by the provider) in `.env`. The Python SDK supports TLS; this environment has not tested a cloud endpoint. Do not disable TLS for a public remote instance.

## Demo scenario

- `web-v3` (latest) selects `id, name, email` and remains compatible after `legacy_status` is dropped.
- `web-v2` (active older deployment) uses an **ORM-style projection simulation** selecting `legacy_status`, although its public output is just `id, name`.
- `digest-worker-v1` (active background consumer) also selects `legacy_status` without requiring it in its output contract.
- `preview-v4` is explicitly inactive, but its dependency still appears in the graph.
- `retired_flag` is genuinely unused by every controlled query.

The contracts (required `id, name` output from each active consumer, source-row IDs, and retained unrelated column values) are declared **before** any plan generation in `fixtures/demo.json`. The records are synthetic. The SQL replay compares: (1) naive drop, (2) one partial projection repair then drop, (3) both projection repairs then drop. The third is a **manual reference plan**, not an invented agent action. The current model, if configured, can separately choose its own plan through tools.

## Architecture

```text
User / FastAPI interface
    |-- /api/graph --> real FalkorDB (deployments, observed SQL READS, evidence paths)
    |-- /api/investigate --> real LLM tool-calling loop
    |      inspect_change -> find_affected_consumers -> test_plan -> record_recommendation
    |                                 |                |
    |                          FalkorDB Cypher         +-- isolated SQLite verification
    |                                 |                     with per-step safety gates
    |                                 +-- observations/coverage
    |-- /api/demo/sql --> deterministic reference replays; no graph/LLM claim
    |-- /api/summary --> executed reference outcomes, independent of model
    |-- /api/history --> version-scoped graph attempts + agent-verified count
    +-- /api/investigations/{id} --> persisted actual tool-event audit
```

Graph Cypher in `schemaguard/queries.py`; graph schema and evidence discipline in `GRAPH_MODEL.md`. A user-edited `fixtures/demo.json` changes the SHA-256-short version. Reseed to regenerate executed observations. `GraphStore.context()` compares graph deployments, probe coverage, all READS edges and observation records to the fixture version. Graph disagreement or a missing observation blocks model investigations, it never means “safe”. Even matching omissions of a READS edge **and** its read Observation are detected by comparing actual current SQL authorizer reads without substituting those reads for the graph topology. The graph and visible impact diagram are generated from the **same graph-retrieved paths**. Model credentials stay server-side.

### Model safety and verifier separation

OpenAI chat tool-calling (`schemaguard/agent.py`) chooses tools with an iteration/attempt cap; it cannot execute shell commands or unrestricted SQL. Allowed changes are only `update_projection(consumer_id, remove_column)` and `drop_column(users.column)` against synthetic allowed fields. `schemaguard/sqlcheck.py` independently constructs SQLite databases and validates *every* required active consumer after every step; baseline and post-state output contracts must match, including all rows and unrelated values. Dropping before repairing is marked unsafe. A model never sets a verification pass flag.

If a required consumer output genuinely needs the removed column, the allowed projection update is rejected; a changed business contract or an alternative migration is necessary. More generally, SQL support is SQLite-only. No automated repository scanning, actual ORM introspection, production readiness, multi-engine migration guarantee, or large-scale performance evidence is claimed.

## Commands / tests

```bash
python -m schemaguard.cli status        # reports connectivity/configured-vs-missing, not secrets
python -m schemaguard.cli check         # real Cypher PING and path traversal + coverage
python -m schemaguard.cli seed          # re-observe SQL & replace only scoped demo graph
python -m schemaguard.cli sql-demo      # print deterministic actual SQL checks
python -m schemaguard.cli sql-demo --target users.retired_flag
python -m pytest -q                   # default excludes the opt-in graph integration test
node --check schemaguard/static/app.js
python scripts/verify_and_report.py     # update evidence report without pretending LLM ran
```

The optional `RUN_LIVE_FALKOR=1 python -m pytest tests/test_live_falkor.py -v` tests **real** Cypher paths, missing observations, renamed worker reseeding, a persisted audit record and a fresh graph-client session. It re-seeds and destructively mutates **only the named project demo graph**, so do not run it against any other graph. It is not part of the offline test claims.

## Complete live acceptance, only after both prerequisites are configured

On Windows, from the project root in activated PowerShell:

```powershell
# First verify Docker Desktop is running and the SDK was installed
python -m schemaguard.cli seed
python -m schemaguard.cli check
$env:RUN_LIVE_FALKOR = "1"
python -m pytest tests/test_live_falkor.py -v
Remove-Item Env:RUN_LIVE_FALKOR
python scripts/live_end_to_end.py
python -m schemaguard.cli serve
```

`python scripts/live_end_to_end.py` makes **actual** OpenAI tool calls and executes Cypher/SQLite; it requires a model key and will return a blocker instead of fabricating output. It tests the original hidden consumer and a renamed worker with removed dependency, and saves full real tool events, SQL results, evidence/version and outcome in `evidence/live-falkordb-agent-results.json` **only if the end-to-end live checks succeed**. It temporarily replaces the synthetic demo graph during testing and restores the original seed afterward. Do not confuse the saved report from this script with a screenshot of the SQL-only baseline.

**Practical troubleshooting:** `ModuleNotFoundError: falkordb` means install requirements into the same Python environment used to launch. `Connection refused` means start Docker Desktop and `docker compose up -d`, then inspect `docker compose ps` and `docker compose logs falkordb --tail 80`. `Missing/stale graph seed` means run `python -m schemaguard.cli seed`; missing/failed observations must be investigated, not ignored. A missing or invalid model key means set it privately in `.env`; the UI's **Model: key present** indicator means only configuration is detected, never that an inference succeeded.

**Dashboard counters:** “SQL reference plans passed” comes only from `/api/summary` (deterministic real SQLite). “Agent-verified recommendations” is a separate count of version-matched investigations with a model-recorded recommendation and verifier-backed `Verification` in FalkorDB. When disconnected it shows “—”, not an invented zero. Agent execution status is shown separately.

## Comparison / originality

A latest-version-only check passes `web-v3` yet misses two active failures. A blanket ban on drops prevents this change entirely. The correctly constructed manual three-step plan matches the successful verified sequence. This prototype's contribution is not a new migration technique: it combines graph-based cross-version dependency investigation, observed SQL read evidence, bounded agent decisions, actual compatibility replay and traceable checks in one interface. This is a synthetic engineering demonstration, not an outcome/savings study.

Real-world motivation: GitHub's [August 2025 availability report](https://github.blog/news-insights/company-news/github-availability-report-august-2025/) documents ORM references left behind during column removal. [Liquibase's 2026 governance survey](https://www.liquibase.com/resources/reports/2026-state-of-database-change-governance-report) describes survey respondents, not SchemaGuard users or benefits. Existing migration/compatibility tools include Liquibase, Flyway, gh-ost, expand-and-contract rollouts and schema contract testing. We claim neither novelty of those patterns nor production prevention rates.

## Files

- `schemaguard/sqlcheck.py`: actual SQLite authorizer observations, controlled migrations, contracts and checks.
- `schemaguard/graph.py`, `schemaguard/queries.py`: real FalkorDB setup, traversal, evidence coverage and persisted attempts.
- `schemaguard/agent.py`: bounded tool-calling model; separate from the verifier.
- `schemaguard/app.py`, `schemaguard/static/`: served interface and HTTP endpoints.
- `tests/`: focused tests, including opt-in real FalkorDB suite.
- `fixtures/demo.json`: user-editable synthetic records, deployments and output contracts.
- `scripts/live_end_to_end.py`: opt-in real-service acceptance recording script; no fake graph/model.
- `evidence/`: local verification report, refreshed continuation screenshots and offline diagnostic recording (not full submission demo).
- The GitHub source contains text verification evidence. Historical offline-only screenshots and recordings remain in the downloadable source ZIP; they are not the working-agent submission video.
- `PROJECT_STATE.md`, `GRAPH_MODEL.md`, `VERIFICATION.md`, `AI_ASSISTANCE.md`, `TEAM_WALKTHROUGH.md`, `DEMO_SCRIPT.md`, `SUBMISSION.md`: handoff.

## Hackathon rule references

[WeMakeDevs rules](https://www.wemakedevs.org/hackathons/falkordb/rules) · [Overview](https://www.wemakedevs.org/hackathons/falkordb) · [FalkorDB docs](https://docs.falkordb.com/) · [FalkorDB Python SDK](https://github.com/FalkorDB/falkordb-py)

### Optional unresolved-output fixture

`fixtures/required_output.json` contains a worker whose public output **really requires** `legacy_status`. For a standalone SQL check run `python -m schemaguard.cli sql-demo --fixture fixtures/required_output.json`; the repair cannot be verified without redesigning that output. To view this in the app, back up `fixtures/demo.json`, copy the required-output JSON over it, run `seed`, and restore/reseed afterward. `Reset demo` restores the default fixture.

On Windows PowerShell, opt in to the destructive-to-demo-graph integration test with:

```powershell
$env:RUN_LIVE_FALKOR = "1"
python -m pytest tests/test_live_falkor.py -v
Remove-Item Env:RUN_LIVE_FALKOR
```

The fixture/configuration hash includes the canonical fixture JSON, the SQLite library version, and the declared verifier policy version, so rerunning under a different SQLite version requires reseeding/reverification.


## 18 October judge challenge and bounded proof tools

The existing dashboard now supports a judge-controlled **synthetic consumer** with an arbitrary safe name. Click **Reobserve in FalkorDB** to execute its controlled SQLite read, reseed the real FalkorDB dependency graph, and update the fixture only when evidence is complete. If the new worker requires the removed field in its public output, the bounded repair remains unresolved. This is not arbitrary repository or ORM discovery.

**Deterministic utilities (not an LLM):** `GET /api/compare` enumerates projection-repair subsets (at most five repairable active consumers) followed by a final column drop. The minimum operation count is only within this bounded search space. `POST /api/reproduction` accepts a tested allowed plan and returns a ZIP with `repro.py` plus captured SQL, expected outputs, observed failure and fixture. Unzip and run `python repro.py`.

**Agent:** may call the `compare_bounded_plans` tool, but must separately choose and `test_plan` then `record_recommendation`. A two-phase persisted-audit check prevents an unfinished graph write from being counted as an agent success. `GET /api/receipt/<investigation_id>` refreshes evidence from real FalkorDB and withdraws current VERIFIED status on graph/fixture/verifier changes. Historical investigations remain stored when reseeding the project-scoped graph.

**NOT YET PROVEN ON THIS ITERATION:** actual LLM execution and new receipt queries against live FalkorDB; run `python scripts/live_end_to_end.py` with real Docker graph and private `OPENAI_API_KEY` before recording or claiming completed agent operation.


## Interface refresh (18 Oct)
The existing workbench now uses restrained paper/ink/teal styling with a smaller introduction and the primary investigation panels ahead of the judge challenge. Its reference summary shows three **actually executed SQLite** cases: missed older consumers, a failed partial fix, and the complete passing manual reference. These are not credited to the LLM. See [DESIGN_NOTES.md](DESIGN_NOTES.md). The backend architecture, fixtures, graph requirements and verifier are unchanged.
