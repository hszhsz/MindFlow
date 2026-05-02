"""LLM client for MindFlow.

Handles all communication with the Claude API via the async Anthropic SDK.
Provides both single-shot generation and streaming generation methods.
Context from the ContextManager is injected into the system prompt so the
model is aware of the user's current environment and recent conversation.
"""

import logging
from typing import AsyncIterator, Optional

import anthropic
from anthropic import AsyncAnthropic

from .config import settings
from .context_manager import ContextManager
from .intent_classifier import Intent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Base exception for LLM-related errors."""


class LLMAuthenticationError(LLMError):
    """Raised when the API key is invalid or missing."""


class LLMRateLimitError(LLMError):
    """Raised when the API rate limit is exceeded."""


class LLMGenerationError(LLMError):
    """Raised when generation fails for any other reason."""


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

BASE_SYSTEM_PROMPT = """\
你是一个智能输入法助手，名为 MindFlow。你的任务是帮助用户快速输入文字。

你的特点：
1. 生成简洁、自然的文本补全
2. 理解中文语境和文化
3. 不生成无意义的填充词
4. 保持用户输入的语气和风格

当用户输入关键词或短语时，直接补全后面的内容，不要重复用户已经输入的部分。
补全内容应该符合上下文，自然衔接。

示例：
用户输入：「项目进度延迟一周」
补全：「，需要周三前通知甲方确认新的交付时间」

用户输入：「请帮我看一下」
补全：「这个问题的解决方案」

