"""
Conversation Memory Store

Provides persistent and session-based memory for multi-turn conversations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)


@dataclass
class ConversationSession:
    """A conversation session with memory."""

    session_id: str
    user_email: str
    created_at: datetime = field(default_factory=datetime.now)
    turns: list[ConversationTurn] = field(default_factory=list)
    context: dict = field(default_factory=dict)  # Persistent context
    pending_confirmation: dict | None = None  # For human-in-the-loop

    def add_turn(
        self,
        role: str,
        content: str,
        tool_calls: list | None = None,
        tool_results: list | None = None,
    ):
        """Add a turn to the conversation."""
        self.turns.append(
            ConversationTurn(
                role=role,
                content=content,
                tool_calls=tool_calls or [],
                tool_results=tool_results or [],
            )
        )

    def get_recent_turns(self, n: int = 10) -> list[ConversationTurn]:
        """Get the n most recent turns."""
        return self.turns[-n:] if len(self.turns) > n else self.turns

    def get_messages_for_llm(self, max_turns: int = 10) -> list[dict]:
        """Convert recent turns to LLM message format."""
        messages = []
        for turn in self.get_recent_turns(max_turns):
            messages.append({"role": turn.role, "content": turn.content})
        return messages

    def set_pending_confirmation(self, action: str, params: dict, message: str):
        """Set a pending confirmation for human-in-the-loop."""
        self.pending_confirmation = {
            "action": action,
            "params": params,
            "message": message,
            "created_at": datetime.now().isoformat(),
        }

    def clear_pending_confirmation(self):
        """Clear the pending confirmation."""
        self.pending_confirmation = None

    def has_pending_confirmation(self) -> bool:
        """Check if there's a pending confirmation."""
        return self.pending_confirmation is not None

    def update_context(self, key: str, value: Any):
        """Update session context."""
        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a value from session context."""
        return self.context.get(key, default)


class MemoryStore:
    """
    In-memory store for conversation sessions.

    In production, this would be backed by Redis or a database.
    """

    def __init__(self):
        self._sessions: dict[str, ConversationSession] = {}

    def get_or_create_session(
        self, session_id: str, user_email: str
    ) -> ConversationSession:
        """Get an existing session or create a new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationSession(
                session_id=session_id,
                user_email=user_email,
            )
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> ConversationSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self, user_email: str | None = None) -> list[ConversationSession]:
        """List all sessions, optionally filtered by user."""
        sessions = list(self._sessions.values())
        if user_email:
            sessions = [s for s in sessions if s.user_email == user_email]
        return sessions


# ========== SINGLETON INSTANCE ==========
_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Get the singleton memory store instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
