"""Context manager for MindFlow.

Handles short-term (session) and long-term memory.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Optional
from pathlib import Path


@dataclass
class Turn:
    """A single conversation turn."""
    user: str
    assistant: str
    intent: str


@dataclass
class SessionContext:
    """Current session context."""
    project: Optional[str] = None
    topic: Optional[str] = None
    app_type: str = "other"
    language: str = "zh"
    history: List[Turn] = None

    def __post_init__(self):
        if self.history is None:
            self.history = []

    def add_turn(self, user: str, assistant: str, intent: str):
        self.history.append(Turn(user=user, assistant=assistant, intent=intent))
        # Keep only last 10 turns
        if len(self.history) > 10:
            self.history = self.history[-10:]


# Long-term memory storage path
MEMORY_DIR = Path.home() / ".mindflow"
MEMORY_FILE = MEMORY_DIR / "memory.json"


class ContextManager:
    """Manages both short-term and long-term context."""

    def __init__(self):
        self.session = SessionContext()
        self._ensure_memory_dir()
        self._load_long_term()

    def _ensure_memory_dir(self):
        MEMORY_DIR.mkdir(exist_ok=True)

    def _load_long_term(self):
        """Load long-term memory from disk."""
        if MEMORY_FILE.exists():
            try:
                data = json.loads(MEMORY_FILE.read_text())
                self.long_term = data.get("projects", {})
                self.current_project = data.get("current_project")
            except Exception:
                self.long_term = {}
                self.current_project = None
        else:
            self.long_term = {}
            self.current_project = None

    def _save_long_term(self):
        """Persist long-term memory to disk."""
        data = {
            "projects": self.long_term,
            "current_project": self.current_project
        }
        MEMORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def get_context(self) -> dict:
        """Get current context for LLM prompts."""
        return {
            "project": self.session.project,
            "topic": self.session.topic,
            "app_type": self.session.app_type,
            "language": self.session.language,
            "recent_history": [
                {"user": t.user, "assistant": t.assistant}
                for t in self.session.history[-3:]
            ]
        }

    def update_session(self, app_type: Optional[str] = None,
                       language: Optional[str] = None,
                       project: Optional[str] = None,
                       topic: Optional[str] = None):
        """Update session context."""
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
            if self.current_project and topic not in self.long_term[self.current_project]["topics"]:
                self.long_term[self.current_project]["topics"].append(topic)
            self._save_long_term()

    def add_turn(self, user: str, assistant: str, intent: str):
        self.session.add_turn(user, assistant, intent)

    def get_project_context(self, project: str) -> Optional[dict]:
        """Get context for a specific project from long-term memory."""
        return self.long_term.get(project)

    def forget(self, scope: str = "session"):
        """Clear memory.

        Args:
            scope: "session" clears current session, "all" clears everything
        """
        if scope == "session":
            self.session = SessionContext()
        elif scope == "all":
            self.session = SessionContext()
            self.long_term = {}
            self.current_project = None
            if MEMORY_FILE.exists():
                MEMORY_FILE.unlink()
