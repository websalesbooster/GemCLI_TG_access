"""Backend implementations for the Telegram-Codex Gateway."""

from typing import Protocol

from app.types import AssistantReply


class AssistantBackend(Protocol):
    """Protocol for assistant backend implementations."""

    async def ask(
        self, prompt: str, session_id: str | None = None
    ) -> AssistantReply:
        """Send prompt to backend, return reply with session ID for continuation."""
        ...

    async def health_check(self) -> bool:
        """Verify backend is available."""
        ...


from app.backends.codex import CodexCLIBackend

__all__ = ["AssistantBackend", "CodexCLIBackend"]