import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import agent_files
import main
import model_config
import pipeline
import tools
from progress import emit, progress_context
from workspace_manager import create_workspace

@pytest.mark.parametrize("path", ["../escape.py", "C:/escape.py", "/escape.py", "..\\escape.py", ".git/config", "file.py:stream"])
def test_reject_outside_and_reserved_paths(tmp_path, path):
    with pytest.raises(ValueError):
        tools.write_file.invoke({"workspace": str(tmp_path), "path": path, "content": "bad"})

def test_nested_utf8_write(tmp_path):
    tools.write_file.invoke({"workspace": str(tmp_path), "path": "pkg/module.py", "content": "# caf?"})
    assert (tmp_path / "pkg/module.py").read_text(encoding="utf-8") == "# caf?"

def test_unique_workspaces_and_real_git(tmp_path):
    first = create_workspace("same requirement", tmp_path)
    second = create_workspace("same requirement", tmp_path)
    assert first != second
    for folder in (first, second):
        assert (Path(folder) / ".git").is_dir()
        assert (Path(folder) / "pytest.ini").is_file()
    tools.run_process(["git", "config", "user.name", "Test Builder"], first, 10)
    tools.run_process(["git", "config", "user.email", "builder@example.invalid"], first, 10)
    result = tools.git_commit.invoke({"workspace": first, "message": "Verify build"})
    assert result["status"] == "COMMITTED"
    assert len(result["commit"]) == 40

def test_real_tests_use_exit_code_not_printed_passed(tmp_path):
    workspace = create_workspace("test results", tmp_path)
    tools.write_file.invoke({"workspace": workspace, "path": "sample.py", "content": "def add(a, b): return a + b"})
    tools.write_file.invoke({"workspace": workspace, "path": "tests/test_sample.py",
                            "content": "from sample import add\ndef test_add():\n    assert add(2, 3) == 5\n"})
    args = {"workspace": workspace, "test_files": ["tests/test_sample.py"]}
    assert tools.run_tests.invoke(args)["status"] == "PASSED"
    tools.write_file.invoke({"workspace": workspace, "path": "tests/test_sample.py",
                            "content": "def test_failure():\n    print('PASSED')\n    assert False\n"})
    result = tools.run_tests.invoke(args)
    assert "PASSED" in result["output"]
    assert result["status"] == "FAILED" and result["exit_code"] == 1

def test_missing_empty_and_timeout(tmp_path):
    assert tools.run_tests.invoke({"workspace": str(tmp_path), "test_files": []})["status"] == "ERROR"
    assert tools.run_tests.invoke({"workspace": str(tmp_path), "test_files": ["missing.py"]})["status"] == "ERROR"
    (tmp_path / "test_slow.py").write_text("import time\ndef test_slow(): time.sleep(30)\n")
    result = tools.run_tests.invoke({"workspace": str(tmp_path), "test_files": ["test_slow.py"], "timeout_seconds": 1})
    assert result["status"] == "TIMEOUT"

class Busy(Exception):
    code = 503

def test_retry_then_success(monkeypatch):
    monkeypatch.setenv("MODEL_MAX_ATTEMPTS", "3")
    monkeypatch.setattr(model_config.time, "sleep", lambda _: None)
    runnable = Mock()
    runnable.invoke.side_effect = [Busy(), Busy(), "ok"]
    events = []
    with progress_context(events.append):
        assert model_config.invoke_model(runnable, "prompt", "Planner") == "ok"
    assert runnable.invoke.call_count == 3
    assert [event["attempt"] for event in events] == [2, 3]

def test_retry_exhaustion_and_permanent_error(monkeypatch):
    monkeypatch.setenv("MODEL_MAX_ATTEMPTS", "3")
    monkeypatch.setattr(model_config.time, "sleep", lambda _: None)
    runnable = Mock()
    runnable.invoke.side_effect = Busy()
    with pytest.raises(model_config.ModelUnavailableError):
        model_config.invoke_model(runnable, "prompt", "Planner")
    assert runnable.invoke.call_count == 3
    runnable.reset_mock()
    runnable.invoke.side_effect = ValueError("Invalid credentials")
    with pytest.raises(ValueError):
        model_config.invoke_model(runnable, "prompt", "Planner")
    assert runnable.invoke.call_count == 1

