"""Fix source against the original requirement and unchanged tests."""
from agent_files import generate_files, read_sources

def fix_bug(source_files, test_output, workspace=".", language="Python",
            requirement="", test_files=None):
    if language != "Python":
        raise ValueError("Only Python is supported.")
    prompt = f"""You are a Python Debugger.
Original requirement: {requirement}
Current source:
{read_sources(workspace, source_files)}
Existing tests (read-only):
{read_sources(workspace, test_files or [])}
Actual test output:
{test_output}
Fix the source to satisfy the requirement and tests. Preserve public interfaces.
Call save_source for each changed source file, writing its complete corrected
content. You may only change these files: {source_files}.
Do not weaken, delete, or modify tests.
"""
    generate_files(prompt, workspace, source_files, "Debugger", require_all=False)
