"""
Cursor CLI - A wrapper for cursor-agent with formatted output support.
"""

from .runner import CursorCLIRunner, cursor_cli, create_chat
from .formatter import StreamJsonFormatter
from .session import (
    get_last_session_id,
    set_last_session_id,
    get_locked_session_id,
    get_locked_session_id_for_shell,
    set_session_lock,
    clear_session_lock,
    list_sessions,
    get_session,
    search_sessions,
    get_conversation_files,
    read_conversation,
    ConversationWriter,
)

__version__ = "0.1.11"
__all__ = [
    "CursorCLIRunner",
    "StreamJsonFormatter",
    "cursor_cli",
    "create_chat",
    "get_last_session_id",
    "set_last_session_id",
    "list_sessions",
    "get_session",
    "search_sessions",
    "get_conversation_files",
    "read_conversation",
]
