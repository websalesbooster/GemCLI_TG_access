"""Unit tests for session management."""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from app.session import (
    JsonFileSessionStore,
    ProcessingLock,
    SessionManager,
)
from app.types import ConversationKey


@pytest.fixture
def temp_storage():
    """Create temporary storage file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def session_store(temp_storage):
    """Create a JsonFileSessionStore for testing."""
    return JsonFileSessionStore(temp_storage)


@pytest.fixture
def session_manager(session_store):
    """Create a SessionManager for testing."""
    return SessionManager(session_store)


@pytest.fixture
def conversation_key():
    """Create a test conversation key."""
    return ConversationKey(chat_id=12345, user_id=67890)


class TestJsonFileSessionStore:
    """Tests for JsonFileSessionStore."""

    def test_initial_load_empty(self, temp_storage):
        """Test that new store starts with empty sessions."""
        store = JsonFileSessionStore(temp_storage)
        assert store._sessions == {}

    def test_set_and_get_session(self, session_store, conversation_key):
        """Test storing and retrieving a session."""
        asyncio.run(
            session_store.set_session(conversation_key, "thread_abc123")
        )
        result = asyncio.run(session_store.get_session(conversation_key))
        assert result == "thread_abc123"

    def test_get_nonexistent_session(self, session_store, conversation_key):
        """Test getting a session that doesn't exist."""
        result = asyncio.run(session_store.get_session(conversation_key))
        assert result is None

    def test_delete_session(self, session_store, conversation_key):
        """Test deleting a session."""
        asyncio.run(
            session_store.set_session(conversation_key, "thread_abc123")
        )
        asyncio.run(session_store.delete_session(conversation_key))
        result = asyncio.run(session_store.get_session(conversation_key))
        assert result is None

    def test_multiple_conversations(self, session_store):
        """Test storing sessions for multiple conversations."""
        key1 = ConversationKey(chat_id=111, user_id=222)
        key2 = ConversationKey(chat_id=333, user_id=444)

        asyncio.run(session_store.set_session(key1, "thread_1"))
        asyncio.run(session_store.set_session(key2, "thread_2"))

        assert asyncio.run(session_store.get_session(key1)) == "thread_1"
        assert asyncio.run(session_store.get_session(key2)) == "thread_2"

    def test_persistence_across_instances(self, temp_storage, conversation_key):
        """Test that sessions persist when creating new store instance."""
        store1 = JsonFileSessionStore(temp_storage)
        asyncio.run(store1.set_session(conversation_key, "thread_xyz"))

        store2 = JsonFileSessionStore(temp_storage)
        result = asyncio.run(store2.get_session(conversation_key))
        assert result == "thread_xyz"

    def test_corrupt_file_graceful_handling(self):
        """Test that corrupt JSON file is handled gracefully."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{ invalid json }")
            temp_path = Path(f.name)

        try:
            store = JsonFileSessionStore(temp_path)
            assert store._sessions == {}
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_missing_file_handling(self, temp_storage):
        """Test that missing file creates empty sessions."""
        temp_storage.unlink()
        store = JsonFileSessionStore(temp_storage)
        assert store._sessions == {}


class TestSessionManager:
    """Tests for SessionManager."""

    def test_get_session_id(self, session_manager, conversation_key):
        """Test getting session ID."""
        asyncio.run(
            session_manager.set_session_id(conversation_key, "thread_abc")
        )
        result = asyncio.run(session_manager.get_session_id(conversation_key))
        assert result == "thread_abc"

    def test_clear_session(self, session_manager, conversation_key):
        """Test clearing a session."""
        asyncio.run(
            session_manager.set_session_id(conversation_key, "thread_abc")
        )
        asyncio.run(session_manager.clear_session(conversation_key))
        result = asyncio.run(session_manager.get_session_id(conversation_key))
        assert result is None


class TestProcessingLock:
    """Tests for ProcessingLock."""

    @pytest.mark.asyncio
    async def test_acquire_and_release(self):
        """Test basic acquire and release."""
        lock_mgr = ProcessingLock()
        key = ConversationKey(chat_id=1, user_id=2)

        acquired = await lock_mgr.acquire(key)
        assert acquired is True

        await lock_mgr.release(key)

        # Should be able to acquire again
        acquired = await lock_mgr.acquire(key)
        assert acquired is True
        await lock_mgr.release(key)

    @pytest.mark.asyncio
    async def test_concurrent_rejection(self):
        """Test that concurrent request is rejected."""
        lock_mgr = ProcessingLock()
        key = ConversationKey(chat_id=1, user_id=2)

        # First acquire succeeds
        acquired1 = await lock_mgr.acquire(key)
        assert acquired1 is True

        # Second acquire should fail (lock already held)
        acquired2 = await lock_mgr.acquire(key)
        assert acquired2 is False

        await lock_mgr.release(key)

        # Now should succeed
        acquired3 = await lock_mgr.acquire(key)
        assert acquired3 is True
        await lock_mgr.release(key)

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using ProcessingLock as async context manager."""
        lock_mgr = ProcessingLock()
        key = ConversationKey(chat_id=1, user_id=2)

        async with lock_mgr(key):
            # Lock should be held
            acquired = await lock_mgr.acquire(key)
            assert acquired is False
            await lock_mgr.release(key)

        # After context, lock should be released
        acquired = await lock_mgr.acquire(key)
        assert acquired is True
        await lock_mgr.release(key)

    @pytest.mark.asyncio
    async def test_context_manager_raises_on_busy(self):
        """Test that context manager raises when lock unavailable."""
        lock_mgr = ProcessingLock()
        key = ConversationKey(chat_id=1, user_id=2)

        # Acquire first lock
        await lock_mgr.acquire(key)

        # Try to enter context - should raise
        with pytest.raises(RuntimeError, match="busy"):
            async with lock_mgr(key):
                pass

        await lock_mgr.release(key)

    @pytest.mark.asyncio
    async def test_different_conversations_independent(self):
        """Test that different conversation keys have independent locks."""
        lock_mgr = ProcessingLock()
        key1 = ConversationKey(chat_id=1, user_id=2)
        key2 = ConversationKey(chat_id=3, user_id=4)

        await lock_mgr.acquire(key1)
        acquired_key2 = await lock_mgr.acquire(key2)

        assert acquired_key2 is True

        await lock_mgr.release(key1)
        await lock_mgr.release(key2)