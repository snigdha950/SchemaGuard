# Demo security boundaries

- Synthetic users have `.test` email domains and invented names. All SQL databases are disposable `:memory:` SQLite connections. This application cannot connect to a production SQL service.
- The only supported schema action is removal of an allowed column in the synthetic `users` table. The only repair is removal of that column from an allowed consumer projection if its required public output does not depend on the column. No model-authored arbitrary SQL, Python or shell commands are executed.
- FalkorDB is a **real required dependency**, not emulated. A downed graph causes blocked investigations, not default empty dependencies.
- `seed` and `/api/reset` can destroy data in the configured graph. Use only an intentionally dedicated graph named `schemaguard_*`; do not put other content in that graph. The included Docker Compose binds to loopback and is not an internet-safe setup.
- `.env` is ignored by Git. Provide model credentials only as server-side environment variables; never put them in seed data, graph properties, the UI, test logs, submissions or recordings. The app exposes only whether the key is configured, not its contents.
- FastAPI binds `127.0.0.1` by default. `/api/reset` is intended for a trusted local development environment, with no user authentication; do not expose this API publicly without adding authentication, authorization, rate limiting, CSRF and security controls.
- Do not infer production safety from this replay. SQLite is not PostgreSQL/MySQL/etc. This tool lacks live query tracing, partial rollout modeling, real ORM introspection, transaction/lock analysis and production deployment protections.
