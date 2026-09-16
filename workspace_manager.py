"""
workspace_manager.py - Creates an ISOLATED folder + its own git repo
for each generated project, completely separate from this system's
own repo (multi-agent-developer/).
"""

import os
import re
import subprocess


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text[:50] or "project"


def create_workspace(requirement: str, base_dir: str = "generated_projects") -> str:
    slug = slugify(requirement)
    workspace_path = os.path.join(base_dir, slug)
    os.makedirs(workspace_path, exist_ok=True)

    git_dir = os.path.join(workspace_path, ".git")
    if not os.path.exists(git_dir):
        subprocess.run(["git", "init"], cwd=workspace_path, capture_output=True)
        print(f"[WORKSPACE] Initialized new git repo at {workspace_path}")
    else:
        print(f"[WORKSPACE] Reusing existing workspace at {workspace_path}")

    return workspace_path


if __name__ == "__main__":
    path = create_workspace("Build a function that adds two numbers")
    print("Workspace ready at:", path)