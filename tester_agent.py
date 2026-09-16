"""
Tester Agent - reusable functions, now WORKSPACE-aware.
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


def test_filename_for(source_file: str) -> str:
    base_name = os.path.basename(source_file)
    name_no_ext, ext = os.path.splitext(base_name)
    if ext == ".py":
        return f"test_{base_name}"
    return f"{name_no_ext}.test{ext}"


def write_tests_for_file(source_file: str, workspace: str = ".", test_framework: str = "pytest") -> str:
    test_file = test_filename_for(source_file)
    full_source_path = os.path.join(workspace, source_file)
    full_test_path = os.path.join(workspace, test_file)

    if not os.path.exists(full_test_path):
        print(f"[TESTER] Writing {test_file}...")
        with open(full_source_path, "r") as f:
            source_code = f.read()

        prompt = f"""You are a Tester agent.

Here is the source code in {source_file}:

{source_code}

Test framework to use: {test_framework}

Write tests for this code using {test_framework} and save them to
{test_file} using the write_file tool.
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
                print(f"[TESTER] {result}")

    return test_file


def run_all_tests(test_files: list, workspace: str = ".", test_framework: str = "pytest") -> dict:
    test_result = run_tests.invoke({
        "test_files": test_files,
        "test_framework": test_framework,
        "workspace": workspace,
    })
    status = "PASSED" if "PASSED" in test_result else "FAILED"
    return {"status": status, "output": test_result}


if __name__ == "__main__":
    source_file = "calculator.py"
    test_file = write_tests_for_file(source_file, workspace=".")
    result = run_all_tests([test_file], workspace=".")
    print(f"\nStatus: {result['status']}")
    print(result["output"])