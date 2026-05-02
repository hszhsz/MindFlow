"""Intent classifier for MindFlow.

Parses trigger patterns and classifies user intent.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class Intent(Enum):
    CONTINUE = "continue"
    MAIL = "mail"
    SUMMARY = "summary"
    POLISH = "polish"
    TRANSLATE = "translate"
    CONTEXT = "context"
    UNKNOWN = "unknown"


@dataclass
class ParsedInput:
    intent: Intent
    text: str
    extra: Optional[str] = None  # e.g., target language for translate


TRIGGER_PATTERNS = {
    ";;mail": Intent.MAIL,
    ";;summary": Intent.SUMMARY,
    ";;polish": Intent.POLISH,
    ";;context": Intent.CONTEXT,
    ";;translate": Intent.TRANSLATE,
}


def classify(text: str) -> ParsedInput:
    """Classify user input and extract intent.

    Args:
        text: Raw user input, may start with trigger pattern

    Returns:
        ParsedInput with intent, cleaned text, and any extra data
    """
    if not text:
        return ParsedInput(intent=Intent.UNKNOWN, text="")

    # Check for trigger patterns
    for pattern, intent in TRIGGER_PATTERNS.items():
        if text.startswith(pattern):
            remaining = text[len(pattern):].strip()
            if intent == Intent.TRANSLATE:
                # Extract target language if specified
                parts = remaining.split(maxsplit=1)
                lang = parts[0] if parts else "en"
                rest = parts[1] if len(parts) > 1 else ""
                return ParsedInput(intent=intent, text=rest, extra=lang)
            return ParsedInput(intent=intent, text=remaining)

    # Default: continue intent when starting with ;;
    if text.startswith(";;"):
        cleaned = text[2:].strip()
        return ParsedInput(intent=Intent.CONTINUE, text=cleaned)

    # No trigger, treat as plain continuation
    return ParsedInput(intent=Intent.CONTINUE, text=text)
