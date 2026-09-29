# Multi-Agent AI Software Developer

A local Python software builder: describe a requirement in the dashboard, and
Groq agents plan, design, write, test, debug, and commit a project.

## Setup

Use Python 3.10+ and Git. In PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn main:app --reload --reload-dir frontend
```

Open http://127.0.0.1:8000. Restricting reload to `frontend` prevents generated
Python files from restarting the server during builds. Restart the server after
editing backend code. For ordinary builds you can simply run `uvicorn main:app`.

Create `.env` in the project root with your own key:

```dotenv
GROQ_API_KEY=your_key_here
MODEL_MAX_ATTEMPTS=3
MODEL_TIMEOUT_SECONDS=60
TEST_TIMEOUT_SECONDS=120
```

The shared model is `openai/gpt-oss-120b` through LangChain `ChatGroq`. Retries handle temporary
429/500/502/503/504 and network errors, not invalid credentials or model names.
The maximum is five attempts, each bounded by the configured request timeout.
Restart the server after changing `.env`.

## Build workflow

1. Create a unique folder and independent Git repository in `generated_projects`.
2. Planner proposes Python source tasks.
3. Architect produces the final Python/pytest design in dependency order.
4. Developer implements each file with previously written source as context.
5. Tester receives the requirement, architecture, and source, writes pytest tests,
   and executes them with the same Python interpreter as the backend.
6. Debugger receives unchanged tests and actual failures and may fix source up to
   three times. Timeouts and execution errors stop the run.
7. Git stages and commits only after tests pass. A commit failure is reported
   separately; generated files remain available in the workspace.

Set your normal Git user.name and user.email if Git reports missing identity.
The builder does not change your Git identity automatically.

## Main modules

- `model_config.py`: shared model, request timeout, transient error retries.
- `pipeline.py` / `pipeline_state.py`: LangGraph workflow and shared state.
- `planner.py`, `architect.py`, `dev_agent.py`, `tester_agent.py`,
  `debugger_agent.py`: agent roles.
- `agent_files.py`: expected-file validation and source context.
- `tools.py`: confined writes, structured test results, process timeouts, Git.
- `workspace_manager.py`: unique project folders.
- `progress.py`: per-build progress callbacks and cooperative cancellation.
- `main.py`: API and frontend hosting.
- `frontend/`: dashboard and live progress display.

## API

- `GET /health`: server status.
- `POST /build`: JSON request `{"requirement": "..."}`; returns the final result.
- `POST /build/stream`: same input, newline-delimited JSON progress events,
  retry notices, test output, and a terminal `result` or `error` event.

`build_status` is COMPLETED only when tests pass AND the commit succeeds.
Streaming errors arrive as events because HTTP headers have already been sent.
Closing the stream cancels subsequent work; an in-flight model call or test can
continue until completion or its timeout. Logs show real agent events; model
tokens and individual test output lines are not streamed while they execute.

## Checks

```powershell
python -m pytest
node --check frontend/script.js
node --test tests/frontend_stream.test.cjs
```

The automated suite uses mocked model calls and local temporary projects; it
does not spend API credits. A live Groq build is a separate verification.

## Current boundaries

- Python output only. The architect writes a generated `requirements.txt`, but
  generated project libraries are not automatically installed. Missing packages
  will appear in test output; install reviewed dependencies into your environment
  before retrying a new build.
- File tools reject paths outside the workspace and unexpected model writes.
  Generated code still executes locally with the server's permissions; workspace
  confinement is not an execution sandbox. Keep this development app local.
- No project history database, code download/editor, deployment, or functional
  settings screen yet. Navigation links move between workbench, activity, and output.
- Model-generated tests improve feedback but do not prove complete correctness.

## Relay frontend

The light studio interface uses `/build/stream` for real stage events. Workspace,
Planner, Architect, Developer, Tester, Debugger, and Git show their current state,
including retries, failures, skipped debugging, and repeated test passes. Stage
completion events include durations; timestamps come from the backend. The timer
measures elapsed time, not estimated progress. Test output appears after each test
run finishes. File writes appear as they occur.

The UI includes examples, keyboard submission, test-output tabs, log downloads,
and copying the completed project's local path. Animations respect reduced-motion
preferences. Fonts use Google Fonts with local sans-serif fallbacks.

`tests/browser_smoke.cjs` checks the UI in headless Chrome using a local synthetic
stream (no AI requests). Install Playwright separately and set `RELAY_PLAYWRIGHT`
to its package directory if it is not on Node's module path. `RELAY_CHROME` can
point to another Chromium executable. Run `node tests/browser_smoke.cjs`.
