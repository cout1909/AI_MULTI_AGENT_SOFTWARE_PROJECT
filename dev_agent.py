"""
Developer Agent — LangChain version, using the @tool decorator.

The tool itself now lives in tools.py — this file only contains
agent LOGIC (the prompt, the decision-checking, the flow).
This separation is what lets Tester/Debugger later import the
same tools.py without duplicating any tool code.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from tools import write_file

load_dotenv()


llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
)

# .bind_tools() tells the model "here are the tools you're allowed to call."
# This replaces our old manual `types.Tool(function_declarations=[...])` setup.
llm_with_tools = llm.bind_tools([write_file])


def run_developer(task_description: str, file_to_create: str):
    prompt = f"""You are a Developer agent.

Task: {task_description}
Target file: {file_to_create}

Write clean, correct Python code that accomplishes this task.
Then call the write_file tool to save it to disk at the target filename.
"""

    response = llm_with_tools.invoke(prompt)

    # LangChain puts any requested tool calls in response.tool_calls
    # This is the equivalent of the old part.function_call check.
    if response.tool_calls:
        for call in response.tool_calls:
            print(f" Model decided to call: {call['name']}({call['args']})")

            if call["name"] == "write_file":
                # .invoke() on the tool itself actually EXECUTES it —
                # this replaces our old manual write_file(path=..., content=...) call.
                result = write_file.invoke(call["args"])
                print(f" Tool executed: {result}")
    else:
        print(" Model did not call a tool. Raw response:")
        print(response.content)


if __name__ == "__main__":
    run_developer(
        task_description="Implement an add function that takes two numbers and returns their sum.",
        file_to_create="calculator.py",
    )