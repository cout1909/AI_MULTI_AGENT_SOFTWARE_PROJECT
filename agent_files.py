"""Validate every model-requested write before changing project files."""
import ast
import json
import logging
from pathlib import Path
from langchain_core.tools import tool
from tools import resolve_workspace_path, write_file
from model_config import get_model, invoke_model
from progress import emit

@tool
def save_source(path: str, content: str) -> str:
    """Request saving a complete Python file at the specified relative project path."""
    # Executed only by generate_files after validating all requested writes.
    return path

def validate_source_name(name):
    parts = name.replace("\\", "/").split("/")
    if (not name.endswith(".py") or any(not part.isidentifier() for part in parts[:-1])
            or not Path(parts[-1]).stem.isidentifier()
            or parts[-1].startswith("test_") or parts[-1] == "conftest.py"):
        raise ValueError(f"Expected a relative Python source filename, received {name!r}.")
    return name

def read_sources(workspace, paths):
    return "\n".join(
        f"--- {name} ---\n{resolve_workspace_path(workspace, name).read_text(encoding='utf-8')}"
        for name in paths
    )

def generate_files(prompt, workspace, allowed_paths, agent, require_all=True):
    allowed = {resolve_workspace_path(workspace, name): name for name in allowed_paths}
    runnable = get_model().bind_tools([save_source])
    request_prompt = prompt
    for attempt in range(2):
        response = invoke_model(runnable, request_prompt, agent)
        writes = {}
        for call in response.tool_calls:
            if call["name"] != "save_source":
                raise ValueError(f"{agent} requested an unsupported tool.")
            path, content = call["args"]["path"], call["args"]["content"]
            target = resolve_workspace_path(workspace, path)
            if target not in allowed or target in writes:
                raise ValueError(f"{agent} requested an unexpected or duplicate file: {path}")
            if not content.strip():
                raise ValueError(f"{agent} produced an empty file: {path}")
            writes[target] = content
        if not writes or (require_all and set(writes) != set(allowed)):
            raise ValueError(f"{agent} did not generate the required files: {', '.join(allowed_paths)}")

        errors = []
        for target, content in writes.items():
            try:
                ast.parse(content, filename=allowed[target])
            except SyntaxError as exc:
                errors.append(f"{allowed[target]}:{exc.lineno}:{exc.offset}: {exc.msg}")
        if not errors:
            break
        details = "; ".join(errors)
        if attempt == 1:
            raise ValueError(
                f"{agent}: generated Python still has invalid syntax after one repair attempt: "
                f"{details}. No files from this generation were written."
            )
        message = f"{agent}: generated Python has invalid syntax ({details}); requesting one repair."
        logging.getLogger(__name__).warning(message)
        emit("retry", agent=agent, attempt=2, message=message)
        rejected = json.dumps({allowed[target]: content for target, content in writes.items()})
        request_prompt = (
            prompt
            + "\n\nYour previous file response failed Python syntax validation and was not saved."
            + f"\nValidation errors: {details}"
            + f"\nRejected files (JSON): {rejected}"
            + "\nCorrect the syntax, including any unclosed strings, while preserving the original requirement."
            + " Return complete files using save_source, not patches or Markdown fences."
            + f" Reissue these files: {list(allowed[target] for target in writes)}."
        )
    for target, content in writes.items():
        name = allowed[target]
        write_file.invoke({"workspace": workspace, "path": name, "content": content})
        emit("file", agent=agent, path=name, message=f"{agent}: saved {name}")
    return [allowed[target] for target in writes]
