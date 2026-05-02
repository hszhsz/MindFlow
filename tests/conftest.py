"""Shared fixtures for MindFlow test suite."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from backend.context_manager import ContextManager, SessionContext
from backend.intent_classifier import Intent, ParsedInput


# ---------------------------------------------------------------------------
# Mock LLM Client
# ---------------------------------------------------------------------------


class MockLLMClient:
    """A mock LLM client that returns predictable responses based on intent."""

    def __init__(self):
        self._model = "mock-model"
        self.call_count = 0
        self.last_text = None
        self.last_intent = None
        self.last_context = None
        self.should_fail = False
        self.failure_exception = None

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, text: str, intent: Intent, context: dict) -> dict:
        self.call_count += 1
        self.last_text = text
        self.last_intent = intent
        self.last_context = context

        if self.should_fail:
            raise self.failure_exception or Exception("LLM unavailable")

        responses = {
            Intent.CONTINUE: f"continued: {text}",
            Intent.MAIL: f"Dear colleague,\n\nRegarding {text}\n\nBest regards",
            Intent.SUMMARY: f"- Point 1 about {text}\n- Point 2",
            Intent.POLISH: f"Polished version of: {text}",
            Intent.TRANSLATE: f"Translated: {text}",
            Intent.CONTEXT: "Context updated",
            Intent.UNKNOWN: "",
        }

        candidate = responses.get(intent, text)
        return {
            "candidate": candidate,
            "confidence": 0.85,
            "model": self._model,
        }

    async def generate_stream(self, text: str, intent: Intent, context: dict):
        """Async generator that yields chunks."""
        if self.should_fail:
            raise self.failure_exception or Exception("LLM unavailable")

        if intent == Intent.CONTEXT:
            yield "Context updated"
            return

        # Simulate streaming by yielding word-by-word
        response = f"streamed response for: {text}"
        words = response.split()
        for word in words:
            yield word + " "


@pytest.fixture
def mock_llm_client():
    """Provide a mock LLM client instance."""
    return MockLLMClient()


# ---------------------------------------------------------------------------
# Context Manager fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def context_manager(tmp_path, monkeypatch):
    """Provide a ContextManager that uses a temporary directory for storage."""
    monkeypatch.setattr("backend.context_manager.MEMORY_DIR", tmp_path)
    monkeypatch.setattr(
        "backend.context_manager.MEMORY_FILE", tmp_path / "memory.json"
    )
    return ContextManager()


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client(mock_llm_client, context_manager):
    """Provide an httpx AsyncClient wired to the FastAPI app with mocked deps."""
    from backend.main import app
    import backend.main as main_module

    # Inject mocked dependencies into the app module globals
    original_llm = main_module.llm_client
    original_ctx = main_module.context_manager

    main_module.llm_client = mock_llm_client
    main_module.context_manager = context_manager

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Restore originals
    main_module.llm_client = original_llm
    main_module.context_manager = original_ctx


@pytest_asyncio.fixture
async def async_client_no_llm(context_manager):
    """Provide an httpx AsyncClient with llm_client set to None (unavailable)."""
    from backend.main import app
    import backend.main as main_module

    original_llm = main_module.llm_client
    original_ctx = main_module.context_manager

    main_module.llm_client = None
    main_module.context_manager = context_manager

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    main_module.llm_client = original_llm
    main_module.context_manager = original_ctx


# ---------------------------------------------------------------------------
# Sample request data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_generate_request():
    """Sample valid /generate request body."""
    return {"text": ";;hello world", "intent": None, "context": None}


@pytest.fixture
def sample_mail_request():
    """Sample mail intent request."""
    return {"text": ";;mail please notify the client about the delay"}


@pytest.fixture
def sample_translate_request():
    """Sample translate intent request."""
    return {"text": ";;translate en hello world"}


@pytest.fixture
def sample_context_update():
    """Sample context update request body."""
    return {
        "app_type": "email",
        "language": "en",
        "project": "MindFlow",
        "topic": "testing",
    }
