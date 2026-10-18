# Competitive audit: SchemaGuard (18 October 2026)

| Existing approach | Official documentation | Where SchemaGuard differs in its controlled demo |
|---|---|---|
| Atlas migration lint | https://atlasgo.io/versioned/lint | Atlas already checks destructive migrations. SchemaGuard additionally demonstrates a recorded active-consumer read path and output-contract replay, without claiming broader coverage. |
| Liquibase policy checks | https://docs.liquibase.com/secure/governance-6-0/what-are-policy-checks | Liquibase checks migration policy/changelogs; our prototype connects SQLite-observed reads and active deployment versions. |
| Flyway Validate | https://documentation.red-gate.com/fd/validate-277578898.html | Flyway validates applied migration history/checksums. This is not directly equivalent to querying a consumer-dependency graph. |
| Prisma safe migration guidance | https://www.prisma.io/docs/guides/v7/database/data-migration | Expand-and-contract is established practice; SchemaGuard does not invent it, but verifies one bounded projection repair sequence. |
| Pact | https://docs.pact.io/ | Pact verifies consumer-provider interaction contracts. SchemaGuard's local required SQL output is only a synthetic, narrower contract. |

An original incident report (https://github.blog/news-insights/company-news/github-availability-report-august-2025/) documents ORM-generated SQL referencing removed database columns. Published incidents are motivation, not SchemaGuard savings measurements.

## Red flags and disposition

| Finding | Severity | Actual change | Validation status |
|---|---|---|---|
| No proven live LLM run in current continuation | Blocking | Keep distinct from deterministic SQL and expose model tool comparison | Still blocked by missing API key; do not claim completed agent |
| Re-seeded graph might erase verification history | High | Scope seed deletion to fixture/deployment/query/observation nodes; keep investigation history | Offline tests pass; live Cypher pending |
| A verified badge could survive failed audit write | High | Require final audit status, persisted recommendation read-back, versioned receipt | Tested with doubles; live graph write fault injection pending |
| Graph contribution looks hardcoded | High | Add judge-selected named consumer, SQLite read observation, FalkorDB reseed, affected path retrieval | Offline input/SQL tests pass; real graph UI pending |
| Failed SQL report non-executable | Medium | ZIP with actual failing plan, fixture and stdlib Python | Real subprocess reproduction passed |
| 'Optimal plan' claim unbounded | High | Enumerate projection-update subsets, <=5 readers, drop last | Four real candidates tested, one passing 3-operation plan |

## Four demonstration abilities
1. Judge-controlled consumer: implemented, offline tested; **real graph re-observation not yet verified**.
2. Executable SQL counterexample: implemented, independently reproduced.
3. Smallest tested repair: enumerates the limited action-subset space; one passing plan with 3 actions; no global optimality claim.
4. Versioned receipt with staleness: implemented, offline-tested, **real FalkorDB read-back pending**.

**Why a graph and a model?** In the tiny controlled manifest, plain Python can enumerate dependencies and candidate repairs. Graph traversal instead provides persisted provenance joining separately declared active deployments, SQLite authorizer evidence and explicit output contracts. The model is a constrained tool-call coordinator, not the verifier; no measurable improvement versus a correct deterministic plan is claimed. Its value is only demonstrated when a permitted live model actually selects tools and persists results.
