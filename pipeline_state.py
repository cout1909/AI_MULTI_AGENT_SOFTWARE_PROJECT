"""
pipeline_state.py - The shared STATE that flows through every agent.
"""

from typing import TypedDict, List, Annotated
import operator


class Task(TypedDict):
    id: int
    description: str
    file_to_create: str


class FileDesign(TypedDict):
    filename: str
    purpose: str
    key_functions_or_classes: List[str]


class PipelineState(TypedDict):
    requirement: str
    tasks: List[Task]
    approach_summary: str
    libraries_needed: List[str]
    files: List[FileDesign]
    source_file: str
    test_file: str
    test_status: str
    test_output: str
    # Annotated + operator.add = a REDUCER. Instead of each node's
    # return value OVERWRITING debug_attempts, LangGraph ADDS it.
    debug_attempts: Annotated[int, operator.add]
    final_status: str