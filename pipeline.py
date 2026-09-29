"""
pipeline.py - The orchestrator. Creates an ISOLATED workspace per
project and auto-commits inside it once tests pass.
"""

from langgraph.graph import StateGraph, START, END

from pipeline_state import PipelineState
from workspace_manager import create_workspace
from planner import get_plan
from architect import get_architecture
from dev_agent import develop_file
from tester_agent import write_tests_for_file, run_all_tests
from debugger_agent import fix_bug
from tools import git_commit, write_file, resolve_workspace_path
from progress import emit
from functools import wraps
from time import perf_counter
from progress import BuildCancelled


def setup_node(state: PipelineState) -> dict:
    print("\n[WORKSPACE] Setting up isolated project folder...")
    workspace = create_workspace(state["requirement"])
    return {"workspace": workspace}


def planner_node(state: PipelineState) -> dict:
    print("\n[PLANNER] Breaking requirement into tasks...")
    plan = get_plan(state["requirement"])
    tasks_as_dicts = [t.model_dump() for t in plan.tasks]
    print(f"[PLANNER] Produced {len(tasks_as_dicts)} task(s):")
    for t in tasks_as_dicts:
        print(f"   [{t['id']}] {t['description']} -> {t['file_to_create']}")
    return {"tasks": tasks_as_dicts}


def architect_node(state: PipelineState) -> dict:
    print("\n[ARCHITECT] Deciding technical approach...")
    task_descriptions = [f"{t['file_to_create']}: {t['description']}" for t in state["tasks"]]
    architecture = get_architecture(state["requirement"], task_descriptions)
    print(f"[ARCHITECT] Language: {architecture.language}, "
          f"Framework: {architecture.framework}, "
          f"Test framework: {architecture.test_framework}")
    for file in architecture.files:
        resolve_workspace_path(state["workspace"], file.filename)
    write_file.invoke({"workspace": state["workspace"], "path": "requirements.txt",
                       "content": "\n".join(architecture.libraries_needed + ["pytest"]) + "\n"})
    return {
        "tasks": [{"id": index, "description": file.purpose,
                   "file_to_create": file.filename}
                  for index, file in enumerate(architecture.files, 1)],
        "approach_summary": architecture.approach_summary,
        "language": architecture.language,
        "framework": architecture.framework,
        "test_framework": architecture.test_framework,
        "libraries_needed": architecture.libraries_needed,
        "files": [f.model_dump() for f in architecture.files],
    }


def developer_node(state: PipelineState) -> dict:
    print("\n[DEVELOPER] Writing code...")

    files_description = "\n".join(
        f"  - {f['filename']}: {f['purpose']} "
        f"(should contain: {', '.join(f['key_functions_or_classes'])})"
        for f in state.get("files", [])
    )

    source_files = []
    for task in state["tasks"]:
        path = develop_file(
            task,
            workspace=state["workspace"],
            language=state.get("language", "Python"),
            framework=state.get("framework", "none"),
            libraries=state.get("libraries_needed", []),
            approach_summary=state.get("approach_summary", ""),
            files_description=files_description,
            source_files=source_files,
            requirement=state["requirement"],
        )
        if path:
            source_files.append(path)

    if not source_files:
        raise ValueError("Developer produced no source files.")
    return {"source_files": source_files}


def tester_node(state: PipelineState) -> dict:
    print("\n[TESTER] Checking tests...")

    test_framework = state.get("test_framework", "pytest")
    workspace = state["workspace"]
    test_files = [
        write_tests_for_file(sf, workspace=workspace, test_framework=test_framework,
                             requirement=state["requirement"],
                             approach_summary=state["approach_summary"],
                             source_files=state["source_files"])
        for sf in state["source_files"]
    ]

    result = run_all_tests(test_files, workspace=workspace, test_framework=test_framework)
    print(f"[TESTER] Status: {result['status']}")
    emit("test_result", agent="Tester", status=result["status"],
         output=result["output"], message=f"Tests: {result['status']}")

    return {
        "test_files": test_files,
        "test_status": result["status"],
        "test_output": result["output"],
    }


def debugger_node(state: PipelineState) -> dict:
    print("\n[DEBUGGER] Attempting to fix the bug...")
    fix_bug(
        state["source_files"],
        state["test_output"],
        workspace=state["workspace"],
        language=state.get("language", "Python"),
        requirement=state["requirement"],
        test_files=state["test_files"],
    )
    return {"debug_attempts": 1}


def commit_node(state: PipelineState) -> dict:
    print("\n[GIT] Committing successful project...")
    message = f"Auto-commit: {state['requirement']} - tests passing"
    result = git_commit.invoke({"workspace": state["workspace"], "message": message})
    print(f"[GIT] {result}")
    return {"commit_status": result["status"], "commit_output": result["output"],
            "commit_hash": result.get("commit")}


def route_after_testing(state: PipelineState) -> str:
    if state["test_status"] == "PASSED":
        if not state.get("debug_attempts", 0):
            emit("agent_skip", agent="Debugger", message="Debugger: not needed; tests passed.")
        return "pass"
    if state["test_status"] in {"ERROR", "TIMEOUT"}:
        return "give_up"
    if state.get("debug_attempts", 0) >= 3:
        print("\n[ROUTER] Max debug attempts reached. Giving up.")
        return "give_up"
    return "fail"


def observed(name, function):
    @wraps(function)
    def run(state):
        emit("agent_start", agent=name, message=f"{name}: started")
        started = perf_counter()
        try:
            result = function(state)
        except BuildCancelled:
            raise
        except Exception:
            emit("agent_error", agent=name, elapsed_ms=round((perf_counter() - started) * 1000),
                 message=f"{name}: stopped with an error.")
            raise
        failed = (result.get("test_status") not in (None, "PASSED")
                  or result.get("commit_status") == "FAILED")
        emit("agent_end", agent=name, status="failed" if failed else "completed",
             elapsed_ms=round((perf_counter() - started) * 1000),
             message=f"{name}: {'needs attention' if failed else 'finished'}")
        return result
    return run


graph_builder = StateGraph(PipelineState)
for key, label, function in [
    ("setup", "Workspace", setup_node), ("planner", "Planner", planner_node),
    ("architect", "Architect", architect_node), ("developer", "Developer", developer_node),
    ("tester", "Tester", tester_node), ("debugger", "Debugger", debugger_node),
    ("commit", "Git", commit_node),
]:
    graph_builder.add_node(key, observed(label, function))

graph_builder.add_edge(START, "setup")
graph_builder.add_edge("setup", "planner")
graph_builder.add_edge("planner", "architect")
graph_builder.add_edge("architect", "developer")
graph_builder.add_edge("developer", "tester")

graph_builder.add_conditional_edges(
    "tester",
    route_after_testing,
    {"pass": "commit", "fail": "debugger", "give_up": END},
)

graph_builder.add_edge("debugger", "tester")
graph_builder.add_edge("commit", END)

graph = graph_builder.compile()


if __name__ == "__main__":
    initial_state = {
        "requirement": "Build a function that adds two numbers",
        "debug_attempts": 0,
    }
    final_state = graph.invoke(initial_state)

    print("\n===== PIPELINE COMPLETE =====")
    print("Workspace:", final_state.get("workspace"))
    print("Language:", final_state.get("language"))
    print("Source files:", final_state.get("source_files"))
    print("Test files:", final_state.get("test_files"))
    print("Final test status:", final_state.get("test_status"))
    print("Debug attempts used:", final_state.get("debug_attempts"))