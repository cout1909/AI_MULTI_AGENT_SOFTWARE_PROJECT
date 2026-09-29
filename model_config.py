"""One Groq configuration and bounded retry policy for every agent."""
import os
import logging
import random
import time
from pathlib import Path
from functools import lru_cache

import httpx
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from progress import check_cancelled, emit

load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)

class ModelUnavailableError(RuntimeError):
    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code


def provider_failure(error):
    """Classify the original exception without exposing credentials or raw bodies."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        code = getattr(error, "code", None) or getattr(error, "status_code", None)
        if code is None:
            code = getattr(getattr(error, "response", None), "status_code", None)
        if str(code) == "429":
            return 429, "Groq returned HTTP 429 (rate or quota limit)", "Check your API quota and any retry delay in Groq Console."
        if str(code) == "503":
            return 503, "Groq returned HTTP 503 (service unavailable)", "Retry later; restarting this app does not restore the provider's availability."
        if str(code) in {"500", "502", "504"}:
            return 503, f"Groq returned HTTP {code} (provider error)", "Retry later."
        if isinstance(error, (TimeoutError, httpx.TimeoutException)):
            return 503, "Groq request timed out", "Check connectivity and try again later."
        error = error.__cause__ or error.__context__
    return 503, "AI connection temporarily unavailable", "Check connectivity and try again later."


def positive_setting(name, default, maximum):
    value = int(os.getenv(name, str(default)))
    if not 1 <= value <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}.")
    return value

@lru_cache(maxsize=1)
def get_model():
    """Return the shared Groq model used by all five agents."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("Set GROQ_API_KEY in your .env file before building.")
    return ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=key,
        temperature=0,
        timeout=positive_setting("MODEL_TIMEOUT_SECONDS", 60, 300),
        # invoke_model owns retries and progress; avoid multiplying attempts.
        max_retries=0,
    )


def is_transient(error):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, (TimeoutError, ConnectionError, httpx.TimeoutException, httpx.NetworkError)):
            return True
        for attr in ("code", "status_code"):
            code = getattr(error, attr, None)
            if str(code) in {"429", "500", "502", "503", "504"}:
                return True
        response = getattr(error, "response", None)
        if getattr(response, "status_code", None) in {429, 500, 502, 503, 504}:
            return True
        error = error.__cause__ or error.__context__
    return False

def invoke_model(runnable, prompt, agent):
    attempts = positive_setting("MODEL_MAX_ATTEMPTS", 3, 5)
    for attempt in range(1, attempts + 1):
        check_cancelled()
        try:
            return runnable.invoke(prompt)
        except Exception as exc:
            if not is_transient(exc):
                raise
            status_code, reason, action = provider_failure(exc)
            if attempt == attempts:
                raise ModelUnavailableError(
                    f"{agent}: {reason} after {attempts} attempts. {action}",
                    status_code=status_code,
                ) from exc
            delay = min(2 ** attempt, 20) + random.uniform(0, 1)
            message = f"{agent}: {reason}; retry {attempt + 1}/{attempts} in {delay:.1f}s."
            logger.warning(message)
            emit("retry", agent=agent, attempt=attempt + 1, message=message)
            time.sleep(delay)
