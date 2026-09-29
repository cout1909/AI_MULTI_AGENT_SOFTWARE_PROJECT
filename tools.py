"""Workspace-confined file tools and bounded process execution."""
import os
from pathlib import Path, PureWindowsPath
import signal
import subprocess
import sys
from typing import List, Optional

from langchain_core.tools import tool


def resolve_workspace_path(workspace: str, path: str) -> Path:
    root = Path(workspace).resolve(strict=True)
    win_path = PureWindowsPath(path)
    parts = path.replace("\\", "/").split("/")
    if (not path or Path(path).is_absolute() or win_path.drive or win_path.root
            or ".." in parts or any(":" in part for part in parts)
            or any(part.lower() == ".git" for part in parts)):
        raise ValueError(f"Unsafe workspace path: {path!r}")
    target = (root / path).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError(f"Path must stay inside the project workspace: {path!r}")
    return target


@tool
def write_file(path: str, content: str, workspace: str) -> str:
    """Write a UTF-8 file using a relative path confined to the supplied workspace."""
    target = resolve_workspace_path(workspace, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {path} ({len(content)} characters)."


def run_process(cmd, workspace, timeout):
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    try:
        process = subprocess.Popen(
            cmd, cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", **options,
        )
    except OSError as exc:
        return {"status": "ERROR", "exit_code": None, "output": str(exc)}
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                pass
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.stdout.close()
            process.stderr.close()
            stdout, stderr = "", ""
        return {"status": "TIMEOUT", "exit_code": None,
                "output": f"Execution timed out after {timeout}s.\n{stdout}\n{stderr}"}
    return {"status": "PASSED" if process.returncode == 0 else "FAILED",
            "exit_code": process.returncode, "output": stdout + "\n" + stderr}


@tool
def run_tests(test_files: Optional[List[str]] = None, test_framework: str = "pytest",
              workspace: str = ".", timeout_seconds: int = 120) -> dict:
    """Execute explicit Python test files and report the actual process exit code."""
    if test_framework != "pytest":
        return {"status": "ERROR", "exit_code": None, "output": "Only pytest is supported."}
    if not test_files:
        return {"status": "ERROR", "exit_code": None, "output": "No test files were generated."}
    if not 1 <= timeout_seconds <= 600:
        raise ValueError("Test timeout must be between 1 and 600 seconds.")
    paths = []
    for path in test_files:
        target = resolve_workspace_path(workspace, path)
        if target.suffix != ".py" or not target.is_file():
            return {"status": "ERROR", "exit_code": None, "output": f"Missing Python test file: {path}"}
        paths.append(str(target))
    return run_process([sys.executable, "-m", "pytest", "-v", "--import-mode=importlib", *paths],
                       workspace, timeout_seconds)


@tool
def git_commit(workspace: str, message: str) -> dict:
    """Commit the project's own repository, reporting staging and commit failures."""
    root = Path(workspace).resolve(strict=True)
    if not (root / ".git").is_dir():
        return {"status": "FAILED", "output": "Workspace has no independent Git repository."}
    for cmd in (["git", "add", "--all"], ["git", "commit", "-m", message]):
        result = run_process(cmd, str(root), 30)
        if result["status"] != "PASSED":
            return {**result, "status": "FAILED"}
    revision = run_process(["git", "rev-parse", "HEAD"], str(root), 10)
    if revision["status"] != "PASSED":
        return {**revision, "status": "FAILED"}
    return {"status": "COMMITTED", "commit": revision["output"].strip(), "output": result["output"]}
