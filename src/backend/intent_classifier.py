"""Intent classifier for MindFlow.

Parses trigger patterns from user input and classifies the intended action.
Supports both English and Chinese trigger keywords prefixed with ';;'.

Trigger patterns:
    ;;mail / ;;邮件       - Draft an email from the input
    ;;summary / ;;总结    - Summarize the input into bullet points
    ;;polish / ;;润色     - Rewrite input for clarity and professionalism
    ;;translate / ;;翻译  - Translate input to a target language
    ;;context / ;;上下文  - Update session context metadata
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class Intent(Enum):
    """Possible user intents recognized by the classifier."""

    CONTINUE = "continue"
    MAIL = "mail"
    SUMMARY = "summary"
    POLISH = "polish"
    TRANSLATE = "translate"
    CONTEXT = "context"
    UNKNOWN = "unknown"


@dataclass
class ParsedInput:
    """Result of classifying raw user input.

    Attributes:
        intent: The detected intent category.
        text: The cleaned text with the trigger prefix removed.
        extra: Optional additional data (e.g., target language for translate).
    """

    intent: Intent
    text: str
    extra: Optional[str] = None


# Mapping from trigger prefix to intent.
# Both English and Chinese variants are supported.
TRIGGER_PATTERNS: dict[str, Intent] = {
    ";;mail": Intent.MAIL,
    ";;邮件": Intent.MAIL,
    ";;summary": Intent.SUMMARY,
    ";;总结": Intent.SUMMARY,
    ";;polish": Intent.POLISH,
    ";;润色": Intent.POLISH,
    ";;translate": Intent.TRANSLATE,
    ";;翻译": Intent.TRANSLATE,
    ";;context": Intent.CONTEXT,
    ";;上下文": Intent.CONTEXT,
}


def classify(text: str) -> ParsedInput:
    """Classify user input and extract the underlying intent.

    The function checks whether the input starts with a known trigger pattern.
    If a trigger is found, it strips the prefix and returns the cleaned text
    along with the matched intent.

    For the translate intent, the first token after the trigger is treated as
    the target language code (defaults to 'en' if not provided).

    Args:
        text: Raw user input string, possibly starting with a ';;' trigger.

    Returns:
        A ParsedInput instance containing the classified intent,
        the cleaned text body, and optional extra metadata.

    Examples:
        >>> classify(";;mail 通知大家周五开会")
        ParsedInput(intent=Intent.MAIL, text='通知大家周五开会', extra=None)

        >>> classify(";;翻译 en 你好世界")
        ParsedInput(intent=Intent.TRANSLATE, text='你好世界', extra='en')

        >>> classify("今天天气不错")
        ParsedInput(intent=Intent.CONTINUE, text='今天天气不错', extra=None)
    """
    if not text:
        return ParsedInput(intent=Intent.UNKNOWN, text="")

    # Check for trigger patterns (sorted longest-first to avoid prefix conflicts)
    for pattern, intent in sorted(TRIGGER_PATTERNS.items(), key=lambda x: -len(x[0])):
        if text.startswith(pattern):
            remaining = text[len(pattern):].strip()

            if intent == Intent.TRANSLATE:
                # Extract optional target language as the first whitespace-separated token
                parts = remaining.split(maxsplit=1)
                if len(parts) == 2:
                    lang, body = parts
                elif len(parts) == 1:
                    # Could be just the language or just the text.
                    # Heuristic: if it looks like a language code (2-5 chars, ASCII), treat as lang.
                    token = parts[0]
                    if token.isascii() and len(token) <= 5:
                        lang, body = token, ""
                    else:
                        lang, body = "en", token
                else:
                    lang, body = "en", ""
                return ParsedInput(intent=intent, text=body, extra=lang)

            return ParsedInput(intent=intent, text=remaining)

    # Double-semicolon without a known trigger: treat as a continue command
    if text.startswith(";;"):
        cleaned = text[2:].strip()
        return ParsedInput(intent=Intent.CONTINUE, text=cleaned)

    # No trigger prefix: plain continuation
    return ParsedInput(intent=Intent.CONTINUE, text=text)