用户输入：「;;邮件 项目进度延迟一周需要通知甲方」
补全：生成一封专业的邮件草稿"""


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_system_prompt(context_block: str) -> str:
    """Assemble the full system prompt by injecting context."""
    if context_block:
        return f"{BASE_SYSTEM_PROMPT}\n\n{context_block}"
    return BASE_SYSTEM_PROMPT


def _build_continue_prompt(text: str, context: dict) -> str:
    """Build a prompt for free-form text continuation."""
    hint = ""
    app_type = context.get("app_type", "other")
    if app_type and app_type != "other":
        hint = f"\n（用户当前正在使用 {app_type}）"
    return (
        f"继续下面的文本，保持相同的风格和语气。"
        f"只输出补全内容，不要加任何解释或前缀。{hint}\n\n"
        f"文本：{text}"
    )


def _build_mail_prompt(text: str, context: dict) -> str:
    """Build a prompt for email drafting."""
    project = context.get("project")
    project_hint = f"\n项目背景：{project}" if project else ""
    return (
        f"根据以下信息，生成一封专业的中文邮件草稿。"
        f"只输出邮件内容，不要加任何解释。{project_hint}\n\n"
        f"信息：{text}\n\n"
        f"邮件应该包含：称呼、正文、结尾语、签名。"
    )


def _build_summary_prompt(text: str, context: dict) -> str:
    """Build a prompt for summarization."""
    return (
        "将以下内容整理成简洁的要点列表。只输出要点列表，不要加任何解释。\n\n"
        f"内容：{text}\n\n"
        "格式要求：\n"
        "- 使用 bullet points\n"
        "- 每条不超过20字\n"
        "- 保持原意"
    )


def _build_polish_prompt(text: str, context: dict) -> str:
    """Build a prompt for text polishing / rewriting."""
    return (
        "改进并润色以下文本，使其更流畅、专业。"
        "只输出改写后的内容，不要加任何解释。\n\n"
        f"文本：{text}"
    )


def _build_translate_prompt(text: str, context: dict) -> str:
    """Build a prompt for translation."""
    target = context.get("target_lang", "en")
    return (
        f"翻译以下文本到{target}。只输出翻译结果，不要加任何解释。\n\n"
        f"文本：{text}"
    )


# Map intents to prompt builders
_PROMPT_BUILDERS = {
    Intent.CONTINUE: _build_continue_prompt,
    Intent.MAIL: _build_mail_prompt,
    Intent.SUMMARY: _build_summary_prompt,
    Intent.POLISH: _build_polish_prompt,
    Intent.TRANSLATE: _build_translate_prompt,
}


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class LLMClient:
    """Async client for LLM inference via the Anthropic Claude API.

    Args:
        api_key: Anthropic API key.  Falls back to ``settings.anthropic_api_key``.
        context_manager: Optional ContextManager instance for prompt enrichment.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        context_manager: Optional[ContextManager] = None,
    ) -> None:
        self._api_key = api_key or settings.anthropic_api_key
        if not self._api_key:
            raise LLMAuthenticationError(
                "Anthropic API key is not set. "
                "Provide ANTHROPIC_API_KEY or MINDFLOW_ANTHROPIC_API_KEY."
            )
        self._client = AsyncAnthropic(api_key=self._api_key)
        self._model = settings.model_name
        self._max_tokens = settings.max_tokens
        self._context_manager = context_manager
        logger.info("LLMClient initialized (model=%s, max_tokens=%d)", self._model, self._max_tokens)

    @property
    def model(self) -> str:
        """The model identifier in use."""
        return self._model

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_system_prompt(self) -> str:
        """Build the system prompt, optionally enriched with context."""
        context_block = ""
        if self._context_manager:
            context_block = await self._context_manager.build_context_prompt()
        return _build_system_prompt(context_block)

    @staticmethod
    def _build_user_prompt(text: str, intent: Intent, context: dict) -> str:
        """Select the right prompt builder and produce the user message."""
        builder = _PROMPT_BUILDERS.get(intent, _build_continue_prompt)
        return builder(text, context)

    @staticmethod
    def _estimate_confidence(candidate: str) -> float:
        """Produce a simple heuristic confidence score.

        Longer, non-empty responses are considered higher-confidence.
        """
        if not candidate:
            return 0.0
        return min(0.95, 0.7 + len(candidate) / 1000)

    async def _handle_api_error(self, exc: Exception) -> None:
        """Translate Anthropic SDK exceptions into MindFlow exceptions."""
        if isinstance(exc, anthropic.AuthenticationError):
            logger.error("Anthropic authentication failed")
            raise LLMAuthenticationError("Invalid Anthropic API key") from exc
        if isinstance(exc, anthropic.RateLimitError):
            logger.warning("Anthropic rate limit hit")
            raise LLMRateLimitError("Rate limit exceeded; please retry later") from exc
        logger.exception("Anthropic API error")
        raise LLMGenerationError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        text: str,
        intent: Intent,
        context: dict,
    ) -> dict:
        """Generate a single text completion (non-streaming).

        Args:
            text: The cleaned user input (trigger prefix already removed).
            intent: The classified intent.
            context: Session context dict (from ContextManager.get_context).

        Returns:
            A dict with keys ``candidate`` (str), ``confidence`` (float),
            and ``model`` (str).

        Raises:
            LLMAuthenticationError: If the API key is invalid.
            LLMRateLimitError: If the rate limit is exceeded.
            LLMGenerationError: For all other generation failures.
        """
        if intent == Intent.CONTEXT:
            return {"candidate": "Context updated", "confidence": 1.0, "model": self._model}

        system_prompt = await self._get_system_prompt()
        user_prompt = self._build_user_prompt(text, intent, context)

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:
            await self._handle_api_error(exc)
            # _handle_api_error always raises; this line is unreachable
            raise  # pragma: no cover

        candidate = response.content[0].text.strip()
        confidence = self._estimate_confidence(candidate)
        logger.debug("Generated %d chars (confidence=%.2f)", len(candidate), confidence)

        return {
            "candidate": candidate,
            "confidence": confidence,
            "model": self._model,
        }

    async def generate_stream(
        self,
        text: str,
        intent: Intent,
        context: dict,
    ) -> AsyncIterator[str]:
        """Stream text completion chunks as they arrive.

        This is an async generator that yields text delta strings.
        Callers can iterate with ``async for chunk in client.generate_stream(...)``.

        Args:
            text: The cleaned user input.
            intent: The classified intent.
            context: Session context dict.

        Yields:
            Text chunks (str) as they are produced by the model.

        Raises:
            LLMAuthenticationError: If the API key is invalid.
            LLMRateLimitError: If the rate limit is exceeded.
            LLMGenerationError: For all other generation failures.
        """
        if intent == Intent.CONTEXT:
            yield "Context updated"
            return

        system_prompt = await self._get_system_prompt()
        user_prompt = self._build_user_prompt(text, intent, context)

        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                async for text_chunk in stream.text_stream:
                    yield text_chunk
        except Exception as exc:
            await self._handle_api_error(exc)
            raise  # pragma: no cover
