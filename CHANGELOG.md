# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
