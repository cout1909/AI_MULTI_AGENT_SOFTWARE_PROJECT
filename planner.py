"""
Planner Agent — LangChain version.

Compare this to step1_planner.py (raw Google SDK version):
- We used to manually write the prompt asking for JSON,
  manually strip markdown fences, manually json.loads(), then
  manually validate with Pydantic.
- LangChain's `.with_structured_output()` does ALL of that for us.
  We just describe the shape (Pydantic model) and pass it in —
  LangChain handles prompting the model correctly AND parsing/
  validating the response.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from typing import List

load_dotenv()


# Same Pydantic schema as before — this part doesn't change.
class Task(BaseModel):
    id: int
    description: str
    file_to_create: str


class Plan(BaseModel):
    requirement: str
    tasks: List[Task]


# Set up the LangChain chat model (same as concept1_basic_call.py)
llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
)

# THE KEY LINE: this wraps our llm so that instead of returning
# a plain AIMessage with .content text, it returns an ALREADY
# VALIDATED Plan object directly. No manual JSON parsing needed.
structured_llm = llm.with_structured_output(Plan)


def get_plan(requirement: str) -> Plan:
    prompt = f"""You are a software Planner agent.
Break the following requirement into a small list of concrete coding tasks.
Each task should map to ONE file to create.

Requirement: {requirement}
"""
    # Notice: no JSON instructions needed in the prompt anymore.
    # LangChain handles telling the model how to format its response
    # based on the Pydantic schema we gave it above.
    plan = structured_llm.invoke(prompt)
    return plan


def load_requirement(path: str = "requirement.txt") -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Create it and write your requirement inside."
        )
    with open(path, "r") as f:
        return f.read().strip()


if __name__ == "__main__":
    requirement = load_requirement()
    plan = get_plan(requirement)

    print("Requirement:", plan.requirement)
    print("\nTasks:")
    for task in plan.tasks:
        print(f"  [{task.id}] {task.description} -> {task.file_to_create}")