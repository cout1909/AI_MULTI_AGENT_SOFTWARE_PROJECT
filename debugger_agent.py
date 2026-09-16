"""
Debugger Agent - reusable function, now WORKSPACE-aware.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from tools import write_file, run_tests

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
)

llm_with_write = llm.bind_tools([write_file])


def fix_bug(source_files: list, test_output: str, workspace: str = ".", language: str = "Python") -> None:
    sources_text = ""
    for sf in source_files:
        full_path = os.path.join(workspace, sf)
        with open(full_path, "r") as f:
            sources_text += f"\n--- {sf} ---\n{f.read()}\n"

    prompt = f"""You are a Debugger agent.

Language: {language}

Here are the current source files:
{sources_text}

Running the tests produced this output:

{test_output}

Find which file has the bug based on this real error output, and fix it
using the write_file tool (rewrite the FULL corrected file, same filename).
"""

    response = llm_with_write.invoke([HumanMessage(content=prompt)])
    for call in response.tool_calls:
        if call["name"] == "write_file":
            model_path = call["args"]["path"]
            full_path = os.path.join(workspace, model_path)
            result = write_file.invoke({
                "path": full_path,
                "content": call["args"]["content"],
            })
            print(f"[DEBUGGER] {result}")


if __name__ == "__main__":
    result = run_tests.invoke({
        "test_files": ["test_calculator.py"],
        "test_framework": "pytest",
        "workspace": ".",
    })
    fix_bug(["calculator.py"], result, workspace=".", language="Python")