"""
tools.py — All agent tools live here.
"""

from langchain_core.tools import tool
import subprocess


@tool
def write_file(path: str, content: str) -> str:
    """Write source code content to a file on disk at the given path."""
    with open(path, "w") as f:
        f.write(content)
    return f"File '{path}' written successfully ({len(content)} chars)."


@tool
def run_tests(test_file: str) -> str:
    """Run a pytest test file and return the pass/fail results as text."""
    result = subprocess.run(
        ["pytest", test_file, "-v"],
        capture_output=True,
        text=True,
    )
    output = result.stdout + "\n" + result.stderr
    status = "PASSED" if result.returncode == 0 else "FAILED"
    return f"Test run status: {status}\n\n{output}"