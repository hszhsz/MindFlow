"""Tests for context_manager module."""

import asyncio
import json
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from backend.context_manager import ContextManager, SessionContext, Turn


# ---------------------------------------------------------------------------
# SessionContext tests
# ---------------------------------------------------------------------------


class TestSessionContext:
    """Test the SessionContext dataclass."""

    def test_defaults(self):
        ctx = SessionContext()
        assert ctx.project is None
        assert ctx.topic is None
        assert ctx.app_type == "other"
        assert ctx.language == "zh"
        assert ctx.history == []

    def test_custom_values(self):
        ctx = SessionContext(
            project="MindFlow", topic="testing", app_type="email", language="en"
        )
        assert ctx.project == "MindFlow"
        assert ctx.topic == "testing"
        assert ctx.app_type == "email"
        assert ctx.language == "en"

    def test_history_starts_empty(self):
        ctx = SessionContext()
        assert len(ctx.history) == 0

    def test_add_turn(self):
        ctx = SessionContext()
        ctx.add_turn(user="hello", assistant="hi there", intent="continue")
        assert len(ctx.history) == 1
        assert ctx.history[0].user == "hello"
        assert ctx.history[0].assistant == "hi there"
        assert ctx.history[0].intent == "continue"

    def test_history_truncation_at_configured_limit(self, monkeypatch):
        """History should be truncated to context_history_size (default 20)."""
        monkeypatch.setattr("backend.context_manager.settings.context_history_size", 20)
        ctx = SessionContext()
        for i in range(25):
            ctx.add_turn(user=f"msg-{i}", assistant=f"resp-{i}", intent="continue")

        assert len(ctx.history) == 20
        # The first entry should be msg-5 (earliest five were dropped)
        assert ctx.history[0].user == "msg-5"
        assert ctx.history[-1].user == "msg-24"

    def test_history_truncation_boundary(self, monkeypatch):
        """Adding the (limit+1)th turn should trigger truncation."""
        monkeypatch.setattr("backend.context_manager.settings.context_history_size", 20)
        ctx = SessionContext()
        for i in range(20):
            ctx.add_turn(user=f"msg-{i}", assistant=f"resp-{i}", intent="continue")
        assert len(ctx.history) == 20

        ctx.add_turn(user="msg-20", assistant="resp-20", intent="continue")
        assert len(ctx.history) == 20
        assert ctx.history[0].user == "msg-1"

    def test_history_truncation_with_custom_limit(self, monkeypatch):
        """History respects custom context_history_size."""
        monkeypatch.setattr("backend.context_manager.settings.context_history_size", 5)
        ctx = SessionContext()
        for i in range(10):
            ctx.add_turn(user=f"msg-{i}", assistant=f"resp-{i}", intent="continue")

        assert len(ctx.history) == 5
        assert ctx.history[0].user == "msg-5"
        assert ctx.history[-1].user == "msg-9"


# ---------------------------------------------------------------------------
# Turn dataclass
# ---------------------------------------------------------------------------


class TestTurn:
    """Test the Turn dataclass."""

    def test_creation(self):
        t = Turn(user="hello", assistant="world", intent="continue")
        assert t.user == "hello"
        assert t.assistant == "world"
        assert t.intent == "continue"

    def test_equality(self):
        a = Turn(user="hello", assistant="world", intent="continue")
        b = Turn(user="hello", assistant="world", intent="continue")
        assert a == b


# ---------------------------------------------------------------------------
# ContextManager: Session operations (async)
# ---------------------------------------------------------------------------


