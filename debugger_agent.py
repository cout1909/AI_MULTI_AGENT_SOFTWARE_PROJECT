"""
Debugger Agent - reusable function, used by BOTH the standalone script
and pipeline.py.
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


def fix_bug(source_files: list, test_output: str, language: str = "Python") -> None:
    sources_text = ""
    for sf in source_files:
        with open(sf, "r") as f:
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
            result = write_file.invoke(call["args"])
            print(f"[DEBUGGER] {result}")


if __name__ == "__main__":
    result = run_tests.invoke({
        "test_files": ["test_calculator.py"],
        "test_framework": "pytest",
    })
    fix_bug(["calculator.py"], result, language="Python")