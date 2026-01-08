"""
Session management module for cursor-cli.

Uses SQLite for efficient indexing and shell session tracking.
Conversation content is stored in individual files for easy access and readability.

Storage structure:
    .cursor-cli/
    ├── sessions.db                    # SQLite for index and shell tracking
    └── {session_id}/                  # Session directory
        └── {YYYY_MM_DD_HH_mm_ss}.md   # Conversation files
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager


# Directory and database names
CURSOR_CLI_DIR = ".cursor-cli"
DATABASE_FILE = "sessions.db"


def get_cursor_cli_dir(workspace: Optional[str] = None) -> Path:
    """
    Get the .cursor-cli directory path.

    Args:
        workspace: Workspace directory (default: current directory)

    Returns:
        Path to .cursor-cli directory
    """
    if workspace is None:
        workspace = os.getcwd()
    return Path(workspace) / CURSOR_CLI_DIR


def get_database_path(workspace: Optional[str] = None) -> Path:
    """
    Get the path to the SQLite database.

    Args:
        workspace: Workspace directory

    Returns:
        Path to sessions.db
    """
    return get_cursor_cli_dir(workspace) / DATABASE_FILE


@contextmanager
def get_db_connection(workspace: Optional[str] = None):
    """
    Context manager for database connections.

    Ensures the database and tables exist before returning a connection.

    Args:
        workspace: Workspace directory

    Yields:
        sqlite3.Connection object
    """
    db_path = get_database_path(workspace)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row  # Enable column access by name

    try:
        _ensure_tables(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """
    Ensure all required tables exist in the database.

    Args:
        conn: Database connection
    """
    cursor = conn.cursor()

    # Sessions table - stores session metadata/index
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            initial_prompt TEXT,
            workspace TEXT,
            conversation_count INTEGER DEFAULT 0
        )
    """
    )

    # Shell sessions table - maps shell PID to last used session
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shell_sessions (
            shell_pid TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            locked_session_id TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """
    )

    # Add locked_session_id column if not exists (migration)
    try:
        cursor.execute(
            "ALTER TABLE shell_sessions ADD COLUMN locked_session_id TEXT"
        )
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Create index for common queries
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sessions_created
        ON sessions(created_at DESC)
    """
    )

    conn.commit()


# ============================================================================
# Session Directory Management
# ============================================================================


def ensure_session_dir(session_id: str, workspace: Optional[str] = None) -> Path:
    """
    Ensure the session directory exists.

    Args:
        session_id: The session ID
        workspace: Workspace directory

    Returns:
        Path to the session directory
    """
    cursor_cli_dir = get_cursor_cli_dir(workspace)
    session_dir = cursor_cli_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def get_conversation_file_path(
    session_id: str, workspace: Optional[str] = None
) -> Path:
    """
    Get the path for a new conversation file with timestamp.

    Args:
        session_id: The session ID
        workspace: Workspace directory

    Returns:
        Path to the conversation file
    """
    session_dir = ensure_session_dir(session_id, workspace)
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    return session_dir / f"{timestamp}.md"


# ============================================================================
# Session Index Management (SQLite)
# ============================================================================


def update_index(
    session_id: str,
    initial_prompt: str,
    workspace: Optional[str] = None,
) -> None:
    """
    Update the session index with a new session entry.

    Args:
        session_id: The session ID
        initial_prompt: The initial prompt for this session
        workspace: Workspace directory
    """
    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()

        # Convert workspace to string if it's a Path
        workspace_str = str(workspace) if workspace else os.getcwd()

        cursor.execute(
            """
            INSERT OR IGNORE INTO sessions (id, created_at, initial_prompt, workspace, conversation_count)
            VALUES (?, ?, ?, ?, 0)
            """,
            (session_id, timestamp, initial_prompt, workspace_str),
        )


def get_session(session_id: str, workspace: Optional[str] = None) -> Optional[dict]:
    """
    Get session information by ID.

    Args:
        session_id: The session ID
        workspace: Workspace directory

    Returns:
        Dict with session info, or None if not found
    """
    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def list_sessions(
    workspace: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[dict]:
    """
    List sessions ordered by creation time (newest first).

    Args:
        workspace: Workspace directory
        limit: Maximum number of sessions to return
        offset: Number of sessions to skip

    Returns:
        List of session dicts
    """
    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM sessions
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]


