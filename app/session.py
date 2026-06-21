"""Session management for the Telegram-Codex Gateway."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Protocol

from app.types import ConversationKey

logger = logging.getLogger(__name__)


class SessionStore(Protocol):
    """Protocol for session persistence backends."""

    async def get_session(self, key: ConversationKey) -> str | None:
        """Retrieve thread ID for conversation."""
        ...

    async def set_session(self, key: ConversationKey, thread_id: str) -> None:
        """Store thread ID for conversation."""
        ...

    async def delete_session(self, key: ConversationKey) -> None:
        """Remove session for conversation."""
        ...


class JsonFileSessionStore:
    """Session store implementation using JSON file persistence."""

    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path
        self._sessions: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._load()

    def _load(self) -> None:
        """Load sessions from JSON file."""
        try:
            if self._storage_path.exists():
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._sessions = data.get("conversations", {})
                    logger.info("Loaded %d sessions from storage", len(self._sessions))
            else:
                self._sessions = {}
                logger.info("No existing session file, starting fresh")
        except json.JSONDecodeError as e:
            logger.error("Corrupt session file, starting fresh: %s", e)
            self._sessions = {}
        except Exception as e:
            logger.error("Failed to load sessions: %s", e)
            self._sessions = {}

    async def _save(self) -> None:
        """Save sessions to JSON file."""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            async with self._lock:
                with open(self._storage_path, "w", encoding="utf-8") as f:
                    json.dump({"conversations": self._sessions}, f, indent=2)
        except Exception as e:
            logger.error("Failed to save sessions: %s", e)

    async def get_session(self, key: ConversationKey) -> str | None:
        """Retrieve thread ID for conversation."""
        return self._sessions.get(self._key_to_string(key))

    async def set_session(self, key: ConversationKey, thread_id: str) -> None:
        """Store thread ID for conversation."""
        self._sessions[self._key_to_string(key)] = thread_id
        await self._save()

    async def delete_session(self, key: ConversationKey) -> None:
        """Remove session for conversation."""
        self._sessions.pop(self._key_to_string(key), None)
        await self._save()

    @staticmethod
    def _key_to_string(key: ConversationKey) -> str:
        """Convert ConversationKey to string key for storage."""
        return f"{key.chat_id}_{key.user_id}"


class SessionManager:
    """Manages conversation sessions with persistence."""

    def __init__(self, store: SessionStore) -> None:
        self.store = store

    async def get_session_id(self, key: ConversationKey) -> str | None:
        """Retrieve session ID or None."""
        return await self.store.get_session(key)

    async def set_session_id(self, key: ConversationKey, thread_id: str) -> None:
        """Store session ID."""
        await self.store.set_session(key, thread_id)

    async def clear_session(self, key: ConversationKey) -> None:
        """Remove session."""
        await self.store.delete_session(key)


class ProcessingLock:
    """Per-conversation lock to prevent concurrent requests."""

    def __init__(self) -> None:
        self._holders: set[ConversationKey] = set()
        self._lock = asyncio.Lock()

    async def acquire(self, key: ConversationKey) -> bool:
        """Try to acquire lock for conversation. Return False if already held."""
        async with self._lock:
            if key in self._holders:
                return False
            self._holders.add(key)
            return True

    async def release(self, key: ConversationKey) -> None:
        """Release lock for conversation."""
        async with self._lock:
            self._holders.discard(key)

    def __call__(self, key: ConversationKey) -> "ProcessingLock":
        """Allow using instance as async context manager."""
        return _ProcessingLockContext(self, key)


class _ProcessingLockContext:
    """Async context manager for ProcessingLock."""

    def __init__(self, lock_manager: ProcessingLock, key: ConversationKey) -> None:
        self._lock_manager = lock_manager
        self._key = key
        self._acquired = False

    async def __aenter__(self) -> bool:
        """Acquire the lock, raise if not available."""
        acquired = await self._lock_manager.acquire(self._key)
        if not acquired:
            raise RuntimeError("Could not acquire lock - conversation is busy")
        self._acquired = True
        return True

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Release the lock."""
        if self._acquired:
            await self._lock_manager.release(self._key)