class TestContextManagerSession:
    """Test ContextManager session operations."""

    @pytest.mark.asyncio
    async def test_initial_session(self, context_manager):
        """A fresh ContextManager should have default session."""
        ctx = await context_manager.get_context()
        assert ctx["project"] is None
        assert ctx["topic"] is None
        assert ctx["app_type"] == "other"
        assert ctx["language"] == "zh"
        assert ctx["recent_history"] == []

    @pytest.mark.asyncio
    async def test_update_session_app_type(self, context_manager):
        await context_manager.update_session(app_type="email")
        ctx = await context_manager.get_context()
        assert ctx["app_type"] == "email"

    @pytest.mark.asyncio
    async def test_update_session_language(self, context_manager):
        await context_manager.update_session(language="en")
        ctx = await context_manager.get_context()
        assert ctx["language"] == "en"

    @pytest.mark.asyncio
    async def test_update_session_project(self, context_manager):
        await context_manager.update_session(project="TestProject")
        ctx = await context_manager.get_context()
        assert ctx["project"] == "TestProject"
        assert context_manager.current_project == "TestProject"

    @pytest.mark.asyncio
    async def test_update_session_topic(self, context_manager):
        await context_manager.update_session(project="TestProject", topic="testing")
        ctx = await context_manager.get_context()
        assert ctx["topic"] == "testing"

    @pytest.mark.asyncio
    async def test_update_session_multiple_fields(self, context_manager):
        await context_manager.update_session(
            app_type="code", language="en", project="MF", topic="api"
        )
        ctx = await context_manager.get_context()
        assert ctx["app_type"] == "code"
        assert ctx["language"] == "en"
        assert ctx["project"] == "MF"
        assert ctx["topic"] == "api"

    @pytest.mark.asyncio
    async def test_add_turn_appears_in_context(self, context_manager):
        await context_manager.add_turn(user="hello", assistant="hi", intent="continue")
        ctx = await context_manager.get_context()
        assert len(ctx["recent_history"]) == 1
        assert ctx["recent_history"][0]["user"] == "hello"
        assert ctx["recent_history"][0]["assistant"] == "hi"

    @pytest.mark.asyncio
    async def test_recent_history_limited_to_5(self, context_manager):
        """get_context() should return only the last 5 turns."""
        for i in range(8):
            await context_manager.add_turn(
                user=f"msg-{i}", assistant=f"resp-{i}", intent="continue"
            )
        ctx = await context_manager.get_context()
        assert len(ctx["recent_history"]) == 5
        assert ctx["recent_history"][0]["user"] == "msg-3"
        assert ctx["recent_history"][-1]["user"] == "msg-7"


# ---------------------------------------------------------------------------
# ContextManager: Context prompt building
# ---------------------------------------------------------------------------


