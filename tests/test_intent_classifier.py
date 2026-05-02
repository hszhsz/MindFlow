"""Tests for intent_classifier module."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from backend.intent_classifier import Intent, ParsedInput, classify


# ---------------------------------------------------------------------------
# Basic trigger patterns
# ---------------------------------------------------------------------------


class TestContinueIntent:
    """Test CONTINUE intent classification."""

    def test_double_semicolon_with_text(self):
        result = classify(";;text")
        assert result.intent == Intent.CONTINUE
        assert result.text == "text"

    def test_double_semicolon_with_spaced_text(self):
        result = classify(";;  some text here")
        assert result.intent == Intent.CONTINUE
        assert result.text == "some text here"

    def test_plain_text_without_trigger(self):
        """Plain text without ;; should still be CONTINUE."""
        result = classify("hello world")
        assert result.intent == Intent.CONTINUE
        assert result.text == "hello world"

    def test_plain_text_preserves_content(self):
        text = "The quick brown fox jumps over the lazy dog"
        result = classify(text)
        assert result.intent == Intent.CONTINUE
        assert result.text == text

    def test_single_semicolon_is_plain_text(self):
        """A single semicolon should not trigger."""
        result = classify(";hello")
        assert result.intent == Intent.CONTINUE
        assert result.text == ";hello"


class TestMailIntent:
    """Test MAIL intent classification."""

    def test_mail_trigger(self):
        result = classify(";;mail text")
        assert result.intent == Intent.MAIL
        assert result.text == "text"

    def test_mail_trigger_with_long_text(self):
        result = classify(";;mail please notify the client about the delay")
        assert result.intent == Intent.MAIL
        assert result.text == "please notify the client about the delay"

    def test_mail_trigger_no_text(self):
        result = classify(";;mail")
        assert result.intent == Intent.MAIL
        assert result.text == ""

    def test_mail_trigger_extra_spaces(self):
        result = classify(";;mail   lots of space")
        assert result.intent == Intent.MAIL
        assert result.text == "lots of space"


class TestSummaryIntent:
    """Test SUMMARY intent classification."""

    def test_summary_trigger(self):
        result = classify(";;summary text")
        assert result.intent == Intent.SUMMARY
        assert result.text == "text"

    def test_summary_trigger_multiword(self):
        result = classify(";;summary meeting notes from today")
        assert result.intent == Intent.SUMMARY
        assert result.text == "meeting notes from today"

    def test_summary_no_text(self):
        result = classify(";;summary")
        assert result.intent == Intent.SUMMARY
        assert result.text == ""


class TestPolishIntent:
    """Test POLISH intent classification."""

    def test_polish_trigger(self):
        result = classify(";;polish text")
        assert result.intent == Intent.POLISH
        assert result.text == "text"

    def test_polish_trigger_multiword(self):
        result = classify(";;polish this sentence needs improvement")
        assert result.intent == Intent.POLISH
        assert result.text == "this sentence needs improvement"

    def test_polish_no_text(self):
        result = classify(";;polish")
        assert result.intent == Intent.POLISH
        assert result.text == ""


class TestTranslateIntent:
    """Test TRANSLATE intent classification."""

    def test_translate_with_language_and_text(self):
        result = classify(";;translate en text")
        assert result.intent == Intent.TRANSLATE
        assert result.extra == "en"
        assert result.text == "text"

    def test_translate_with_language_and_long_text(self):
        result = classify(";;translate ja this is a longer sentence to translate")
        assert result.intent == Intent.TRANSLATE
        assert result.extra == "ja"
        assert result.text == "this is a longer sentence to translate"

    def test_translate_with_only_language(self):
        """If only a language code is given, text should be empty."""
        result = classify(";;translate en")
        assert result.intent == Intent.TRANSLATE
        assert result.extra == "en"
        assert result.text == ""

    def test_translate_no_args(self):
        """If no args, default language should be 'en'."""
        result = classify(";;translate")
        assert result.intent == Intent.TRANSLATE
        assert result.extra == "en"
        assert result.text == ""

    def test_translate_chinese_target(self):
        result = classify(";;translate zh hello world")
        assert result.intent == Intent.TRANSLATE
        assert result.extra == "zh"
        assert result.text == "hello world"

    def test_translate_language_code_heuristic(self):
        """Short ASCII tokens are treated as language codes."""
        result = classify(";;translate fr bonjour le monde")
        assert result.intent == Intent.TRANSLATE
        assert result.extra == "fr"
        assert result.text == "bonjour le monde"

    def test_translate_non_ascii_first_token_treated_as_text(self):
        """Non-ASCII first token should be treated as text, default lang 'en'."""
        result = classify(";;translate 你好世界")
        assert result.intent == Intent.TRANSLATE
        assert result.extra == "en"
        assert result.text == "你好世界"


class TestContextIntent:
    """Test CONTEXT intent classification."""

    def test_context_trigger(self):
        result = classify(";;context")
        assert result.intent == Intent.CONTEXT
        assert result.text == ""

    def test_context_trigger_with_text(self):
        result = classify(";;context some additional text")
        assert result.intent == Intent.CONTEXT
        assert result.text == "some additional text"


# ---------------------------------------------------------------------------
# Chinese variants
# ---------------------------------------------------------------------------


class TestChineseVariants:
    """Test that Chinese trigger keywords are recognized."""

    def test_chinese_mail(self):
        result = classify(";;邮件 通知大家周五开会")
        assert result.intent == Intent.MAIL
        assert result.text == "通知大家周五开会"

    def test_chinese_mail_no_text(self):
        result = classify(";;邮件")
        assert result.intent == Intent.MAIL
        assert result.text == ""

    def test_chinese_summary(self):
        result = classify(";;总结 今天的会议内容")
        assert result.intent == Intent.SUMMARY
        assert result.text == "今天的会议内容"

    def test_chinese_polish(self):
        result = classify(";;润色 这段文字需要润色")
        assert result.intent == Intent.POLISH
        assert result.text == "这段文字需要润色"

    def test_chinese_translate(self):
        result = classify(";;翻译 en 你好世界")
        assert result.intent == Intent.TRANSLATE
        assert result.extra == "en"
        assert result.text == "你好世界"

    def test_chinese_translate_no_lang(self):
        """Chinese translate with non-ASCII text defaults to 'en'."""
        result = classify(";;翻译 你好世界")
        assert result.intent == Intent.TRANSLATE
        assert result.extra == "en"
        assert result.text == "你好世界"

    def test_chinese_context(self):
        result = classify(";;上下文")
        assert result.intent == Intent.CONTEXT
        assert result.text == ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_input_returns_unknown(self):
        result = classify("")
        assert result.intent == Intent.UNKNOWN
        assert result.text == ""

    def test_none_input_returns_unknown(self):
        """None is falsy, so classify(None) returns UNKNOWN (same as empty)."""
        result = classify(None)
        assert result.intent == Intent.UNKNOWN
        assert result.text == ""

    def test_just_double_semicolon(self):
        """Just ';;' with no text should be CONTINUE with empty text."""
        result = classify(";;")
        assert result.intent == Intent.CONTINUE
        assert result.text == ""

    def test_triple_semicolon(self):
        """';;;' should be CONTINUE with ';' as text."""
        result = classify(";;;")
        assert result.intent == Intent.CONTINUE
        assert result.text == ";"

    def test_multiple_semicolons(self):
        """Many semicolons still triggers on first ;;."""
        result = classify(";;;;;;")
        assert result.intent == Intent.CONTINUE
        assert result.text == ";;;;"

    def test_whitespace_only(self):
        """Whitespace-only input is truthy but has no trigger."""
        result = classify("   ")
        assert result.intent == Intent.CONTINUE
        assert result.text == "   "

    def test_semicolons_in_middle(self):
        """Semicolons in the middle of text should not trigger."""
        result = classify("hello;;world")
        assert result.intent == Intent.CONTINUE
        assert result.text == "hello;;world"

    def test_trigger_case_sensitivity(self):
        """Triggers should be case-sensitive (;;MAIL should not match ;;mail)."""
        result = classify(";;MAIL hello")
        assert result.intent == Intent.CONTINUE
        assert result.text == "MAIL hello"

    def test_extra_is_none_for_non_translate(self):
        """Extra field should be None for non-TRANSLATE intents."""
        result = classify(";;mail hello")
        assert result.extra is None

    def test_unicode_text_preserved(self):
        """Unicode characters should be preserved."""
        result = classify("你好世界")
        assert result.intent == Intent.CONTINUE
        assert result.text == "你好世界"

    def test_newlines_in_text(self):
        """Newlines should be preserved in text."""
        result = classify(";;mail line1\nline2\nline3")
        assert result.intent == Intent.MAIL
        assert "line1\nline2\nline3" in result.text

    def test_longest_prefix_match(self):
        """Longer Chinese triggers should match before shorter ;; prefix."""
        # ;;邮件 is longer than ;; so should match MAIL, not CONTINUE
        result = classify(";;邮件 内容")
        assert result.intent == Intent.MAIL
        assert result.text == "内容"

    def test_translate_five_char_ascii_lang_code(self):
        """A 5-char ASCII token should be treated as language code."""
        result = classify(";;translate pt-BR some text")
        assert result.intent == Intent.TRANSLATE
        assert result.extra == "pt-BR"
        assert result.text == "some text"


# ---------------------------------------------------------------------------
# ParsedInput dataclass
# ---------------------------------------------------------------------------


class TestParsedInput:
    """Test the ParsedInput dataclass."""

    def test_default_extra_is_none(self):
        pi = ParsedInput(intent=Intent.CONTINUE, text="hello")
        assert pi.extra is None

    def test_with_extra(self):
        pi = ParsedInput(intent=Intent.TRANSLATE, text="hello", extra="en")
        assert pi.extra == "en"

    def test_equality(self):
        a = ParsedInput(intent=Intent.MAIL, text="hello")
        b = ParsedInput(intent=Intent.MAIL, text="hello")
        assert a == b

    def test_inequality(self):
        a = ParsedInput(intent=Intent.MAIL, text="hello")
        b = ParsedInput(intent=Intent.MAIL, text="world")
        assert a != b