@pytest.mark.parametrize("calls", [[], [{"name": "save_source", "args": {"path": "other.py", "content": "x=1"}}],
    [{"name": "save_source", "args": {"path": "expected.py", "content": "broken("}}]])
def test_missing_unexpected_invalid_model_files(monkeypatch, tmp_path, calls):
    monkeypatch.setattr(agent_files, "get_model", Mock())
    monkeypatch.setattr(agent_files, "invoke_model", lambda *args: SimpleNamespace(tool_calls=calls))
    with pytest.raises((ValueError, SyntaxError)):
        agent_files.generate_files("prompt", str(tmp_path), ["expected.py"], "Developer")
    assert not list(tmp_path.iterdir())

def test_failed_staging_prevents_commit(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    runner = Mock(return_value={"status": "FAILED", "output": "staging failed", "exit_code": 1})
    monkeypatch.setattr(tools, "run_process", runner)
    assert tools.git_commit.invoke({"workspace": str(tmp_path), "message": "test"})["status"] == "FAILED"
    assert runner.call_count == 1

def test_reconcile_architecture_and_share_context(monkeypatch, tmp_path):
    from architect import Architecture, FileDesign
    architecture = Architecture(approach_summary="calculator", framework="none", libraries_needed=[],
        files=[FileDesign(filename="calc.py", purpose="add numbers", key_functions_or_classes=["add(a,b)"]),
               FileDesign(filename="app.py", purpose="use calculator", key_functions_or_classes=["main()"] )])
    monkeypatch.setattr(pipeline, "get_architecture", lambda *args: architecture)
    state = {"requirement": "add", "workspace": str(tmp_path),
             "tasks": [{"description": "old plan", "file_to_create": "old.py"}]}
    state.update(pipeline.architect_node(state))
    assert [t["file_to_create"] for t in state["tasks"]] == ["calc.py", "app.py"]
    contexts = []
    def develop(task, **kwargs):
        contexts.append(list(kwargs["source_files"]))
        return task["file_to_create"]
    monkeypatch.setattr(pipeline, "develop_file", develop)
    pipeline.developer_node(state)
    assert contexts == [[], ["calc.py"]]

def test_graph_debug_limit_and_progress(monkeypatch, tmp_path):
    from architect import Architecture, FileDesign
    from planner import Plan, Task
    monkeypatch.setattr(pipeline, "create_workspace", lambda _: str(tmp_path))
    monkeypatch.setattr(pipeline, "get_plan", lambda _: Plan(requirement="add", tasks=[Task(id=1, description="add", file_to_create="calc.py")]))
    monkeypatch.setattr(pipeline, "get_architecture", lambda *args: Architecture(approach_summary="add", framework="none", libraries_needed=[], files=[FileDesign(filename="calc.py", purpose="add", key_functions_or_classes=["add"]) ]))
    monkeypatch.setattr(pipeline, "develop_file", lambda *args, **kwargs: "calc.py")
    monkeypatch.setattr(pipeline, "write_tests_for_file", lambda *args, **kwargs: "tests/test_calc.py")
    monkeypatch.setattr(pipeline, "run_all_tests", lambda *args, **kwargs: {"status": "FAILED", "output": "assertion failure"})
    fix = Mock()
    monkeypatch.setattr(pipeline, "fix_bug", fix)
    events = []
    with progress_context(events.append):
        state = pipeline.graph.invoke({"requirement": "add", "debug_attempts": 0})
    assert state["debug_attempts"] == 3 and fix.call_count == 3
    assert len([e for e in events if e["type"] == "test_result"]) == 4
    assert not any(e.get("agent") == "Git" for e in events)

def test_api_stream_validation_and_failure(monkeypatch):
    client = TestClient(main.app)
    assert client.post("/build", json={"requirement": "   "}).status_code == 422
    def execute(requirement):
        emit("agent_start", agent="Planner", message="Planner started")
        emit("retry", agent="Planner", message="Retrying")
        return {"build_status": "COMPLETED", "requirement": requirement}
    monkeypatch.setattr(main, "execute_build", execute)
    response = client.post("/build/stream", json={"requirement": "add"})
    events = [json.loads(line) for line in response.text.splitlines()]
    assert [event["type"] for event in events] == ["agent_start", "retry", "result"]
    def unavailable(_):
        raise model_config.ModelUnavailableError("AI service temporarily unavailable")
    monkeypatch.setattr(main, "execute_build", unavailable)
    assert client.post("/build", json={"requirement": "add"}).status_code == 503
    response = client.post("/build/stream", json={"requirement": "add"})
    assert json.loads(response.text)["type"] == "error"

def test_commit_failure_is_not_build_success():
    result = main.build_result("add", {"test_status": "PASSED", "commit_status": "FAILED"})
    assert result["build_status"] == "FAILED"


def test_full_build_repairs_code_keeps_tests_and_commits(monkeypatch, tmp_path):
    import architect
    import planner
    from architect import Architecture, FileDesign
    from planner import Plan, Task
    monkeypatch.setattr(planner, "get_model", Mock())
    monkeypatch.setattr(architect, "get_model", Mock())
    monkeypatch.setattr(agent_files, "get_model", Mock())
    monkeypatch.setattr(planner, "invoke_model", lambda *args: Plan(requirement="add two numbers", tasks=[Task(id=1, description="add", file_to_create="calc.py")]))
    monkeypatch.setattr(architect, "invoke_model", lambda *args: Architecture(approach_summary="add two numbers", framework="none", libraries_needed=[], files=[FileDesign(filename="calc.py", purpose="add", key_functions_or_classes=["add(a, b)"]) ]))
    calls = []
    def generate(runnable, prompt, agent):
        calls.append(agent)
        assert "add two numbers" in prompt
        if agent == "Tester":
            path = "tests/test_calc.py"
            code = "from calc import add\ndef test_add():\n    assert add(2, 3) == 5\n"
        else:
            path = "calc.py"
            code = "def add(a, b): return a " + ("-" if agent == "Developer" else "+") + " b\n"
        return SimpleNamespace(tool_calls=[{"name": "save_source", "args": {"path": path, "content": code}}])
    monkeypatch.setattr(agent_files, "invoke_model", generate)
    def workspace(requirement):
        folder = create_workspace(requirement, tmp_path)
        tools.run_process(["git", "config", "user.name", "Test Builder"], folder, 10)
        tools.run_process(["git", "config", "user.email", "builder@example.invalid"], folder, 10)
        return folder
    monkeypatch.setattr(pipeline, "create_workspace", workspace)
    result = main.execute_build("add two numbers")
    assert result["build_status"] == "COMPLETED"
    assert result["test_status"] == "PASSED"
    assert result["commit_status"] == "COMMITTED"
    assert result["debug_attempts"] == 1
    assert calls == ["Developer", "Tester", "Debugger"]
    assert "assert add(2, 3) == 5" in (Path(result["workspace"]) / "tests/test_calc.py").read_text()


def test_model_configuration_without_network(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-used-for-network")
    model_config.get_model.cache_clear()
    try:
        model = model_config.get_model()
        from langchain_groq import ChatGroq
        assert isinstance(model, ChatGroq)
        assert model.model_name == "openai/gpt-oss-120b"
        # ChatGroq normalizes a requested temperature of zero to 1e-8.
        assert model.temperature == pytest.approx(0, abs=1e-8)
        assert model.max_retries == 0
        assert model.request_timeout > 0
        assert model_config.get_model() is model
    finally:
        model_config.get_model.cache_clear()


def test_outage_logging_is_concise_but_bugs_keep_traceback(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        main.log_build_error(model_config.ModelUnavailableError("Unavailable after 3 attempts"))
    assert len(caplog.records) == 1
    assert caplog.records[0].exc_info is None
    caplog.clear()
    try:
        raise RuntimeError("unexpected bug")
    except RuntimeError as exc:
        main.log_build_error(exc)
    assert caplog.records[0].exc_info is not None


def test_groq_structured_output_and_all_writer_agents(monkeypatch, tmp_path):
    from planner import Plan
    from architect import Architecture
    from dev_agent import develop_file
    from tester_agent import write_tests_for_file
    from debugger_agent import fix_bug
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-used-for-network")
    model_config.get_model.cache_clear()
    model = model_config.get_model()
    requests = []
    def create(**kwargs):
        requests.append(kwargs)
        function = kwargs["tools"][0]["function"]["name"]
        if function == "Plan":
            args = {"requirement": "add", "tasks": [{"id": 1, "description": "add", "file_to_create": "calc.py"}]}
        elif function == "Architecture":
            args = {"approach_summary": "add", "language": "Python", "framework": "none", "test_framework": "pytest", "libraries_needed": [],
                    "files": [{"filename": "calc.py", "purpose": "add", "key_functions_or_classes": ["add(a,b)"]}]}
        else:
            prompt = str(kwargs["messages"])
            is_tester = "You are a Python Tester" in prompt
            args = {"path": "tests/test_calc.py" if is_tester else "calc.py",
                    "content": "from calc import add\ndef test_add(): assert add(2, 3) == 5\n" if is_tester else "def add(a, b): return a + b\n"}
        return {"id": "test-response", "model": "openai/gpt-oss-120b", "choices": [{"index": 0, "finish_reason": "tool_calls",
                "message": {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": function, "arguments": json.dumps(args)}}]}}]}
    monkeypatch.setattr(model.client, "create", create)
    try:
        assert isinstance(planner_result := __import__("planner").get_plan("add"), Plan)
        assert isinstance(__import__("architect").get_architecture("add", ["add"]), Architecture)
        develop_file(planner_result.tasks[0].model_dump(), workspace=str(tmp_path), requirement="add")
        test_file = write_tests_for_file("calc.py", workspace=str(tmp_path), requirement="add")
        fix_bug(["calc.py"], "example failure", workspace=str(tmp_path), requirement="add", test_files=[test_file])
        assert (tmp_path / "calc.py").is_file()
        assert (tmp_path / test_file).is_file()
        assert len(requests) == 5
        assert all(request["model"] == "openai/gpt-oss-120b" for request in requests)
        assert all("automatic_function_calling" not in request for request in requests)
    finally:
        model_config.get_model.cache_clear()


def test_provider_status_preserved_in_api_and_retry_message(monkeypatch, caplog):
    monkeypatch.setenv("MODEL_MAX_ATTEMPTS", "2")
    monkeypatch.setattr(model_config.time, "sleep", lambda _: None)
    class QuotaError(Exception):
        code = 429
    runnable = Mock()
    runnable.invoke.side_effect = QuotaError()
    with pytest.raises(model_config.ModelUnavailableError) as caught:
        model_config.invoke_model(runnable, "prompt", "Planner")
    assert caught.value.status_code == 429
    assert "HTTP 429" in str(caught.value)
    assert "HTTP 429" in caplog.text
    def fail(_):
        raise caught.value
    monkeypatch.setattr(main, "execute_build", fail)
    assert TestClient(main.app).post("/build", json={"requirement": "add"}).status_code == 429
    code, reason, _ = model_config.provider_failure(Busy())
    assert code == 503 and "HTTP 503" in reason


def test_dashboard_serves_current_assets_without_cache():
    client = TestClient(main.app)
    for path in ("/frontend/", "/frontend/script.js?v=1.1.1", "/frontend/style.css"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
    assert '/build/stream' in client.get('/frontend/script.js').text


def syntax_response(path, content):
    return SimpleNamespace(tool_calls=[{"name": "save_source", "args": {"path": path, "content": content}}])


def test_unterminated_string_repaired_before_any_write(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_files, "get_model", Mock())
    prompts = []
    def invoke(runnable, prompt, agent):
        prompts.append(prompt)
        assert not (tmp_path / "converter.py").exists()
        if len(prompts) == 1:
            return syntax_response("converter.py", 'def convert(c):\n    """Unclosed documentation\n')
        return syntax_response("converter.py", 'def convert(c):\n    return c * 9 / 5 + 32\n')
    monkeypatch.setattr(agent_files, "invoke_model", invoke)
    events = []
    with progress_context(events.append):
        assert agent_files.generate_files("Convert Celsius", str(tmp_path), ["converter.py"], "Developer") == ["converter.py"]
    assert len(prompts) == 2
    assert "unterminated triple-quoted string" in prompts[1]
    assert "Convert Celsius" in prompts[1]
    assert (tmp_path / "converter.py").read_text().endswith("return c * 9 / 5 + 32\n")
    assert [event["type"] for event in events] == ["retry", "file"]


def test_repeated_syntax_error_preserves_existing_files(monkeypatch, tmp_path):
    original = "def convert(c): return c\n"
    (tmp_path / "converter.py").write_text(original)
    monkeypatch.setattr(agent_files, "get_model", Mock())
    invoke = Mock(return_value=syntax_response("converter.py", '"""unterminated'))
    monkeypatch.setattr(agent_files, "invoke_model", invoke)
    with pytest.raises(ValueError, match="after one repair attempt"):
        agent_files.generate_files("convert", str(tmp_path), ["converter.py"], "Debugger", require_all=False)
    assert invoke.call_count == 2
    assert (tmp_path / "converter.py").read_text() == original


def test_syntax_repair_still_rejects_unexpected_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_files, "get_model", Mock())
    invoke = Mock(side_effect=[syntax_response("converter.py", '"""unterminated'), syntax_response("../escape.py", "x = 1")])
    monkeypatch.setattr(agent_files, "invoke_model", invoke)
    with pytest.raises(ValueError, match="Unsafe workspace path"):
        agent_files.generate_files("convert", str(tmp_path), ["converter.py"], "Developer")
    assert not list(tmp_path.iterdir())


def test_generation_api_error_does_not_start_syntax_repair(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_files, "get_model", Mock())
    invoke = Mock(side_effect=RuntimeError("API failed"))
    monkeypatch.setattr(agent_files, "invoke_model", invoke)
    with pytest.raises(RuntimeError, match="API failed"):
        agent_files.generate_files("convert", str(tmp_path), ["converter.py"], "Developer")
    assert invoke.call_count == 1
    assert not list(tmp_path.iterdir())


def test_observed_progress_reports_timing_outcome_and_exception():
    events = []
    with progress_context(events.append):
        assert pipeline.observed("Tester", lambda _: {"test_status": "FAILED"})({}) == {"test_status": "FAILED"}
    assert [event["type"] for event in events] == ["agent_start", "agent_end"]
    assert events[-1]["status"] == "failed"
    assert events[-1]["elapsed_ms"] >= 0
    assert all(event["timestamp"] for event in events)
    events.clear()
    def broken(_):
        raise ValueError("Invalid output")
    with progress_context(events.append), pytest.raises(ValueError):
        pipeline.observed("Developer", broken)({})
    assert [event["type"] for event in events] == ["agent_start", "agent_error"]


def test_debugger_skip_event_only_when_no_repair_was_needed():
    events = []
    with progress_context(events.append):
        assert pipeline.route_after_testing({"test_status": "PASSED", "debug_attempts": 0}) == "pass"
    assert events[0]["type"] == "agent_skip" and events[0]["agent"] == "Debugger"
    events.clear()
    with progress_context(events.append):
        pipeline.route_after_testing({"test_status": "PASSED", "debug_attempts": 1})
    assert not events


def test_http_progress_arrives_before_build_finishes(monkeypatch):
    import socket
    import time
    import threading
    import httpx
    import uvicorn
    release = threading.Event()
    finished = threading.Event()
    def execute(_):
        emit("agent_start", agent="Planner", message="Planning")
        release.wait(timeout=5)
        finished.set()
        return {"build_status": "COMPLETED"}
    monkeypatch.setattr(main, "execute_build", execute)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(main.app, log_level="error", lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        with httpx.Client(timeout=5, trust_env=False) as client:
            with client.stream("POST", f"http://127.0.0.1:{port}/build/stream", json={"requirement": "test"}) as response:
                lines = response.iter_lines()
                first = json.loads(next(lines))
                assert first["type"] == "agent_start"
                assert not finished.is_set(), "Progress was buffered until the build ended"
                release.set()
                assert json.loads(next(lines))["type"] == "result"
    finally:
        release.set()
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
