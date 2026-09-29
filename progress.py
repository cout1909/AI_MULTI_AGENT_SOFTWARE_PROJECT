"""Per-build progress callbacks, shared by nodes and model retries."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

_sink = ContextVar("progress_sink", default=None)
_cancel = ContextVar("build_cancel", default=None)

class BuildCancelled(RuntimeError):
    pass

def check_cancelled():
    event = _cancel.get()
    if event is not None and event.is_set():
        raise BuildCancelled("Build connection closed; remaining work cancelled.")

def emit(event_type, **data):
    check_cancelled()
    sink = _sink.get()
    if sink:
        sink({"type": event_type, "timestamp": datetime.now(timezone.utc).isoformat(), **data})

@contextmanager
def progress_context(sink, cancelled=None):
    token = _sink.set(sink)
    cancel_token = _cancel.set(cancelled)
    try:
        yield
    finally:
        _sink.reset(token)
        _cancel.reset(cancel_token)
