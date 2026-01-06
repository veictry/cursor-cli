# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.9] - 2026-01-06

### Added

- **`--file` option**: Read task from a file
  - Usage: `cursor-cli --file /path/to/task.txt`
  - Prompt sent to cursor-agent: `请尝试完成 {absolute_path} 中的任务`
  - File content is recorded as `initial_prompt` in database for easy searching
  - cursor-agent can read the file directly via the absolute path

## [0.1.8] - 2026-01-06

### Changed

- **`--danger` improvements**: Now adds Write permission for current working directory
  - Running `cursor-cli --danger` in different directories accumulates Write permissions
  - Permissions are deduplicated (won't add the same path twice)
  - Format: `Write(/absolute/path/to/directory/**/*)`
  - Base permissions (Shell, Read) are always added

## [0.1.7] - 2026-01-06

### Added

- **Session Management**: Automatic conversation logging with hybrid storage

  - SQLite database (`sessions.db`) for session index and shell session tracking
  - Markdown files for conversation content (human-readable, easy to search)
  - Directory structure: `.cursor-cli/{session_id}/{timestamp}.md`
  - Real-time writing: conversation files are created immediately and updated in real-time
  - `ConversationWriter` class for streaming conversation content to files

- **Shell Session Tracking**: Resume conversations without remembering session IDs

  - `--resume` without arguments resumes the last session from current shell
  - `--resume "prompt"` intelligently detects if argument is a prompt (contains spaces or is long)
  - Tracks shell PID to session ID mapping in SQLite

- **New Python API functions**:

  - `list_sessions()` - List all sessions (newest first)
  - `get_session()` - Get session info by ID
  - `search_sessions()` - Search sessions by initial prompt
  - `get_conversation_files()` - Get conversation files for a session
  - `read_conversation()` - Read a conversation file
  - `ConversationWriter` - Class for real-time conversation file writing

- **`output_to` parameter** in `cursor_cli()` function:

  - `output_to=True` - Auto-print to stdout (no manual iteration needed)
  - `output_to="/path/to/file"` - Write to file in real-time
  - `output_to=None` - Silent mode (run but don't output)

- **`save_session` parameter** in `cursor_cli()` function to control conversation saving

### Fixed

- Fixed `--install` failing with `FileNotFoundError` when cursor-agent is not installed
- Fixed assistant text duplication in formatter when cursor-agent sends accumulated content
- Fixed potential stderr deadlock by reading stderr in a separate thread

### Changed

- Conversation files are now written in real-time instead of after conversation ends
- Session tracking uses parent process ID (PPID) to identify shells

## [0.1.6] - 2024-12-09

### Changed

- Migrated project to GitHub: [https://github.com/veictry/cursor-cli](https://github.com/veictry/cursor-cli)
- Added project URLs (Homepage, Repository, Issues) to `pyproject.toml`
- Added author information to project metadata
- Updated README with GitHub badges and repository links
- Added Contributing section to README

## [0.1.5] - 2024-12-09

### Added

- `--install` flag for installing cursor-agent CLI and setting up PATH environment variable
  - Checks if cursor-agent is already installed before proceeding
  - Runs `curl https://cursor.com/install -fsS | bash` to install cursor-agent
  - Automatically adds `$HOME/.local/bin` to PATH in `.bashrc` and/or `.zshrc`
  - Detects current shell and provides appropriate source command

## [0.1.3] - 2024-12-09

### Added

- Subcommand passthrough: cursor-agent subcommands (`login`, `status`, `create-chat`, etc.) are passed directly without formatting

### Fixed

- Fixed syntax error in `formatter.py`

## [0.1.2] - 2024-12-09

### Added

- `create_chat()` function to create a new chat session and return chat_id
- `workspace` parameter in `cursor_cli()` - equivalent to `--workspace <path>` (default: current directory)
- `chat_id` parameter in `cursor_cli()` - equivalent to `--resume <chat_id>`

### Changed

- `cursor_cli()` now automatically creates a chat session if `chat_id` is not provided
- All subsequent commands use `--resume <chat_id>` for session continuity
- `json` parameter default changed from `False` to `True` in `cursor_cli()`

## [0.1.1] - 2024-12-09

### Added

- `--danger [path]` flag for setting up extended permissions in `.cursor/cli-config.json`
  - Default path: `~/.cursor` (user home directory)
  - Cross-platform support (Windows, macOS, Linux)
  - Automatically appends permissions without overwriting existing ones
- Default permissions include: `Shell(*)`, `Read(*)`, `Write(**/agents/**/*)`, `Write(**/.agents/**/*)`

### Changed

- Default mode is now streaming with formatted output (no need for `--stream` flag)
- Added `--text` flag for text output mode

## [0.1.0] - 2024-12-09

### Added

- Initial release
- `cursor-cli` command-line tool for running cursor-agent with formatted output
- Default streaming mode with real-time formatted output
- `--text` flag for text output mode
- `--no-color` flag to disable colored output
- `--no-format` flag to disable output formatting
- `cursor_cli()` Python function for programmatic usage
- `CursorCLIRunner` class for advanced usage
- `StreamJsonFormatter` for parsing and formatting cursor-agent stream-json output
- Color-coded output for different message types (system, user, thinking, assistant, tool_call, result)
- Cross-platform support (Windows, macOS, Linux)

### Features

- Real-time output streaming
- Formatted stream-JSON output with aggregated messages
- Support for multiple output formats (streaming, text, json)
- Extended permissions setup with `--danger` flag
