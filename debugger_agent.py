"""
Debugger Agent — the payoff of the whole project.

Loop:
1. Run the existing tests.
2. If they PASS, we're done - nothing to fix.
3. If they FAIL, read the real error output, ask the model to fix
   the source code, write the fix, and try again.
4. Repeat until tests pass or we hit max_attempts.

This reuses the exact same "conversation loop" pattern as tester_agent.py,
but now the loop has a real PURPOSE: converging on working code.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, ToolMessage
from tools import write_file, run_tests

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
)

llm_with_tools = llm.bind_tools([write_file, run_tests])

AVAILABLE_TOOLS = {
    "write_file": write_file,
    "run_tests": run_tests,
}


def run_debugger(source_file: str, test_file: str, max_attempts: int = 3):
    for attempt in range(1, max_attempts + 1):
        print(f"\n===== Attempt {attempt}/{max_attempts}: running tests =====")

        # Run tests directly ourselves first (not via the model) just to
        # CHECK the current status before involving the LLM at all.
        test_result = run_tests.invoke({"test_file": test_file})
        print(test_result)

        if "PASSED" in test_result:
            print(f"\nAll tests passed on attempt {attempt}. Nothing to debug.")
            return True

        print(f"\nTests FAILED. Asking Debugger agent to fix {source_file}...")

        with open(source_file, "r") as f:
            source_code = f.read()

        prompt = f"""You are a Debugger agent.

The file {source_file} currently has this code:

{source_code}

Running its tests ({test_file}) produced this output:

{test_result}

Find the bug based on this real error output, fix {source_file} using the
write_file tool (rewrite the FULL corrected file), then verify your fix
by calling run_tests on {test_file}.
"""

        messages = [HumanMessage(content=prompt)]

        # Same conversation loop pattern as tester_agent.py
        for turn in range(5):
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                print("Debugger's final message:")
                print(response.content)
                break

            for call in response.tool_calls:
                tool_name = call["name"]
                tool_fn = AVAILABLE_TOOLS.get(tool_name)
                print(f"Debugger calls {tool_name}({call['args']})")

                result = tool_fn.invoke(call["args"])
                print(f"Result:\n{result}\n")

                messages.append(
                    ToolMessage(content=str(result), tool_call_id=call["id"])
                )

    print(f"\nGave up after {max_attempts} attempts. Tests still failing.")
    return False


if __name__ == "__main__":
    success = run_debugger(source_file="calculator.py", test_file="test_calculator.py")
    print("\n=== FINAL RESULT:", "SUCCESS" if success else "FAILED", "===")