# Graph Hacks submission draft

**Name:** SchemaGuard

**Tagline:** Check what a database change will break before applying it.

**Primary track:** Agents That Act on Connected Data.

**Repository:** https://github.com/snigdha950/SchemaGuard

**Short description:** A column unused by the newest application can still be selected by an older deployment or background worker. SchemaGuard connects deployments, consumer versions, SQL queries, columns and observed reads in FalkorDB. Its bounded agent is designed to retrieve affected paths, propose projection repairs and test every migration step against disposable SQLite databases. Output contracts and retained data must pass independently before a recommendation is verified. This prototype supports controlled synthetic fixtures, not production migrations.

**Technology:** Python 3.12+, FastAPI, FalkorDB, SQLite, an OpenAI-compatible tool-calling model, vanilla JavaScript and SVG.

## Current verification

- Real SQLite reference results: immediate drop is unsafe; one-consumer repair is unsafe; repairing both affected consumers before dropping is verified.
- Real FalkorDB traversal, evidence-drift blocking, changed worker/dependencies and independent-client audit persistence passed on Linux using official FalkorDBLite binaries and the standard SDK.
- Full suite with real graph integration enabled: **31 passed**. Evidence is in `evidence/real-graph-review-results.json` and `evidence/review-pytest-output.txt`.
- **Real model execution remains unverified.** A model key has not been configured in the review runtime. Offline SQL footage does not establish a working agent.

## Remaining submission work

- [ ] Run participant-machine setup from `START_HERE_WINDOWS.md`.
- [ ] Privately configure the model and make `scripts/live_end_to_end.py` print `LIVE PASSED`.
- [ ] Inspect actual model tool events, SQL verification and generated live acceptance evidence.
- [ ] Record the real app and working agent following `DEMO_SCRIPT.md`; add an accessible video URL here.
- [ ] Complete and document participants' own review, understanding and verification in `AI_ASSISTANCE.md`.
- [ ] Check GitHub Actions; its default suite is offline and does not prove model execution.
- [ ] Submit the real repository and working video through the official portal by 11:59 PM IST on 18 October 2026.

**Demo video URL:** Pending recording and upload.

**Deployment:** Full localhost setup is documented. A hosted deployment is not provided.

**Memory track:** Not claimed; persisted attempts alone do not establish an independently demonstrated memory-and-coordination workflow.

**Rules:** https://www.wemakedevs.org/hackathons/falkordb/rules


## New branch handoff

Review the judge challenge, executable SQL failure ZIP, minimum bounded SQL comparison, and staleness-aware verification receipt. Offline tests and real SQLite execution are distinct from live FalkorDB+LLM acceptance. The latter is still required. Do not submit the old offline UI recording as the agent demo. A full live demonstration video URL remains missing until the team records and uploads it.
