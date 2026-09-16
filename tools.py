"""
tools.py - All agent tools live here.
"""

from langchain_core.tools import tool
from typing import List, Optional
import subprocess


@tool
def write_file(path: str, content: str) -> str:
    """Write source code content to a file on disk at the given path."""
    with open(path, "w") as f:
        f.write(content)
    return f"File '{path}' written successfully ({len(content)} chars)."


@tool
def run_tests(
    test_files: Optional[List[str]] = None,
    test_framework: str = "pytest",
    workspace: str = ".",
) -> str:
    """Run tests inside the given workspace folder, using the appropriate test runner for the given test_framework."""
    if test_framework == "pytest":
        cmd = ["pytest", "-v"]
        if test_files:
            cmd.extend(test_files)
    elif test_framework in ("npm", "jest", "vitest"):
        cmd = ["npm", "test"]
    else:
        return f"Unsupported test framework: {test_framework}"

    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=workspace,
        shell=(test_framework != "pytest"),
    )
    output = result.stdout + "\n" + result.stderr
    status = "PASSED" if result.returncode == 0 else "FAILED"
    return f"Test run status: {status}\n\n{output}"


@tool
def git_commit(workspace: str, message: str) -> str:
    """Stage and commit all changes inside the given workspace folder."""
    subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True)
    result = subprocess.run(
        ["git", "commit", "-m", message], cwd=workspace,
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return f"Committed to {workspace}: {message}"
    return f"Nothing to commit or commit failed: {result.stdout}{result.stderr}"