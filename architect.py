"""Produce the authoritative Python file design, in dependency order."""
from typing import Literal
from pydantic import BaseModel, Field
from agent_files import validate_source_name
from model_config import get_model, invoke_model

class FileDesign(BaseModel):
    filename: str
    purpose: str
    key_functions_or_classes: list[str]

class Architecture(BaseModel):
    approach_summary: str
    language: Literal["Python"] = "Python"
    framework: str
    test_framework: Literal["pytest"] = "pytest"
    libraries_needed: list[str]
    files: list[FileDesign] = Field(min_length=1)

def get_architecture(requirement: str, task_descriptions: list[str]) -> Architecture:
    prompt = f"""You are the Architect for a Python-only software builder.
Requirement: {requirement}
Planner's proposed tasks: {task_descriptions}
Choose Python and pytest. Prefer the standard library; list any necessary pip
packages in libraries_needed. Specify each source .py file, its purpose, and
public interfaces with function signatures. Include package __init__.py files
when needed. No tests or conftest.py: a separate tester owns them.
Your files list is the final implementation plan; cover ALL requested behavior.
Order files with dependencies first so subsequent files can read earlier code.
Use framework 'none' when no framework is needed.
"""
    design = invoke_model(get_model().with_structured_output(Architecture), prompt, "Architect")
    names = [validate_source_name(file.filename) for file in design.files]
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("Architect returned duplicate filenames.")
    return design
