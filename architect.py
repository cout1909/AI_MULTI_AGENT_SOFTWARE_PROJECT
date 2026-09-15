"""
Architect Agent - outputs an explicit tech stack.
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
    language: str
    framework: str
    test_framework: str
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

Decide the full technical approach, including:
- The programming language best suited to this requirement.
- The framework needed, if any (use "none" if no framework is needed).
- The test framework to use for this language (e.g. pytest for Python,
  vitest or jest for JavaScript).
- The libraries needed (keep minimal, standard library where possible).
- The files that should exist, each with its purpose and key
  functions/classes.

Currently supported languages in this system: Python, JavaScript.
Choose whichever fits the requirement best.
"""

    architecture = structured_llm.invoke(prompt)
    return architecture


if __name__ == "__main__":
    requirement = "Build a function that adds two numbers"
    task_descriptions = [
        "Implement the add function that takes two numbers and returns their sum.",
    ]
    architecture = get_architecture(requirement, task_descriptions)
    print("Approach:", architecture.approach_summary)
    print("Language:", architecture.language)
    print("Framework:", architecture.framework)
    print("Test framework:", architecture.test_framework)
    print("\nLibraries needed:", architecture.libraries_needed)
    print("\nFiles:")
    for f in architecture.files:
        print(f"  {f.filename} - {f.purpose}")
        for item in f.key_functions_or_classes:
            print(f"    - {item}")