"""Create a unique project folder and independent Git repository per build."""
from pathlib import Path
import re
from uuid import uuid4
from tools import run_process

DEFAULT_PROJECTS = Path(__file__).resolve().parent / "generated_projects"

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "project"

def create_workspace(requirement, base_dir=None):
    base = Path(base_dir) if base_dir is not None else DEFAULT_PROJECTS
    base.mkdir(parents=True, exist_ok=True)
    workspace = (base / f"{slugify(requirement)}-{uuid4().hex[:12]}").resolve()
    workspace.mkdir(exist_ok=False)
    (workspace / ".gitignore").write_text(
        "__pycache__/\n.pytest_cache/\n*.pyc\n.env\n.venv/\nvenv/\n", encoding="utf-8")
    (workspace / "pytest.ini").write_text("[pytest]\npythonpath = .\ntestpaths = tests\n", encoding="utf-8")
    result = run_process(["git", "init"], str(workspace), 30)
    if result["status"] != "PASSED":
        raise RuntimeError(f"Unable to initialize project Git repository: {result['output']}")
    return str(workspace)