def search_sessions(
    query: str,
    workspace: Optional[str] = None,
    limit: int = 20,
) -> List[dict]:
    """
    Search sessions by initial prompt.

    Args:
        query: Search query string
        workspace: Workspace directory
        limit: Maximum results to return

    Returns:
        List of matching session dicts
    """
    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()
        search_pattern = f"%{query}%"

        cursor.execute(
            """
            SELECT * FROM sessions
            WHERE initial_prompt LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (search_pattern, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


# ============================================================================
# Conversation File Management
# ============================================================================


class ConversationWriter:
    """
    A writer for streaming conversation content to a file.

    Creates the file immediately and allows real-time appending of content.
    """

    def __init__(
        self,
        session_id: str,
        prompt: str,
        workspace: Optional[str] = None,
    ):
        """
        Create a new conversation file and write the header.

        Args:
            session_id: The session ID
            prompt: The user prompt
            workspace: Workspace directory
        """
        self.session_id = session_id
        self.workspace = workspace
        self.file_path = get_conversation_file_path(session_id, workspace)
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._closed = False

        # Create and open the file immediately
        self._file = open(self.file_path, "w", encoding="utf-8")

        # Write the header with prompt
        header = f"""# Conversation - {self.timestamp}

## Prompt

{prompt}

## Response

"""
        self._file.write(header)
        self._file.flush()

    def write(self, content: str) -> None:
        """
        Append content to the conversation file.

        Args:
            content: Content to append
        """
        if self._closed:
            return
        self._file.write(content)
        self._file.flush()

    def close(self) -> Path:
        """
        Close the file and update the conversation count.

        Returns:
            Path to the saved file
        """
        if self._closed:
            return self.file_path

        self._closed = True
        self._file.close()

        # Update conversation count in index
        with get_db_connection(self.workspace) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions
                SET conversation_count = conversation_count + 1
                WHERE id = ?
                """,
                (self.session_id,),
            )

        return self.file_path

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def save_conversation(
    session_id: str,
    prompt: str,
    output: str,
    workspace: Optional[str] = None,
) -> Path:
    """
    Save a conversation to a timestamped file (one-shot version).

    Args:
        session_id: The session ID
        prompt: The user prompt
        output: The conversation output
        workspace: Workspace directory

    Returns:
        Path to the saved file
    """
    with ConversationWriter(session_id, prompt, workspace) as writer:
        writer.write(output)
    return writer.file_path


def get_conversation_files(
    session_id: str, workspace: Optional[str] = None
) -> List[Path]:
    """
    Get all conversation files for a session.

    Args:
        session_id: The session ID
        workspace: Workspace directory

    Returns:
        List of conversation file paths (sorted by name, newest first)
    """
    session_dir = get_cursor_cli_dir(workspace) / session_id
    if not session_dir.exists():
        return []

    files = list(session_dir.glob("*.md"))
    return sorted(files, reverse=True)  # Newest first


def read_conversation(file_path: Path) -> Optional[str]:
    """
    Read a conversation file.

    Args:
        file_path: Path to the conversation file

    Returns:
        File content, or None if file doesn't exist
    """
    if not file_path.exists():
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================================
# Shell Session Tracking (SQLite)
# ============================================================================


def get_shell_pid() -> str:
    """
    Get the current shell's process ID.

    Returns:
        String representation of the parent process ID
    """
    return str(os.getppid())


def get_last_session_id(
    workspace: Optional[str] = None, shell_pid: Optional[str] = None
) -> Optional[str]:
    """
    Get the last session ID for a shell.

    Args:
        workspace: Workspace directory
        shell_pid: Shell process ID (default: current shell)

    Returns:
        The last session ID, or None if not found
    """
    if shell_pid is None:
        shell_pid = get_shell_pid()

    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id FROM shell_sessions WHERE shell_pid = ?",
            (shell_pid,),
        )
        row = cursor.fetchone()
        if row:
            return row["session_id"]
        return None


def get_locked_session_id_for_shell(
    workspace: Optional[str] = None, shell_pid: Optional[str] = None
) -> Optional[str]:
    """
    Get the locked session ID for a specific shell.

    Args:
        workspace: Workspace directory
        shell_pid: Shell process ID (default: current shell)

    Returns:
        The locked session ID, or None if not locked
    """
    if shell_pid is None:
        shell_pid = get_shell_pid()

    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT locked_session_id FROM shell_sessions WHERE shell_pid = ?",
            (shell_pid,),
        )
        row = cursor.fetchone()
        if row and row["locked_session_id"]:
            return row["locked_session_id"]
        return None


