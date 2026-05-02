"""Tests for FastAPI endpoints."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from backend.llm_client import LLMAuthenticationError, LLMRateLimitError, LLMGenerationError


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Test the /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, async_client):
        resp = await async_client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_schema(self, async_client):
        resp = await async_client.get("/health")
        data = resp.json()
        assert "status" in data
        assert "llm_available" in data
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_llm_available(self, async_client):
        """When a mock LLM client is injected, llm_available should be True."""
        resp = await async_client.get("/health")
        data = resp.json()
        assert data["llm_available"] is True

    @pytest.mark.asyncio
    async def test_health_llm_unavailable(self, async_client_no_llm):
        """When llm_client is None, llm_available should be False."""
        resp = await async_client_no_llm.get("/health")
        data = resp.json()
        assert data["llm_available"] is False

    @pytest.mark.asyncio
    async def test_health_includes_model(self, async_client):
        """When LLM is available, model field should be present."""
        resp = await async_client.get("/health")
        data = resp.json()
        # model may or may not be in response depending on whether it's from settings
        # At minimum the key should exist
        assert "model" in data


# ---------------------------------------------------------------------------
# POST /generate - successful requests
# ---------------------------------------------------------------------------


class TestGenerateEndpoint:
    """Test the /generate endpoint with valid requests."""

    @pytest.mark.asyncio
    async def test_generate_valid_request(self, async_client):
        resp = await async_client.post(
            "/generate", json={"text": ";;hello world"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "candidate" in data
        assert "confidence" in data
        assert "model" in data

    @pytest.mark.asyncio
    async def test_generate_continue_intent(self, async_client):
        resp = await async_client.post(
            "/generate", json={"text": ";;hello world"}
        )
        data = resp.json()
        assert "hello world" in data["candidate"]

    @pytest.mark.asyncio
    async def test_generate_mail_intent(self, async_client):
        resp = await async_client.post(
            "/generate",
            json={"text": ";;mail notify client about delay"},
        )
        data = resp.json()
        assert "candidate" in data
        assert len(data["candidate"]) > 0

    @pytest.mark.asyncio
    async def test_generate_summary_intent(self, async_client):
        resp = await async_client.post(
            "/generate",
            json={"text": ";;summary meeting notes from today"},
        )
        data = resp.json()
        assert "candidate" in data

    @pytest.mark.asyncio
    async def test_generate_polish_intent(self, async_client):
        resp = await async_client.post(
            "/generate",
            json={"text": ";;polish this sentence needs improvement"},
        )
        data = resp.json()
        assert "candidate" in data

    @pytest.mark.asyncio
    async def test_generate_translate_intent(self, async_client):
        resp = await async_client.post(
            "/generate",
            json={"text": ";;translate en hello world"},
        )
        data = resp.json()
        assert "candidate" in data

    @pytest.mark.asyncio
    async def test_generate_with_context(self, async_client):
        resp = await async_client.post(
            "/generate",
            json={
                "text": ";;hello",
                "context": {"project": "MindFlow", "language": "en"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "candidate" in data

    @pytest.mark.asyncio
    async def test_generate_plain_text(self, async_client):
        """Plain text without trigger should still work (CONTINUE intent)."""
        resp = await async_client.post(
            "/generate", json={"text": "The quick brown fox"}
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_generate_response_has_confidence(self, async_client):
        resp = await async_client.post(
            "/generate", json={"text": ";;hello"}
        )
        data = resp.json()
        assert isinstance(data["confidence"], float)
        assert 0.0 <= data["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_generate_response_has_model(self, async_client):
        resp = await async_client.post(
            "/generate", json={"text": ";;hello"}
        )
        data = resp.json()
        assert isinstance(data["model"], str)
        assert len(data["model"]) > 0


# ---------------------------------------------------------------------------
# POST /generate - error cases
# ---------------------------------------------------------------------------


class TestGenerateErrors:
    """Test /generate error handling."""

    @pytest.mark.asyncio
    async def test_generate_empty_body(self, async_client):
        """POST with no body should return 422."""
        resp = await async_client.post("/generate")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_missing_text_field(self, async_client):
        """POST without 'text' field should return 422."""
        resp = await async_client.post("/generate", json={"intent": "continue"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_llm_unavailable(self, async_client_no_llm):
        """When LLM is not available, should return 503."""
        resp = await async_client_no_llm.post(
            "/generate", json={"text": ";;hello"}
        )
        assert resp.status_code == 503
        data = resp.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_generate_llm_raises_generic_error(self, async_client, mock_llm_client):
        """When LLM raises a LLMGenerationError, should return 500."""
        mock_llm_client.should_fail = True
        mock_llm_client.failure_exception = LLMGenerationError("API timeout")

        resp = await async_client.post(
            "/generate", json={"text": ";;hello"}
        )
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_generate_llm_raises_auth_error(self, async_client, mock_llm_client):
        """When LLM raises LLMAuthenticationError, should return 401."""
        mock_llm_client.should_fail = True
        mock_llm_client.failure_exception = LLMAuthenticationError("Bad key")

        resp = await async_client.post(
            "/generate", json={"text": ";;hello"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_generate_llm_raises_rate_limit(self, async_client, mock_llm_client):
        """When LLM raises LLMRateLimitError, should return 429."""
        mock_llm_client.should_fail = True
        mock_llm_client.failure_exception = LLMRateLimitError("Too many requests")

        resp = await async_client.post(
            "/generate", json={"text": ";;hello"}
        )
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# POST /context
# ---------------------------------------------------------------------------


class TestContextEndpoint:
    """Test the /context endpoint."""

    @pytest.mark.asyncio
    async def test_update_context(self, async_client):
        resp = await async_client.post(
            "/context",
            json={"app_type": "email", "language": "en"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_update_context_project(self, async_client):
        resp = await async_client.post(
            "/context",
            json={"project": "TestProject", "topic": "testing"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_context_empty(self, async_client):
        """Posting with empty body should succeed (no-op)."""
        resp = await async_client.post("/context", json={})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_context_persists_across_generate(self, async_client):
        """Context set via /context should be used in subsequent /generate calls."""
        # Set context
        await async_client.post(
            "/context", json={"app_type": "email", "language": "en"}
        )

        # Generate should succeed with the set context
        resp = await async_client.post(
            "/generate", json={"text": ";;hello"}
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /forget
# ---------------------------------------------------------------------------


class TestForgetEndpoint:
    """Test the /forget endpoint."""

    @pytest.mark.asyncio
    async def test_forget_session(self, async_client):
        resp = await async_client.post("/forget", json={"scope": "session"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_forget_all(self, async_client):
        resp = await async_client.post("/forget", json={"scope": "all"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_forget_default_scope(self, async_client):
        """Default scope should be 'session'."""
        resp = await async_client.post("/forget", json={})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_forget_clears_context(self, async_client, context_manager):
        """After forget, context should be reset."""
        # Set up some context
        await context_manager.update_session(app_type="email", language="en")
        await context_manager.add_turn(user="u1", assistant="a1", intent="continue")

        # Forget
        resp = await async_client.post("/forget", json={"scope": "session"})
        assert resp.status_code == 200

        # Verify context is reset
        ctx = await context_manager.get_context()
        assert ctx["app_type"] == "other"
        assert ctx["recent_history"] == []


# ---------------------------------------------------------------------------
# POST /generate/stream (SSE)
# ---------------------------------------------------------------------------


class TestStreamEndpoint:
    """Test the /generate/stream SSE endpoint."""

    @pytest.mark.asyncio
    async def test_stream_endpoint_returns_200(self, async_client):
        resp = await async_client.post(
            "/generate/stream", json={"text": ";;hello world"}
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_stream_content_type(self, async_client):
        resp = await async_client.post(
            "/generate/stream", json={"text": ";;hello world"}
        )
        content_type = resp.headers.get("content-type", "")
        assert "text/event-stream" in content_type

    @pytest.mark.asyncio
    async def test_stream_returns_chunk_events(self, async_client):
        resp = await async_client.post(
            "/generate/stream", json={"text": ";;hello world"}
        )
        body = resp.text
        assert "event: chunk" in body

    @pytest.mark.asyncio
    async def test_stream_returns_done_event(self, async_client):
        resp = await async_client.post(
            "/generate/stream", json={"text": ";;hello world"}
        )
        body = resp.text
        assert "event: done" in body

    @pytest.mark.asyncio
    async def test_stream_done_has_full_text(self, async_client):
        resp = await async_client.post(
            "/generate/stream", json={"text": ";;hello world"}
        )
        body = resp.text
        # Find the done event data line
        for line in body.split("\n"):
            if line.startswith("data:") and "done" not in line:
                continue
            if "\"text\":" in line and "model" in line:
                data = json.loads(line.replace("data:", "").strip())
                assert "text" in data
                assert "model" in data
                break

    @pytest.mark.asyncio
    async def test_stream_llm_unavailable(self, async_client_no_llm):
        """When LLM is unavailable, stream should return 503."""
        resp = await async_client_no_llm.post(
            "/generate/stream", json={"text": ";;hello"}
        )
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_stream_missing_text(self, async_client):
        """Missing text field should return 422."""
        resp = await async_client.post(
            "/generate/stream", json={"intent": "continue"}
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


class TestRequestValidation:
    """Test request validation across endpoints."""

    @pytest.mark.asyncio
    async def test_invalid_json(self, async_client):
        resp = await async_client.post(
            "/generate",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_wrong_content_type(self, async_client):
        resp = await async_client.post(
            "/generate",
            content=b"text=hello",
            headers={"content-type": "text/plain"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_extra_fields_ignored(self, async_client):
        """Extra fields in request should be ignored (Pydantic default)."""
        resp = await async_client.post(
            "/generate",
            json={"text": ";;hello", "extra_field": "should be ignored"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_nonexistent_endpoint(self, async_client):
        resp = await async_client.get("/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_records_turn_in_context(self, async_client, context_manager):
        """After a successful /generate call, the turn should be in context."""
        resp = await async_client.post(
            "/generate", json={"text": ";;hello test"}
        )
        assert resp.status_code == 200

        ctx = await context_manager.get_context()
        assert len(ctx["recent_history"]) == 1
        assert ctx["recent_history"][0]["user"] == ";;hello test"
