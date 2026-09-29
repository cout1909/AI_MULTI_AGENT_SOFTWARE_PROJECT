"""Generate each file with the architecture and existing source as context."""
from agent_files import generate_files, read_sources

def develop_file(task, workspace=".", language="Python", framework="none",
                 libraries=None, approach_summary="", files_description="",
                 source_files=None, requirement=""):
    if language != "Python":
        raise ValueError("Only Python is supported.")
    target = task["file_to_create"]
    prompt = f"""You are a Python Developer.
Original requirement: {requirement}
Task: {task['description']}
Target file: {target}
Framework: {framework}. Libraries: {libraries or []}
Architecture: {approach_summary}
File designs and interfaces: {files_description}
Already implemented source (preserve these public interfaces):
{read_sources(workspace, source_files or [])}
Write correct Python implementing the requirement. Match existing imports and
function signatures. Avoid running servers or interactive input at import time.
Call save_source exactly once with the complete code for {target}.
"""
    generate_files(prompt, workspace, [target], "Developer")
    return target
