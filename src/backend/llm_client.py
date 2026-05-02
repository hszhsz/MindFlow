"""LLM client for MindFlow.

Handles communication with Claude API.
"""

import os
from typing import Optional
from anthropic import Anthropic
from .intent_classifier import Intent


SYSTEM_PROMPT = """你是一个智能输入法助手，名为 MindFlow。你的任务是帮助用户快速输入文字。

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
补全：「这个问题的解决方案»

用户输入：「;;邮件 项目进度延迟一周需要通知甲方」
补全：生成一封专业的邮件草稿

开始工作。"""


class LLMClient:
    """Client for LLM inference via Claude."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"

    async def generate(
        self,
        text: str,
        intent: Intent,
        context: dict
    ) -> dict:
        """Generate text completion.

        Args:
            text: User input text
            intent: Classified intent
            context: Session context

        Returns:
            {"candidate": str, "confidence": float}
        """
        if intent == Intent.MAIL:
            prompt = self._build_mail_prompt(text, context)
        elif intent == Intent.SUMMARY:
            prompt = self._build_summary_prompt(text, context)
        elif intent == Intent.POLISH:
            prompt = self._build_polish_prompt(text, context)
        elif intent == Intent.TRANSLATE:
            prompt = self._build_translate_prompt(text, context)
        elif intent == Intent.CONTEXT:
            return {"candidate": "Context updated", "confidence": 1.0}
        else:
            prompt = self._build_continue_prompt(text, context)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        candidate = response.content[0].text.strip()
        # Simple confidence based on response length
        confidence = min(0.95, 0.7 + len(candidate) / 1000)

        return {
            "candidate": candidate,
            "confidence": confidence,
            "model": self.model
        }

    def _build_continue_prompt(self, text: str, context: dict) -> str:
        return f"""继续下面的文本，保持相同的风格和语气。只输出补全内容，不要加任何解释或前缀。

文本：{text}"""

    def _build_mail_prompt(self, text: str, context: dict) -> str:
        return f"""根据以下信息，生成一封专业的中文邮件草稿。只输出邮件内容，不要加任何解释。

信息：{text}

邮件应该包含：称呼、正文、结尾语、签名。"""

    def _build_summary_prompt(self, text: str, context: dict) -> str:
        return f"""将以下内容整理成简洁的要点列表。只输出要点列表，不要加任何解释。

内容：{text}

格式要求：
- 使用 bullet points
- 每条不超过20字
- 保持原意"""

    def _build_polish_prompt(self, text: str, context: dict) -> str:
        return f"""改进并润色以下文本，使其更流畅、专业。只输出改写后的内容，不要加任何解释。

文本：{text}"""

    def _build_translate_prompt(self, text: str, context: dict) -> str:
        target = context.get("target_lang", "en")
        return f"""翻译以下文本到{target}。只输出翻译结果，不要加任何解释。

文本：{text}"""
