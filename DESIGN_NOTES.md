# Interface decisions

SchemaGuard should read like a developer migration-review tool, not a landing page.

- Compact sidebar: change review, SQL verification, dependency graph, agent activity, and optional demo tools.
- Primary work area: choose the column, run the investigation, compare actual SQLite results and preserved output contracts.
- Graph topology and highlighted paths must come only from FalkorDB; when offline the map says so instead of drawing imaginary connections.
- Actual LLM activity remains separate from deterministic SQL comparison.
- Dark charcoal navigation, light canvas and restrained violet accents; clean system fonts and minimal decoration.
- Small-screen layout stacks panels and keeps buttons accessible. Keyboard focus styling and reduced-motion settings are supported.
- UI changes do not relax SQL verification, expand supported migrations or establish model access.

## Verification and remaining work

The live FalkorDB integration has a passing GitHub Actions run, but actual LLM tool calls and an agent-generated verified recommendation still require an acceptance run with a private API key. An authentic recorded demonstration is also outstanding. Never label the reference SQL pass as an agent result.

The published repo intentionally keeps source, fixture data, integration tests, Cypher queries, licence, documentation, and small human-readable verification records. Stale offline screenshots and WebM recordings are **not tracked**; their only role is historical diagnostic context in earlier downloadable ZIPs. No customer data, credentials or production migrations belong in this repository.
