# Full working demo recording script (2–3 minutes)

**Recording is a human task until Docker + FalkorDB + model API have been connected and the entire live agent route is verified.** The `evidence/` offline recording is not the contest's required full demo.

Before recording: run Docker Desktop, `docker compose up -d`, install requirements, configure private `OPENAI_API_KEY`, run `python -m schemaguard.cli seed`, `python -m schemaguard.cli check`, `python -m schemaguard.cli serve`. Confirm the three distinct top-right indicators: **Graph: connected_real_cypher**, **Model: key present, untested**, and after the investigation **Agent: verified**. A key-present indicator is NOT a successful model request. First run `python scripts/live_end_to_end.py` and read the real evidence file. Do a practice run to ensure the LLM actually records a tested recommendation. Close environment/config panels before screen recording.

**0:00–0:20 | Problem.** "The newest app has stopped using a column, but older deployments or workers might still select it. SchemaGuard checks which consumers break before the column is removed." Show the proposed change `users.legacy_status`.

**0:20–0:48 | Real graph and agent.** Click **Run agent investigation**. The agent must finish with actual tool activity and a verifier-backed recommendation; do not fake a pass. Show the live graph. Trace `deployment:web-v2` → `web-v2` → `query:web-v2` → `users.legacy_status` and the second worker path. Hover or read the observation labels. State that the graph comes from FalkorDB queries and observed SQLite authorizer reads.

**0:48–1:25 | Failure evidence.** Click **Replay SQL proof**. Explain that these are intentionally tested deterministic reference baselines, not claims about what the LLM proposed. Show first drop causing two actual `OperationalError` failures. Show one repair still leaving the worker failing; latest-version-only passes but misses both.

**1:25–2:10 | Checked remediation.** Show the full repair reference sequence and output checks, then click **Run agent investigation** again to show its *actual* chosen tool calls, tested attempts and evidence-linked recommendation. Expand `test_plan` and demonstrate exact per-step output contracts and schema change. If the agent fails to verify, do not present it as verified. Highlight that per-step outputs, retained data and dropped schema must all pass.

**2:10–2:35 | Safe and blocked cases.** Change target to `users.retired_flag` and show no affected paths and safe SQL removal. Explain missing graph or evidence blocks the real agent. Do not deliberately disable Docker during recording if it risks recording time.

**2:35–2:50 | Limits and track.** "This supports synthetic SQLite fixtures and bounded projection changes, not production schema migration. The submission is to Agents That Act on Connected Data." Show source README, public repository link if created, and close.

Recording requirements: actual running app on the team's machine, video and source repo accessible to judges. Use OBS, Xbox Game Bar, or another real screen recorder. Never replace with simulated/generated UI footage.

## Evidence and filming checklist
- First make sure the agent attempt says **Agent: verified**. Don't record a failed request and narrate it as a pass.
- Under tools, show inspect_change → find_affected_consumers → test_plan → record_recommendation with actual argument/result details.
- The SQL replay is separate and intentionally scripted. Its count must never be called agent-verified.
- Save a genuine desktop capture with actual app interaction using Xbox Game Bar (`Win + G`) or OBS. The authoring environment only captured offline diagnostic UI; no full live demo video exists yet.
- Keep `.env`, API keys, credentials and any private GitHub data off-screen.
