"""
Planner Agent - LangChain version. Produces SOURCE CODE tasks only -
testing is owned entirely by the Tester agent, not planned here.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from typing import List

load_dotenv()


class Task(BaseModel):
    id: int
    description: str
    file_to_create: str


class Plan(BaseModel):
    requirement: str
    tasks: List[Task]


llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
)

structured_llm = llm.with_structured_output(Plan)


def get_plan(requirement: str) -> Plan:
    prompt = f"""You are a software Planner agent.
Break the following requirement into a small list of concrete coding tasks.
Each task should map to ONE file to create.

IMPORTANT RULES:
- This project is Python-only. Every file_to_create MUST end in .py.
- Do NOT create any test-related tasks (no test_*.py files, no testing
  tasks at all). Testing is handled automatically by a separate Tester
  agent later in the pipeline - you should only plan the actual SOURCE
  CODE files needed to fulfill the requirement.

Requirement: {requirement}
"""
    plan = structured_llm.invoke(prompt)
    return plan


def load_requirement(path: str = "requirement.txt") -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found.")
    with open(path, "r") as f:
        return f.read().strip()


if __name__ == "__main__":
    requirement = load_requirement()
    plan = get_plan(requirement)
    print("Requirement:", plan.requirement)
    print("\nTasks:")
    for task in plan.tasks:
        print(f"  [{task.id}] {task.description} -> {task.file_to_create}")