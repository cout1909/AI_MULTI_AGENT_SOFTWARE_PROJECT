"""
Developer Agent - ONE reusable function, used by BOTH the standalone
script and pipeline.py.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from tools import write_file

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
)

llm_with_write = llm.bind_tools([write_file])


def develop_file(
    task: dict,
    language: str = "Python",
    framework: str = "none",
    libraries: list = None,
    approach_summary: str = "",
    files_description: str = "",
) -> str:
    libraries = libraries or []

    prompt = f"""You are a Developer agent.

Task: {task['description']}
Target file: {task['file_to_create']}

Language: {language}
Framework: {framework}
Libraries to use: {libraries}

Architecture approach: {approach_summary}
File designs:
{files_description}

Write clean, correct code in the specified LANGUAGE. Then call the
write_file tool to save it to disk at the target filename.
"""

    response = llm_with_write.invoke([HumanMessage(content=prompt)])

    written_path = None
    for call in response.tool_calls:
        if call["name"] == "write_file":
            result = write_file.invoke(call["args"])
            print(f"[DEVELOPER] {result}")
            written_path = call["args"]["path"]

    return written_path


if __name__ == "__main__":
    task = {
        "description": "Implement an add function that takes two numbers and returns their sum.",
        "file_to_create": "calculator.py",
    }
    develop_file(task)