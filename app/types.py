from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationKey:
    """Unique identifier for a conversation."""
    chat_id: int
    user_id: int


@dataclass
class AssistantReply:
    """Response from assistant backend."""
    text: str
    session_id: str | None