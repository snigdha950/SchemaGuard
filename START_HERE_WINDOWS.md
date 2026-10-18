# Finish the working-agent check on Windows

The SQL checks and actual FalkorDB integration have passed in a separate Linux review runtime. The remaining technical proof is the real model choosing tools against the graph on your machine. This guide avoids PowerShell activation-policy changes.

## 1. Open the project

Extract the ZIP. Start Docker Desktop with Linux containers. Open the inner `SchemaGuard` folder containing `compose.yaml`, type `powershell` in File Explorer's address bar, and press Enter. Python 3.12+ must already be installed.

Run commands individually and stop at the first error:

```powershell
docker compose up -d
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

If you have Python 3.13 instead, use `py -3.13` for the venv command. If you already have a configured `.env`, keep it rather than copying over it.

## 2. Configure the model privately

In `.env`, remove the `#` before `OPENAI_API_KEY` and replace `your-key-here` with your own permitted API key. Save and close Notepad. Do not upload the key or include it in screenshots. `OPENAI_MODEL` must name a model your API account can use.

## 3. Run actual acceptance

```powershell
.\.venv\Scripts\python.exe -m schemaguard.cli seed
.\.venv\Scripts\python.exe -m schemaguard.cli check
.\.venv\Scripts\python.exe scripts/live_end_to_end.py
```

The last command must print `LIVE PASSED`. It makes two real model investigations and verifies graph, changed dependencies, SQLite results and saved audit. The success file is `evidence/live-falkordb-agent-results.json`. A missing credential, model permission error or failed check is a blocker, not proof of a working agent.

If Docker reports connection refused, check `docker compose ps` and `docker compose logs falkordb --tail 80`. If the model fails, retain the error type while hiding credentials; do not change the verifier or substitute canned tool output.

## 4. Record the actual demo

```powershell
.\.venv\Scripts\python.exe -m schemaguard.cli serve
```

Open http://127.0.0.1:8000. Keep the terminal running. Show the graph, replay the SQL comparison, then click **Run agent investigation**. The SQL comparison is supposed to pass only **1 of 3** plans: the first two are unsafe demonstrations. The agent-verified counter is separate and should increase only after a real verified model recommendation.

The acceptance script restores the seed when finished, clearing its temporary graph records. Run a new investigation in the UI for your recording. The JSON acceptance evidence remains on disk.

Use `DEMO_SCRIPT.md` for the story. Publish the source with `.env` excluded, include the working video and complete setup instructions, and complete the submission. A deployed site is optional when full local setup is provided.

## No local Docker? Run acceptance securely in GitHub Actions

The feature branch contains a **manual-only** workflow, `Live graph and real model acceptance (manual only)`. It starts real FalkorDB on a GitHub runner and runs `scripts/live_end_to_end.py` with real tool-calling model access. This workflow **has not run a model yet**.

To run it without pasting an API key into chat: open repository **Settings → Secrets and variables → Actions → New repository secret**, name it **OPENAI_API_KEY**, and save a valid permitted Platform API key. Open **Actions → Live graph and real model acceptance (manual only) → Run workflow**, choose branch **evidence-challenge-2026-10-18**, leave the default model or select one your account supports, then run. Inspect actual logs and the `schemaguard-live-evidence` artifact. The full walkthrough/video still needs a genuine running dashboard. Remove the repository secret afterward if no longer needed. Set the key only in GitHub Actions secrets or local `.env`, never in committed source or chat.
