# Multi-Agent AI Software Developer

A multi-agent AI system that takes a plain-English software requirement and autonomously plans, writes, tests, debugs, and commits real, working code — with no manual coding in the loop.

## What it does

Give it a requirement like `"Build a function that adds two numbers"`, and the system:

1. **Plans** the work into concrete coding tasks
2. **Decides** the technical approach (language, framework, test framework)
3. **Writes** the actual source code
4. **Tests** the code with real, executed tests
5. **Debugs** itself autonomously if tests fail — reads the real error, fixes the code, re-verifies
6. **Commits** the finished, passing project to its own isolated Git repository

All of this happens in one command, with zero human intervention once it starts.

## Architecture

Requirement
|
v
[Workspace Setup] --> creates an isolated project folder + git repo
|
v
[Planner] --> breaks requirement into source-code tasks
|
v
[Architect] --> decides language, framework, test framework, file design
|
v
[Developer] --> writes all source files, following Architect's design
|
v
[Tester] --> writes tests, runs them for real
|
v
PASS? ----NO----> [Debugger] --> fixes the bug --> back to Tester
|
YES
|
v
[Commit] --> auto-commits to the project's own git history


The Debug loop is capped at 3 attempts to avoid infinite retries on an unfixable failure.

## Tech Stack

- **Python** — core language
- **Google Gemini API** (`gemini-3.6-flash`) — the LLM powering every agent
- **LangChain** — LLM abstraction, tool calling (`@tool`, `.bind_tools()`), structured output (`.with_structured_output()`)
- **LangGraph** — multi-agent orchestration, shared state, conditional routing
- **Pydantic** — strict, validated structured output from every LLM call
- **pytest** — real test execution (via Python's `subprocess`)

## Project Structure

pipeline.py - the orchestrator (LangGraph graph definition)
pipeline_state.py - shared state schema passed between agents
planner.py - Planner agent (standalone + reusable)
architect.py - Architect agent (standalone + reusable)
dev_agent.py - Developer agent (standalone + reusable)
tester_agent.py - Tester agent (standalone + reusable)
debugger_agent.py - Debugger agent (standalone + reusable)
tools.py - shared tools: write_file, run_tests, git_commit
workspace_manager.py - creates isolated folders + git repos per project
generated_projects/ - output folder (gitignored) - each project has
its own independent git history


Every agent file can also be run standalone (e.g. `python planner.py`) for isolated testing, and the same functions are reused by `pipeline.py` — no duplicated logic between the two.

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

Create a `.env` file with your Gemini API key:

GEMINI_API_KEY=your_key_here


## Running it

```bash
python pipeline.py
```

The requirement is currently set inside `pipeline.py`'s `__main__` block. Each run creates a new folder under `generated_projects/`, named from the requirement, with its own independent Git repository and commit history.

## Known Limitations (current MVP)

- **Requirement is hardcoded** in `pipeline.py` rather than accepted as user input (planned: CLI arg or API endpoint)
- **JavaScript support is architecturally present but not fully wired** — the Architect agent can choose JavaScript as the language, but the test runner (`npm test`) requires a `package.json` that nothing currently generates. Python is the only fully working language end-to-end today.
- **No parallelism** — tasks and tests run sequentially, not concurrently
- **Free-tier API rate limits** (20 requests/day on Gemini's free tier) constrain how much testing can be done per day

## Roadmap

- FastAPI backend to accept requirements via HTTP and trigger the pipeline
- Frontend UI to submit requirements and view live agent progress
- Full JavaScript/multi-language support (auto-generated `package.json`, per-language test runners)
- Docker + Docker Compose for local multi-service running
- CI/CD via GitHub Actions
- Cloud deployment
- Logging/monitoring of agent runs, token usage, and execution time