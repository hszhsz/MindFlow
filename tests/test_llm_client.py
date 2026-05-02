"""Tests for llm_client module (with mocked LLM providers)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from backend.intent_classifier import Intent
from backend.llm_client import (
    BASE_SYSTEM_PROMPT,
    LLMAuthenticationError,
    LLMClient,
    LLMError,
    LLMGenerationError,
    LLMRateLimitError,
    _build_continue_prompt,
    _build_mail_prompt,
    _build_polish_prompt,
    _build_summary_prompt,
    _build_system_prompt,
    _build_translate_prompt,
    AnthropicProvider,
    OpenAIProvider,
)


# ---------------------------------------------------------------------------
# Helper: Create mock providers
# ---------------------------------------------------------------------------

def _make_mock_anthropic_response(text: str):
    """Build a mock object that mimics an Anthropic Messages.create() response."""
    mock_content_block = MagicMock()
    mock_content_block.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]
    return mock_response


class MockProvider:
    """Mock provider for testing."""
    def __init__(self, response_text: str = "mock response"):
        self._response_text = response_text
        self.generate_calls = []
        self.stream_calls = []

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.generate_calls.append((system_prompt, user_prompt))
        return self._response_text.strip()

    async def generate_stream(self, system_prompt: str, user_prompt: str):
        self.stream_calls.append((system_prompt, user_prompt))
        words = self._response_text.split()
        for i, word in enumerate(words):
            trailing = " " if i < len(words) - 1 else ""
            yield word + trailing

    async def close(self):
        pass


# ---------------------------------------------------------------------------
# Client initialization
# ---------------------------------------------------------------------------

class TestLLMClientInit:
    """Test LLMClient initialization."""

    def _mock_settings(self, **kwargs):
        defaults = {
            "llm_provider": "anthropic",
            "llm_api_key": "test-key",
            "llm_base_url": None,
            "model_name": "claude-sonnet-4-20250514",
            "max_tokens": 512,
        }
        defaults.update(kwargs)
        return patch("backend.llm_client.settings", **defaults)

    def test_init_with_explicit_key(self):
        mock_provider = MockProvider()
        with patch("backend.llm_client._create_provider", return_value=mock_provider):
            client = LLMClient(api_key="test-key-123")
            assert client._provider is mock_provider

    def test_init_from_settings(self):
        mock_provider = MockProvider()
        with self._mock_settings(llm_api_key="settings-key"):
            with patch("backend.llm_client._create_provider", return_value=mock_provider):
                client = LLMClient()
                assert client._provider is mock_provider

    def test_init_no_key_raises(self):
        with self._mock_settings(llm_api_key=None):
            with pytest.raises(LLMAuthenticationError, match="API key"):
                LLMClient()

    def test_model_property(self):
        mock_provider = MockProvider()
        with self._mock_settings(model_name="test-model"):
            with patch("backend.llm_client._create_provider", return_value=mock_provider):
                client = LLMClient(api_key="test-key")
                assert client.model == "test-model"

    def test_accepts_context_manager(self):
        mock_provider = MockProvider()
        with patch("backend.llm_client._create_provider", return_value=mock_provider):
            mock_cm = MagicMock()
            client = LLMClient(api_key="test-key", context_manager=mock_cm)
            assert client._context_manager is mock_cm


# ---------------------------------------------------------------------------
# Module-level prompt builders
# ---------------------------------------------------------------------------


class TestPromptBuilders:
    """Test the module-level prompt builder functions."""

    def test_continue_prompt_contains_text(self):
        prompt = _build_continue_prompt("hello world", {})
        assert "hello world" in prompt

    def test_continue_prompt_has_instruction(self):
        prompt = _build_continue_prompt("hello", {})
        assert "继续" in prompt

    def test_continue_prompt_with_app_type(self):
        prompt = _build_continue_prompt("hello", {"app_type": "email"})
        assert "email" in prompt

    def test_continue_prompt_ignores_other_app_type(self):
        prompt = _build_continue_prompt("hello", {"app_type": "other"})
        assert "other" not in prompt or "用户当前" not in prompt

    def test_mail_prompt_contains_text(self):
        prompt = _build_mail_prompt("notify about delay", {})
        assert "notify about delay" in prompt
        assert "邮件" in prompt

    def test_mail_prompt_with_project(self):
        prompt = _build_mail_prompt("content", {"project": "MindFlow"})
        assert "MindFlow" in prompt

    def test_summary_prompt_contains_text(self):
        prompt = _build_summary_prompt("meeting notes", {})
        assert "meeting notes" in prompt
        assert "要点" in prompt

    def test_polish_prompt_contains_text(self):
        prompt = _build_polish_prompt("rough text", {})
        assert "rough text" in prompt
        assert "润色" in prompt

    def test_translate_prompt_default_target(self):
        prompt = _build_translate_prompt("hello", {})
        assert "en" in prompt
        assert "hello" in prompt

    def test_translate_prompt_with_target(self):
        prompt = _build_translate_prompt("hello", {"target_lang": "ja"})
        assert "ja" in prompt

    def test_translate_prompt_with_french_target(self):
        prompt = _build_translate_prompt("text", {"target_lang": "fr"})
        assert "fr" in prompt


class TestSystemPromptBuilder:
    """Test _build_system_prompt."""

    def test_without_context(self):
        prompt = _build_system_prompt("")
        assert prompt == BASE_SYSTEM_PROMPT

    def test_with_context(self):
        prompt = _build_system_prompt("[Context]\nProject: MindFlow\n[/Context]")
        assert BASE_SYSTEM_PROMPT in prompt
        assert "MindFlow" in prompt

    def test_base_system_prompt_content(self):
        assert "MindFlow" in BASE_SYSTEM_PROMPT
        assert "输入法" in BASE_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Context injection
# ---------------------------------------------------------------------------


class TestContextInjection:
    """Test that context is properly injected into prompts."""

    def test_translate_uses_target_lang(self):
        context = {"target_lang": "fr"}
        prompt = _build_translate_prompt("bonjour", context)
        assert "fr" in prompt

    def test_translate_defaults_to_en(self):
        prompt = _build_translate_prompt("hello", {})
        assert "en" in prompt

    @pytest.mark.asyncio
    async def test_system_prompt_with_context_manager(self):
        """When a context_manager is provided, its output enriches the system prompt."""
        mock_provider = MockProvider()
        mock_cm = AsyncMock()
        mock_cm.build_context_prompt.return_value = "[Context]\nProject: Test\n[/Context]"

        with patch("backend.llm_client._create_provider", return_value=mock_provider):
            client = LLMClient(api_key="test-key", context_manager=mock_cm)
            system_prompt = await client._get_system_prompt()
            assert BASE_SYSTEM_PROMPT in system_prompt
            assert "Test" in system_prompt
            mock_cm.build_context_prompt.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_system_prompt_without_context_manager(self):
        """Without a context_manager, the base system prompt is returned."""
        mock_provider = MockProvider()
        with patch("backend.llm_client._create_provider", return_value=mock_provider):
            client = LLMClient(api_key="test-key")
            system_prompt = await client._get_system_prompt()
            assert system_prompt == BASE_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Generate method
# ---------------------------------------------------------------------------


class TestGenerate:
    """Test the generate() method with mocked provider."""

    @pytest.fixture
    def client(self):
        mock_provider = MockProvider("continued text here")
        with patch("backend.llm_client._create_provider", return_value=mock_provider):
            c = LLMClient(api_key="test-key")
            c._provider = mock_provider
            yield c

    @pytest.mark.asyncio
    async def test_generate_continue(self, client):
        client._provider._response_text = "continued text here"
        result = await client.generate("hello", Intent.CONTINUE, {})
        assert result["candidate"] == "continued text here"
        assert "confidence" in result
        assert "model" in result

    @pytest.mark.asyncio
    async def test_generate_mail(self, client):
        client._provider._response_text = "Dear colleague,\n\nBest regards"
        result = await client.generate("notify client", Intent.MAIL, {})
        assert "Dear colleague" in result["candidate"]

    @pytest.mark.asyncio
    async def test_generate_summary(self, client):
        client._provider._response_text = "- Point 1\n- Point 2"
        result = await client.generate("meeting notes", Intent.SUMMARY, {})
        assert "Point 1" in result["candidate"]

    @pytest.mark.asyncio
    async def test_generate_polish(self, client):
        client._provider._response_text = "Polished and refined text"
        result = await client.generate("rough text", Intent.POLISH, {})
        assert result["candidate"] == "Polished and refined text"

    @pytest.mark.asyncio
    async def test_generate_translate(self, client):
        client._provider._response_text = "Hello world"
        result = await client.generate("你好世界", Intent.TRANSLATE, {"target_lang": "en"})
        assert result["candidate"] == "Hello world"

    @pytest.mark.asyncio
    async def test_generate_context_intent_no_api_call(self, client):
        """CONTEXT intent should return immediately without calling the provider."""
        client._provider.generate_calls.clear()
        result = await client.generate("", Intent.CONTEXT, {})
        assert result["candidate"] == "Context updated"
        assert result["confidence"] == 1.0
        assert len(client._provider.generate_calls) == 0

    @pytest.mark.asyncio
    async def test_generate_uses_system_prompt(self, client):
        client._provider._response_text = "result"
        await client.generate("test", Intent.CONTINUE, {})
        assert len(client._provider.generate_calls) == 1
        system, user = client._provider.generate_calls[0]
        assert BASE_SYSTEM_PROMPT in system

    @pytest.mark.asyncio
    async def test_generate_uses_correct_model(self, client):
        """Model is passed through via the client model property."""
        assert client.model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_generate_sets_max_tokens(self, client):
        """Max tokens is set from settings."""
        assert client._max_tokens == 512

    @pytest.mark.asyncio
    async def test_generate_confidence_range(self, client):
        client._provider._response_text = "a" * 500
        result = await client.generate("test", Intent.CONTINUE, {})
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_generate_confidence_increases_with_length(self, client):
        """Longer responses should have higher confidence (up to cap)."""
        client._provider._response_text = "hi"
        result_short = await client.generate("test", Intent.CONTINUE, {})

        client._provider._response_text = "a" * 300
        result_long = await client.generate("test", Intent.CONTINUE, {})

        assert result_long["confidence"] >= result_short["confidence"]

    @pytest.mark.asyncio
    async def test_generate_confidence_capped_at_095(self, client):
        """Confidence should never exceed 0.95."""
        client._provider._response_text = "a" * 10000
        result = await client.generate("test", Intent.CONTINUE, {})
        assert result["confidence"] <= 0.95

    @pytest.mark.asyncio
    async def test_generate_empty_candidate_confidence_zero(self, client):
        """Empty candidate should have confidence 0.0."""
        client._provider._response_text = ""
        result = await client.generate("test", Intent.CONTINUE, {})
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_generate_strips_whitespace(self, client):
        """Response text should be stripped of leading/trailing whitespace."""
        client._provider._response_text = "  spaced text  \n"
        result = await client.generate("test", Intent.CONTINUE, {})
        assert result["candidate"] == "spaced text"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test error handling in LLM client."""

    @pytest.fixture
    def client(self):
        mock_provider = MockProvider("result")
        with patch("backend.llm_client._create_provider", return_value=mock_provider):
            c = LLMClient(api_key="test-key")
            c._provider = mock_provider
            yield c

    @pytest.mark.asyncio
    async def test_auth_error_propagates(self, client):
        """LLMAuthenticationError should propagate."""
        client._provider.generate = AsyncMock(side_effect=LLMAuthenticationError("Invalid key"))
        with pytest.raises(LLMAuthenticationError):
            await client.generate("test", Intent.CONTINUE, {})

    @pytest.mark.asyncio
    async def test_rate_limit_error_propagates(self, client):
        """LLMRateLimitError should propagate."""
        client._provider.generate = AsyncMock(side_effect=LLMRateLimitError("Rate limit"))
        with pytest.raises(LLMRateLimitError):
            await client.generate("test", Intent.CONTINUE, {})

    @pytest.mark.asyncio
    async def test_generation_error_propagates(self, client):
        """LLMGenerationError should propagate."""
        client._provider.generate = AsyncMock(side_effect=LLMGenerationError("Gen failed"))
        with pytest.raises(LLMGenerationError):
            await client.generate("test", Intent.CONTINUE, {})

    @pytest.mark.asyncio
    async def test_custom_exceptions_inherit_from_llm_error(self):
        """All custom exceptions should inherit from LLMError."""
        assert issubclass(LLMAuthenticationError, LLMError)
        assert issubclass(LLMRateLimitError, LLMError)
        assert issubclass(LLMGenerationError, LLMError)