class TestContextPromptBuilding:
    """Test that context dict and prompt are properly structured."""

    @pytest.mark.asyncio
    async def test_context_dict_keys(self, context_manager):
        ctx = await context_manager.get_context()
        expected_keys = {"project", "topic", "app_type", "language", "recent_history"}
        assert set(ctx.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_context_with_full_session(self, context_manager):
        await context_manager.update_session(
            project="MindFlow", topic="API design", app_type="docs", language="en"
        )
        await context_manager.add_turn(user="q1", assistant="a1", intent="continue")

        ctx = await context_manager.get_context()
        assert ctx["project"] == "MindFlow"
        assert ctx["topic"] == "API design"
        assert ctx["app_type"] == "docs"
        assert ctx["language"] == "en"
        assert len(ctx["recent_history"]) == 1

    @pytest.mark.asyncio
    async def test_history_items_have_user_and_assistant(self, context_manager):
        await context_manager.add_turn(user="u", assistant="a", intent="continue")
        ctx = await context_manager.get_context()
        history_entry = ctx["recent_history"][0]
        assert set(history_entry.keys()) == {"user", "assistant"}

    @pytest.mark.asyncio
    async def test_build_context_prompt_default_includes_language(self, context_manager):
        """Default session has language='zh' so prompt includes it."""
        prompt = await context_manager.build_context_prompt()
        # Default session has language set, so prompt is not empty
        assert "[Context]" in prompt
        assert "zh" in prompt

    @pytest.mark.asyncio
    async def test_build_context_prompt_with_app_type(self, context_manager):
        await context_manager.update_session(app_type="email")
        prompt = await context_manager.build_context_prompt()
        assert "[Context]" in prompt
        assert "email" in prompt

    @pytest.mark.asyncio
    async def test_build_context_prompt_with_project(self, context_manager):
        await context_manager.update_session(project="MindFlow", topic="testing")
        prompt = await context_manager.build_context_prompt()
        assert "MindFlow" in prompt
        assert "testing" in prompt

    @pytest.mark.asyncio
    async def test_build_context_prompt_with_history(self, context_manager):
        await context_manager.add_turn(user="hello", assistant="hi", intent="continue")
        prompt = await context_manager.build_context_prompt()
        assert "hello" in prompt
        assert "hi" in prompt
        assert "Recent conversation" in prompt

    @pytest.mark.asyncio
    async def test_build_context_prompt_includes_project_topics(self, context_manager):
        await context_manager.update_session(project="P1", topic="T1")
        await context_manager.update_session(topic="T2")
        prompt = await context_manager.build_context_prompt()
        assert "Project topics" in prompt
        assert "T1" in prompt
        assert "T2" in prompt


# ---------------------------------------------------------------------------
# ContextManager: Long-term memory save/load
# ---------------------------------------------------------------------------


class TestLongTermMemory:
    """Test long-term memory persistence."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, tmp_path, monkeypatch):
        """Memory should persist across ContextManager instances."""
        monkeypatch.setattr("backend.context_manager.MEMORY_DIR", tmp_path)
        monkeypatch.setattr(
            "backend.context_manager.MEMORY_FILE", tmp_path / "memory.json"
        )

        # First instance: create some data
        cm1 = ContextManager()
        await cm1.update_session(project="TestProject", topic="topic1")

        # Second instance: should load the saved data
        cm2 = ContextManager()
        assert "TestProject" in cm2.long_term
        assert "topic1" in cm2.long_term["TestProject"]["topics"]
        assert cm2.current_project == "TestProject"

    @pytest.mark.asyncio
    async def test_memory_file_created(self, tmp_path, monkeypatch):
        """Saving should create the memory file."""
        monkeypatch.setattr("backend.context_manager.MEMORY_DIR", tmp_path)
        mem_file = tmp_path / "memory.json"
        monkeypatch.setattr("backend.context_manager.MEMORY_FILE", mem_file)

        cm = ContextManager()
        await cm.update_session(project="P1", topic="T1")

        assert mem_file.exists()
        data = json.loads(mem_file.read_text())
        assert data["current_project"] == "P1"
        assert "P1" in data["projects"]

    @pytest.mark.asyncio
    async def test_corrupt_memory_file(self, tmp_path, monkeypatch):
        """Corrupt memory file should be handled gracefully."""
        monkeypatch.setattr("backend.context_manager.MEMORY_DIR", tmp_path)
        mem_file = tmp_path / "memory.json"
        monkeypatch.setattr("backend.context_manager.MEMORY_FILE", mem_file)
        mem_file.write_text("NOT VALID JSON {{{")

        cm = ContextManager()
        assert cm.long_term == {}
        assert cm.current_project is None

    @pytest.mark.asyncio
    async def test_no_memory_file(self, tmp_path, monkeypatch):
        """Missing memory file should result in empty state."""
        monkeypatch.setattr("backend.context_manager.MEMORY_DIR", tmp_path)
        monkeypatch.setattr(
            "backend.context_manager.MEMORY_FILE", tmp_path / "memory.json"
        )

        cm = ContextManager()
        assert cm.long_term == {}
        assert cm.current_project is None

    @pytest.mark.asyncio
    async def test_multiple_projects(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.context_manager.MEMORY_DIR", tmp_path)
        monkeypatch.setattr(
            "backend.context_manager.MEMORY_FILE", tmp_path / "memory.json"
        )

        cm = ContextManager()
        await cm.update_session(project="Project1", topic="t1")
        await cm.update_session(project="Project2", topic="t2")

        assert "Project1" in cm.long_term
        assert "Project2" in cm.long_term

    def test_get_project_context(self, context_manager):
        """get_project_context is sync and returns project info."""
        # Directly manipulate long_term since get_project_context is sync
        context_manager.long_term["P1"] = {"topics": ["T1"], "context": {}}
        result = context_manager.get_project_context("P1")
        assert result is not None
        assert "T1" in result["topics"]

    def test_get_project_context_missing(self, context_manager):
        result = context_manager.get_project_context("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# ContextManager: Forget
# ---------------------------------------------------------------------------


class TestForget:
    """Test memory clearing functionality."""

    @pytest.mark.asyncio
    async def test_forget_session(self, context_manager):
        await context_manager.update_session(project="P1", app_type="email")
        await context_manager.add_turn(user="u", assistant="a", intent="continue")

        await context_manager.forget(scope="session")

        ctx = await context_manager.get_context()
        assert ctx["project"] is None
        assert ctx["app_type"] == "other"
        assert ctx["recent_history"] == []

    @pytest.mark.asyncio
    async def test_forget_session_preserves_long_term(self, context_manager):
        """Forgetting session should not affect long-term memory."""
        await context_manager.update_session(project="P1", topic="T1")
        await context_manager.forget(scope="session")

        # Long-term memory should still have P1
        assert "P1" in context_manager.long_term

    @pytest.mark.asyncio
    async def test_forget_all(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.context_manager.MEMORY_DIR", tmp_path)
        mem_file = tmp_path / "memory.json"
        monkeypatch.setattr("backend.context_manager.MEMORY_FILE", mem_file)

        cm = ContextManager()
        await cm.update_session(project="P1", topic="T1")
        assert mem_file.exists()

        await cm.forget(scope="all")

        assert cm.long_term == {}
        assert cm.current_project is None
        assert cm.session.project is None
        assert not mem_file.exists()

    @pytest.mark.asyncio
    async def test_forget_all_without_file(self, tmp_path, monkeypatch):
        """Forget all should not fail if memory file doesn't exist."""
        monkeypatch.setattr("backend.context_manager.MEMORY_DIR", tmp_path)
        monkeypatch.setattr(
            "backend.context_manager.MEMORY_FILE", tmp_path / "memory.json"
        )

        cm = ContextManager()
        await cm.forget(scope="all")  # Should not raise
        assert cm.long_term == {}


# ---------------------------------------------------------------------------
# Thread safety / Concurrency
# ---------------------------------------------------------------------------


class TestConcurrency:
    """Test concurrent async access to ContextManager."""

    @pytest.mark.asyncio
    async def test_concurrent_add_turns(self, context_manager):
        """Multiple concurrent add_turn calls should not corrupt state."""

        async def add_batch(start_idx):
            for i in range(20):
                await context_manager.add_turn(
                    user=f"t{start_idx}-msg{i}",
                    assistant=f"t{start_idx}-resp{i}",
                    intent="continue",
                )

        await asyncio.gather(*(add_batch(t) for t in range(5)))

        # History should not exceed the configured limit (default 20)
        from backend.config import settings
        assert len(context_manager.session.history) <= settings.context_history_size

    @pytest.mark.asyncio
    async def test_concurrent_update_session(self, context_manager):
        """Multiple concurrent update_session calls should not raise."""

        async def update(idx):
            await context_manager.update_session(
                app_type=f"type-{idx}", language=f"lang-{idx}"
            )

        await asyncio.gather(*(update(i) for i in range(10)))

        # Session should have some valid state (last writer wins)
        ctx = await context_manager.get_context()
        assert ctx["app_type"].startswith("type-")
        assert ctx["language"].startswith("lang-")

    @pytest.mark.asyncio
    async def test_concurrent_read_write(self, context_manager):
        """Concurrent reads and writes should not raise."""

        async def writer():
            for i in range(20):
                await context_manager.add_turn(
                    user=f"w-{i}", assistant=f"r-{i}", intent="continue"
                )

        async def reader():
            for _ in range(20):
                await context_manager.get_context()

        await asyncio.gather(writer(), reader())
        # If we reach here without exception, concurrency is safe
