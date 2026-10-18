# Verification evidence

- `real-graph-review-results.json`: current additional Linux review, with actual FalkorDB queries, dependency mutations, independent-client persistence and SQL reference results. No real model calls occurred.
- `review-pytest-output.txt`: 31 passing tests with the real FalkorDB integration test enabled. Model orchestration unit tests still use labelled test doubles.
- `verification-results.json` and `pytest-output.txt`: historical offline authoring evidence. These do not prove a real model ran.

Historical PNG screenshots and WebM recordings are retained in the source ZIP and omitted from this source repository. They show offline diagnostics, not a full working graph-and-model agent. The required real model acceptance result, `live-falkordb-agent-results.json`, is created only after the participant runs `scripts/live_end_to_end.py` successfully with a privately configured model key.