# ---------------------------------------------------------------------------
# Streaming response handling
# ---------------------------------------------------------------------------


class TestStreamingResponse:
    """Test generate_stream() method."""

    @pytest.fixture
    def client(self):
        mock_provider = MockProvider("Hello world !")
        with patch("backend.llm_client._create_provider", return_value=mock_provider):
            c = LLMClient(api_key="test-key")
            c._provider = mock_provider
            yield c

    @pytest.mark.asyncio
    async def test_stream_context_intent(self, client):
        """CONTEXT intent should yield 'Context updated' immediately."""
        client._provider.stream_calls.clear()
        chunks = []
        async for chunk in client.generate_stream("", Intent.CONTEXT, {}):
            chunks.append(chunk)
        assert chunks == ["Context updated"]
        assert len(client._provider.stream_calls) == 0

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self, client):
        """Streaming should yield text chunks from the provider."""
        chunks = []
        async for chunk in client.generate_stream("test", Intent.CONTINUE, {}):
            chunks.append(chunk)
        expected = ["Hello ", "world ", "!"]
        assert chunks == expected

    @pytest.mark.asyncio
    async def test_stream_error_propagates(self, client):
        """Provider errors during streaming should propagate."""
        async def error_stream(*args):
            raise LLMGenerationError("Stream error")
            yield  # make it an async generator

        client._provider.generate_stream = error_stream
        with pytest.raises(LLMGenerationError):
            async for _ in client.generate_stream("test", Intent.CONTINUE, {}):
                pass


# ---------------------------------------------------------------------------
# Confidence estimation (static method)
# ---------------------------------------------------------------------------


class TestConfidenceEstimation:
    """Test the _estimate_confidence static method."""

    def test_empty_string_returns_zero(self):
        assert LLMClient._estimate_confidence("") == 0.0

    def test_short_string(self):
        conf = LLMClient._estimate_confidence("hi")
        assert 0.7 <= conf < 0.75

    def test_medium_string(self):
        conf = LLMClient._estimate_confidence("a" * 100)
        assert 0.7 < conf < 0.95

    def test_long_string_capped(self):
        conf = LLMClient._estimate_confidence("a" * 10000)
        assert conf == 0.95

    def test_monotonically_increasing(self):
        c1 = LLMClient._estimate_confidence("a" * 10)
        c2 = LLMClient._estimate_confidence("a" * 100)
        c3 = LLMClient._estimate_confidence("a" * 500)
        assert c1 <= c2 <= c3