def set_last_session_id(session_id: str, workspace: Optional[str] = None) -> None:
    """
    Set the last session ID for the current shell.

    Args:
        session_id: The session ID to remember
        workspace: Workspace directory
    """
    shell_pid = get_shell_pid()
    timestamp = datetime.now().isoformat()

    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()
        # Preserve locked_session_id if exists
        cursor.execute(
            "SELECT locked_session_id FROM shell_sessions WHERE shell_pid = ?",
            (shell_pid,),
        )
        row = cursor.fetchone()
        locked_session_id = row["locked_session_id"] if row else None

        cursor.execute(
            """
            INSERT OR REPLACE INTO shell_sessions 
            (shell_pid, session_id, updated_at, locked_session_id)
            VALUES (?, ?, ?, ?)
            """,
            (shell_pid, session_id, timestamp, locked_session_id),
        )


def get_locked_session_id(workspace: Optional[str] = None) -> Optional[str]:
    """
    Get the locked session ID for the current shell.

    Args:
        workspace: Workspace directory

    Returns:
        The locked session ID, or None if not locked
    """
    shell_pid = get_shell_pid()

    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT locked_session_id FROM shell_sessions WHERE shell_pid = ?",
            (shell_pid,),
        )
        row = cursor.fetchone()
        if row and row["locked_session_id"]:
            return row["locked_session_id"]
        return None


def set_session_lock(
    session_id: str, workspace: Optional[str] = None
) -> None:
    """
    Lock the current shell to a specific session ID.

    Args:
        session_id: The session ID to lock to
        workspace: Workspace directory
    """
    shell_pid = get_shell_pid()
    timestamp = datetime.now().isoformat()

    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()
        # Check if row exists
        cursor.execute(
            "SELECT session_id FROM shell_sessions WHERE shell_pid = ?",
            (shell_pid,),
        )
        row = cursor.fetchone()

        if row:
            cursor.execute(
                """
                UPDATE shell_sessions 
                SET locked_session_id = ?, updated_at = ?
                WHERE shell_pid = ?
                """,
                (session_id, timestamp, shell_pid),
            )
        else:
            cursor.execute(
                """
                INSERT INTO shell_sessions 
                (shell_pid, session_id, updated_at, locked_session_id)
                VALUES (?, ?, ?, ?)
                """,
                (shell_pid, session_id, timestamp, session_id),
            )


def clear_session_lock(workspace: Optional[str] = None) -> Optional[str]:
    """
    Clear the session lock for the current shell.

    Args:
        workspace: Workspace directory

    Returns:
        The previously locked session ID, or None if wasn't locked
    """
    shell_pid = get_shell_pid()
    timestamp = datetime.now().isoformat()

    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT locked_session_id FROM shell_sessions WHERE shell_pid = ?",
            (shell_pid,),
        )
        row = cursor.fetchone()
        old_locked = row["locked_session_id"] if row else None

        if row:
            cursor.execute(
                """
                UPDATE shell_sessions 
                SET locked_session_id = NULL, updated_at = ?
                WHERE shell_pid = ?
                """,
                (timestamp, shell_pid),
            )

        return old_locked


def cleanup_stale_sessions(workspace: Optional[str] = None) -> int:
    """
    Clean up shell sessions for processes that no longer exist.

    This helps prevent the database from growing indefinitely.

    Args:
        workspace: Workspace directory

    Returns:
        Number of stale sessions removed
    """
    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()

        # Get all shell PIDs
        cursor.execute("SELECT shell_pid FROM shell_sessions")
        rows = cursor.fetchall()

        stale_pids = []
        for row in rows:
            shell_pid = row["shell_pid"]
            try:
                pid = int(shell_pid)
                os.kill(pid, 0)  # Signal 0 just checks if process exists
            except (ValueError, ProcessLookupError, PermissionError):
                stale_pids.append(shell_pid)

        if stale_pids:
            placeholders = ",".join("?" * len(stale_pids))
            cursor.execute(
                f"DELETE FROM shell_sessions WHERE shell_pid IN ({placeholders})",
                stale_pids,
            )

        return len(stale_pids)


# ============================================================================
# Utility Functions
# ============================================================================


def get_session_stats(workspace: Optional[str] = None) -> dict:
    """
    Get statistics about stored sessions.

    Args:
        workspace: Workspace directory

    Returns:
        Dict with statistics
    """
    with get_db_connection(workspace) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM sessions")
        session_count = cursor.fetchone()["count"]

        cursor.execute("SELECT SUM(conversation_count) as total FROM sessions")
        row = cursor.fetchone()
        conversation_count = row["total"] if row["total"] else 0

        cursor.execute("SELECT COUNT(*) as count FROM shell_sessions")
        shell_session_count = cursor.fetchone()["count"]

        return {
            "sessions": session_count,
            "conversations": conversation_count,
            "shell_sessions": shell_session_count,
        }
