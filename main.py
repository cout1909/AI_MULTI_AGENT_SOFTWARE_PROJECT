"""FastAPI build API with live progress and a backwards-compatible JSON endpoint."""
import asyncio
import json
import logging
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from model_config import ModelUnavailableError
from pipeline import graph
from progress import BuildCancelled, progress_context

app = FastAPI(title="Multi-Agent Software Developer", version="1.1.0")
BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

class BuildRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=20000)

    @field_validator("requirement")
    @classmethod
    def strip_requirement(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter a software requirement.")
        return value

@app.get("/")
def home():
    return RedirectResponse(url="/frontend/")

@app.get("/health")
def health():
    return {"status": "ok", "message": "Multi-Agent Developer API is running"}

def build_result(requirement, state):
    passed = state.get("test_status") == "PASSED"
    committed = state.get("commit_status") == "COMMITTED"
    return {
        "requirement": requirement,
        "workspace": state.get("workspace"),
        "language": state.get("language"),
        "source_files": state.get("source_files") or [],
        "test_files": state.get("test_files") or [],
        "test_status": state.get("test_status"),
        "test_output": state.get("test_output", ""),
        "debug_attempts": state.get("debug_attempts", 0),
        "commit_status": state.get("commit_status", "NOT_ATTEMPTED"),
        "commit_output": state.get("commit_output", ""),
        "commit_hash": state.get("commit_hash"),
        "build_status": "COMPLETED" if passed and committed else "FAILED",
    }

def execute_build(requirement):
    state = graph.invoke({"requirement": requirement, "debug_attempts": 0})
    return build_result(requirement, state)

def error_message(exc):
    if isinstance(exc, (ModelUnavailableError, ValueError)):
        return str(exc)
    return "Build failed. See the server terminal for details."

def log_build_error(exc):
    if isinstance(exc, ModelUnavailableError):
        logger.warning("%s", exc)
    else:
        logger.exception("Build failed")

@app.post("/build")
def build(request: BuildRequest):
    try:
        return execute_build(request.requirement)
    except Exception as exc:
        log_build_error(exc)
        raise HTTPException(status_code=exc.status_code if isinstance(exc, ModelUnavailableError) else 500,
                            detail=error_message(exc)) from exc

@app.post("/build/stream")
async def build_stream(payload: BuildRequest, request: Request):
    async def events():
        queue = Queue()
        cancelled = Event()

        def worker():
            try:
                with progress_context(queue.put, cancelled):
                    result = execute_build(payload.requirement)
                    queue.put({"type": "result", "data": result})
            except BuildCancelled:
                pass
            except Exception as exc:
                log_build_error(exc)
                queue.put({"type": "error", "message": error_message(exc)})
            finally:
                queue.put(None)

        Thread(target=worker, daemon=True, name="project-build").start()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = queue.get_nowait()
                except Empty:
                    await asyncio.sleep(0.1)
                    continue
                if event is None:
                    break
                yield json.dumps(event) + "\n"
        finally:
            # In-flight calls finish or time out; subsequent work is cancelled.
            cancelled.set()

    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

class DashboardFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response

app.mount("/frontend", DashboardFiles(directory=BASE_DIR / "frontend", html=True), name="frontend")
