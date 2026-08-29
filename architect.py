"""
Architect Agent — same pattern as planner.py: structured output, no tools.

Takes the Planner's task list and decides HOW to build it technically:
what libraries to use, what the file structure should look like,
any design notes the Developer agent should follow.

No new concepts here on purpose — reusing with_structured_output()
exactly like the Planner. Proves you can reuse a pattern across agents.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from typing import List

load_dotenv()


class FileDesign(BaseModel):
    filename: str
    purpose: str
    key_functions_or_classes: List[str]


class Architecture(BaseModel):
    approach_summary: str
    libraries_needed: List[str]
    files: List[FileDesign]


llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
)

structured_llm = llm.with_structured_output(Architecture)


def get_architecture(requirement: str, task_descriptions: list[str]) -> Architecture:
    tasks_text = "\n".join(f"- {t}" for t in task_descriptions)

    prompt = f"""You are a software Architect agent.

Requirement: {requirement}

Planned tasks:
{tasks_text}

Decide the technical approach: what libraries are needed (keep it minimal,
standard library where possible), what files should exist, and for each file,
its purpose and the key functions/classes it should contain.
"""

    architecture = structured_llm.invoke(prompt)
    return architecture


if __name__ == "__main__":
    # For now, hardcoded example. Later this will chain directly
    # from planner.py's output automatically.
    requirement = "Build a function that adds two numbers"
    task_descriptions = [
        "Implement the add function that takes two numbers and returns their sum.",
        "Write unit tests to verify the add function works correctly.",
    ]

    architecture = get_architecture(requirement, task_descriptions)

    print("Approach:", architecture.approach_summary)
    print("\nLibraries needed:", architecture.libraries_needed)
    print("\nFiles:")
    for f in architecture.files:
        print(f"  {f.filename} — {f.purpose}")
        for item in f.key_functions_or_classes:
            print(f"    - {item}")