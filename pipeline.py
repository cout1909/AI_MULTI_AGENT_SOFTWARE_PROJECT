"""
pipeline.py - The FULL orchestrated pipeline.

Flow:
  START -> planner -> architect -> developer -> tester
                                                    |
                                    (conditional: pass or fail?)
                                                    |
                                        pass -> END
                                        fail -> debugger -> back to tester

Every node REUSES your already-built, already-tested agent logic
(planner.py, architect.py, tools.py) instead of duplicating it.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END

from pipeline_state import PipelineState
from planner import get_plan
from architect import get_architecture
from tools import write_file, run_tests

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
)

llm_with_write = llm.bind_tools([write_file])


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

    print(f"[ARCHITECT] Approach: {architecture.approach_summary}")

    return {
        "approach_summary": architecture.approach_summary,
        "libraries_needed": architecture.libraries_needed,
        "files": [f.model_dump() for f in architecture.files],
    }


def developer_node(state: PipelineState) -> dict:
    print("\n[DEVELOPER] Writing code...")

    task = state["tasks"][0]

    prompt = f"""You are a Developer agent.

Task: {task['description']}
Target file: {task['file_to_create']}

Write clean, correct Python code that accomplishes this task.
Then call the write_file tool to save it to disk at the target filename.
"""

    response = llm_with_write.invoke([HumanMessage(content=prompt)])

    for call in response.tool_calls:
        if call["name"] == "write_file":
            result = write_file.invoke(call["args"])
            print(f"[DEVELOPER] {result}")

    return {"source_file": task["file_to_create"]}


def tester_node(state: PipelineState) -> dict:
    print("\n[TESTER] Checking tests...")

    source_file = state["source_file"]
    test_file = state.get("test_file") or f"test_{source_file}"

    if not os.path.exists(test_file):
        print("[TESTER] No test file yet - writing one...")
        with open(source_file, "r") as f:
            source_code = f.read()

        prompt = f"""You are a Tester agent.

Here is the source code in {source_file}:

{source_code}

Write pytest tests for this code and save them to {test_file} using the write_file tool.
"""
        response = llm_with_write.invoke([HumanMessage(content=prompt)])

        for call in response.tool_calls:
            if call["name"] == "write_file":
                result = write_file.invoke(call["args"])
                print(f"[TESTER] {result}")

    test_result = run_tests.invoke({"test_file": test_file})
    status = "PASSED" if "PASSED" in test_result else "FAILED"

    print(f"[TESTER] Status: {status}")

    return {
        "test_file": test_file,
        "test_status": status,
        "test_output": test_result,
    }


def debugger_node(state: PipelineState) -> dict:
    print("\n[DEBUGGER] Attempting to fix the bug...")

    source_file = state["source_file"]
    test_output = state["test_output"]

    with open(source_file, "r") as f:
        source_code = f.read()

    prompt = f"""You are a Debugger agent.

The file {source_file} currently has this code:

{source_code}

Running its tests produced this output:

{test_output}

Find the bug based on this real error output and fix {source_file}
using the write_file tool. Rewrite the FULL corrected file.
"""

    response = llm_with_write.invoke([HumanMessage(content=prompt)])

    for call in response.tool_calls:
        if call["name"] == "write_file":
            result = write_file.invoke(call["args"])
            print(f"[DEBUGGER] {result}")

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
    {
        "pass": END,
        "fail": "debugger",
        "give_up": END,
    },
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
    print("Final test status:", final_state.get("test_status"))
    print("Debug attempts used:", final_state.get("debug_attempts"))