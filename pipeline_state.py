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
    workspace: str
    tasks: List[Task]
    approach_summary: str
    language: str
    framework: str
    test_framework: str
    libraries_needed: List[str]
    files: List[FileDesign]
    source_files: List[str]
    test_files: List[str]
    test_status: str
    test_output: str
    debug_attempts: Annotated[int, operator.add]