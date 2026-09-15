"""
pipeline.py - The orchestrator. Every node is a thin wrapper calling
the real, reusable agent logic. No duplicated logic here.
"""

from langgraph.graph import StateGraph, START, END

from pipeline_state import PipelineState
from planner import get_plan
from architect import get_architecture
from dev_agent import develop_file
from tester_agent import write_tests_for_file, run_all_tests
from debugger_agent import fix_bug


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
    task_descriptions = [t["description"] for t in state["tasks"]]
    architecture = get_architecture(state["requirement"], task_descriptions)
    print(f"[ARCHITECT] Language: {architecture.language}, "
          f"Framework: {architecture.framework}, "
          f"Test framework: {architecture.test_framework}")
    return {
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
            language=state.get("language", "Python"),
            framework=state.get("framework", "none"),
            libraries=state.get("libraries_needed", []),
            approach_summary=state.get("approach_summary", ""),
            files_description=files_description,
        )
        if path:
            source_files.append(path)

    return {"source_files": source_files}


def tester_node(state: PipelineState) -> dict:
    print("\n[TESTER] Checking tests...")

    test_framework = state.get("test_framework", "pytest")
    test_files = [
        write_tests_for_file(sf, test_framework) for sf in state["source_files"]
    ]

    result = run_all_tests(test_files, test_framework)
    print(f"[TESTER] Status: {result['status']}")

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
        language=state.get("language", "Python"),
    )
    return {"debug_attempts": 1}


def route_after_testing(state: PipelineState) -> str:
    if state["test_status"] == "PASSED":
        return "pass"
    if state.get("debug_attempts", 0) >= 3:
        print("\n[ROUTER] Max debug attempts reached. Giving up.")
        return "give_up"
    return "fail"


graph_builder = StateGraph(PipelineState)
graph_builder.add_node("planner", planner_node)
graph_builder.add_node("architect", architect_node)
graph_builder.add_node("developer", developer_node)
graph_builder.add_node("tester", tester_node)
graph_builder.add_node("debugger", debugger_node)

graph_builder.add_edge(START, "planner")
graph_builder.add_edge("planner", "architect")
graph_builder.add_edge("architect", "developer")
graph_builder.add_edge("developer", "tester")

graph_builder.add_conditional_edges(
    "tester",
    route_after_testing,
    {"pass": END, "fail": "debugger", "give_up": END},
)

graph_builder.add_edge("debugger", "tester")

graph = graph_builder.compile()


if __name__ == "__main__":
    initial_state = {
        "requirement": "Build a function that adds two numbers",
        "debug_attempts": 0,
    }
    final_state = graph.invoke(initial_state)

    print("\n===== PIPELINE COMPLETE =====")
    print("Language:", final_state.get("language"))
    print("Source files:", final_state.get("source_files"))
    print("Test files:", final_state.get("test_files"))
    print("Final test status:", final_state.get("test_status"))
    print("Debug attempts used:", final_state.get("debug_attempts"))