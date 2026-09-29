"""Write requirement-based tests once, then rerun the same tests after fixes."""
from pathlib import PurePosixPath
import os
from agent_files import generate_files, read_sources
from tools import resolve_workspace_path, run_tests

def test_filename_for(source_file):
    source = PurePosixPath(source_file.replace("\\", "/"))
    # Keep the full source path, preventing collisions between packages.
    return str(PurePosixPath("tests") / source.parent / f"test_{source.name}")

def write_tests_for_file(source_file, workspace=".", test_framework="pytest",
                         requirement="", approach_summary="", source_files=None):
    if test_framework != "pytest":
        raise ValueError("Only pytest is supported.")
    test_file = test_filename_for(source_file)
    full_test_path = resolve_workspace_path(workspace, test_file)
    if not full_test_path.exists():
        prompt = f"""You are a Python Tester.
Original user requirement (the specification): {requirement}
Architecture: {approach_summary}
Source under test: {source_file}
Project sources:
{read_sources(workspace, source_files or [source_file])}
Write pytest tests for the specified behavior, with independently derived
expected values, boundary cases and invalid input where appropriate.
Do not copy implementation mistakes into expected values. Include meaningful
assertions. Import the real project modules using their full package paths.
Tests should be deterministic and not require external services. If this is a
package initializer, test its public imports. Never modify source code.
Call save_source exactly once to write the complete {test_file}.
"""
        generate_files(prompt, workspace, [test_file], "Tester")
    if not full_test_path.is_file() or not full_test_path.read_text(encoding="utf-8").strip():
        raise ValueError(f"Missing or empty test file: {test_file}")
    return test_file

def run_all_tests(test_files, workspace=".", test_framework="pytest"):
    return run_tests.invoke({"test_files": test_files, "workspace": workspace,
                             "test_framework": test_framework,
                             "timeout_seconds": int(os.getenv("TEST_TIMEOUT_SECONDS", "120"))})
