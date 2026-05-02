"""Context manager for MindFlow.

Provides short-term (session) and long-term (disk-persisted) memory.
Session context includes recent conversation turns, current application type,
active project, and topic. Long-term memory stores per-project metadata
in ~/.mindflow/memory.json.

Thread-safety for the session state is ensured via an asyncio.Lock, since
the FastAPI server may process multiple concurrent requests that read or
mutate context.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

from .config import settings

logger = logging.getLogger(__name__)

# Long-term memory storage path
MEMORY_DIR = Path.home() / ".mindflow"
MEMORY_FILE = MEMORY_DIR / "memory.json"


@dataclass
class Turn:
    """A single conversation turn.

    Attributes:
        user: The raw user input.
        assistant: The generated assistant response.
        intent: The classified intent label for this turn.
    """

    user: str
    assistant: str
    intent: str


@dataclass
class SessionContext:
    """Mutable session state for the current interaction window.

    Attributes:
        project: Currently active project name, if any.
        topic: Current topic within the project.
        app_type: The type of application the user is working in
                  (e.g. 'code_editor', 'email', 'chat', 'browser', 'other').
        language: Primary language code (e.g. 'zh', 'en').
        history: Rolling window of recent conversation turns.
    """

    project: Optional[str] = None
    topic: Optional[str] = None
    app_type: str = "other"
    language: str = "zh"
    history: List[Turn] = field(default_factory=list)

    def add_turn(self, user: str, assistant: str, intent: str) -> None:
        """Append a turn and enforce the history size limit."""
        self.history.append(Turn(user=user, assistant=assistant, intent=intent))
        max_size = settings.context_history_size
        if len(self.history) > max_size:
            self.history = self.history[-max_size:]


class ContextManager:
    """Manages both short-term session and long-term persisted context.

    All public methods that mutate state are async and protected by an
    internal asyncio.Lock for safe concurrent access.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.session = SessionContext()
        self._ensure_memory_dir()
        self._load_long_term()
        logger.info("ContextManager initialized (history_size=%d)", settings.context_history_size)

    # ------------------------------------------------------------------
    # Long-term memory persistence
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_memory_dir() -> None:
        """Create the memory directory if it does not exist."""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def _load_long_term(self) -> None:
        """Load long-term memory from disk."""
        if MEMORY_FILE.exists():
            try:
                data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
                self.long_term: dict = data.get("projects", {})
                self.current_project: Optional[str] = data.get("current_project")
                logger.debug("Loaded long-term memory with %d projects", len(self.long_term))
            except Exception:
                logger.exception("Failed to load long-term memory; starting fresh")
                self.long_term = {}
                self.current_project = None
        else:
            self.long_term = {}
            self.current_project = None

    def _save_long_term(self) -> None:
        """Persist long-term memory to disk (sync, called under lock)."""
        data = {
            "projects": self.long_term,
            "current_project": self.current_project,
        }
        try:
            MEMORY_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to persist long-term memory")

    # ------------------------------------------------------------------
    # Context retrieval
    # ------------------------------------------------------------------

    async def get_context(self) -> dict:
        """Return a snapshot of the current session context as a plain dict.

        The dict contains keys: project, topic, app_type, language,
        recent_history (list of {user, assistant} dicts for the last 5 turns).
        """
        async with self._lock:
            return {
                "project": self.session.project,
                "topic": self.session.topic,
                "app_type": self.session.app_type,
                "language": self.session.language,
                "recent_history": [
                    {"user": t.user, "assistant": t.assistant}
                    for t in self.session.history[-5:]
                ],
            }

    async def build_context_prompt(self) -> str:
        """Build a compact context string suitable for injection into LLM prompts.

        The string is designed to be prepended (or appended) to the system
        prompt so the model is aware of the user's environment, project, and
        recent conversation.

        Returns:
            A human-readable context block. Returns an empty string if there
            is nothing meaningful to include.
        """
        async with self._lock:
            parts: list[str] = []

            if self.session.app_type and self.session.app_type != "other":
                parts.append(f"Application: {self.session.app_type}")

            if self.session.project:
                parts.append(f"Project: {self.session.project}")

            if self.session.topic:
                parts.append(f"Topic: {self.session.topic}")

            if self.session.language:
                parts.append(f"Language: {self.session.language}")

            # Include recent history as a compact transcript
            if self.session.history:
                recent = self.session.history[-5:]
                lines = []
                for turn in recent:
                    lines.append(f"  User: {turn.user}")
                    lines.append(f"  Assistant: {turn.assistant}")
                parts.append("Recent conversation:\n" + "\n".join(lines))

            # Include project context from long-term memory if available
            if self.session.project and self.session.project in self.long_term:
                proj = self.long_term[self.session.project]
                topics = proj.get("topics", [])
                if topics:
                    parts.append(f"Project topics: {', '.join(topics[-5:])}")

            if not parts:
                return ""

            return "[Context]\n" + "\n".join(parts) + "\n[/Context]"

    # ------------------------------------------------------------------
    # Context mutation
    # ------------------------------------------------------------------

    async def update_session(
        self,
        app_type: Optional[str] = None,
        language: Optional[str] = None,
        project: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> None:
        """Update session context fields.

        Only non-None arguments are applied. Setting a project also updates
        long-term memory.
        """
        async with self._lock:
            if app_type:
                self.session.app_type = app_type
            if language:
                self.session.language = language
            if project:
                self.session.project = project
                self.current_project = project
                if project not in self.long_term:
                    self.long_term[project] = {"topics": [], "context": {}}
            if topic:
                self.session.topic = topic
                if self.current_project:
                    topics_list = self.long_term[self.current_project]["topics"]
                    if topic not in topics_list:
                        topics_list.append(topic)
                self._save_long_term()
            logger.debug(
                "Session updated: app_type=%s, project=%s, topic=%s",
                self.session.app_type,
                self.session.project,
                self.session.topic,
            )

    async def add_turn(self, user: str, assistant: str, intent: str) -> None:
        """Record a conversation turn in session history."""
        async with self._lock:
            self.session.add_turn(user, assistant, intent)

    def get_project_context(self, project: str) -> Optional[dict]:
        """Get long-term context for a specific project (sync, read-only)."""
        return self.long_term.get(project)

    async def forget(self, scope: str = "session") -> None:
        """Clear memory.

        Args:
            scope: 'session' clears the current session only.
                   'all' clears both session and long-term memory.
        """
        async with self._lock:
            if scope == "session":
                self.session = SessionContext()
                logger.info("Session context cleared")
            elif scope == "all":
                self.session = SessionContext()
                self.long_term = {}
                self.current_project = None
                if MEMORY_FILE.exists():
                    MEMORY_FILE.unlink()
                logger.info("All context cleared (session + long-term)")
