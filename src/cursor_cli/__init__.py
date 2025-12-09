"""
Cursor CLI - A wrapper for cursor-agent with formatted output support.
"""

from .runner import CursorCLIRunner, cursor_cli, create_chat
from .formatter import StreamJsonFormatter

__version__ = "0.1.6"
__all__ = ["CursorCLIRunner", "StreamJsonFormatter", "cursor_cli", "create_chat"]
