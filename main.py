"""
main.py - FastAPI interface for the Multi-Agent Developer.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from pipeline import graph


app = FastAPI(title="Multi-Agent Software Developer")


# 1. Define the data expected from the user
class BuildRequest(BaseModel):
    requirement: str = Field(min_length=1)


# 2. API endpoint
@app.post("/build")
def build(request: BuildRequest):

    # 3. Prepare the initial LangGraph state
    initial_state = {
        "requirement": request.requirement,
        "debug_attempts": 0,
    }

    # 4. Run the actual multi-agent pipeline
    try:
        final_state = graph.invoke(initial_state)

    except Exception as e:
        print(f"[PIPELINE ERROR] {e}")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) from e

    # 5. Return the pipeline result
    return {
        "requirement": request.requirement,
        "workspace": final_state.get("workspace"),
        "language": final_state.get("language"),
        "source_files": final_state.get("source_files"),
        "test_files": final_state.get("test_files"),
        "test_status": final_state.get("test_status"),
        "debug_attempts": final_state.get("debug_attempts"),
    }