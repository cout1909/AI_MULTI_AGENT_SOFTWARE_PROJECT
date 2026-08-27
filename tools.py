"""
tools.py — All agent tools live here.

Any agent (Developer, Tester, Debugger, etc.) that needs a tool
imports it from this file, instead of tools being scattered across
every agent's own file.

More tools (run_tests, git_commit, etc.) will be added here later —
this file grows as the project grows, agent files don't need to change.
"""

from langchain_core.tools import tool


@tool
def write_file(path: str, content: str) -> str:
    """Write source code content to a file on disk at the given path."""
    with open(path, "w") as f:
        f.write(content)
    return f"File '{path}' written successfully ({len(content)} chars)."