"""
Tester Agent — v2, with a REAL agent loop.

The previous version only gave the model ONE turn to respond, so it
could only call ONE tool (write_file) and then stopped.

This version keeps the conversation going: after each tool call, we
feed the RESULT back to the model and ask "what's next?" — repeating
until the model has no more tool calls to make.

This is the actual mechanism that makes multi-step agents work,
and it's the same pattern the Debugger will need later
(fix code -> retest -> check result -> maybe fix again -> ...).
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


def run_tester(source_file: str, test_file: str, max_turns: int = 5):
    with open(source_file, "r") as f:
        source_code = f.read()

    prompt = f"""You are a Tester agent.

Here is the source code in {source_file}:

{source_code}

Write pytest tests for this code and save them to {test_file} using the write_file tool.
Then run the tests using the run_tests tool on {test_file}.
Only stop once you have both written AND run the tests.
"""

    messages = [HumanMessage(content=prompt)]

    for turn in range(max_turns):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            print(f"Model finished after {turn + 1} turn(s). Final message:")
            print(response.content)
            return

        for call in response.tool_calls:
            tool_name = call["name"]
            tool_fn = AVAILABLE_TOOLS.get(tool_name)

            print(f"Turn {turn + 1}: Model calls {tool_name}({call['args']})")

            if tool_fn:
                result = tool_fn.invoke(call["args"])
                print(f"Result:\n{result}\n")
            else:
                result = f"Error: unknown tool '{tool_name}'"
                print(result)

            messages.append(
                ToolMessage(content=str(result), tool_call_id=call["id"])
            )

    print(f"Stopped after {max_turns} turns without the model finishing on its own.")


if __name__ == "__main__":
    run_tester(source_file="calculator.py", test_file="test_calculator.py")