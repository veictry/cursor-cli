# Cursor CLI

[![PyPI version](https://badge.fury.io/py/cursor-cli.svg)](https://badge.fury.io/py/cursor-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A Python wrapper for `cursor-agent` with enhanced output formatting support.

**GitHub**: [https://github.com/veictry/cursor-cli](https://github.com/veictry/cursor-cli)

## Installation

### From PyPI

```bash
pip install cursor-cli
```

### From source

```bash
cd cursor_cli
pip install -e .
```

### Or run directly as a module

```bash
python -m cursor_cli [args...]
```

## Features

- **Real-time Output Streaming**: Outputs cursor-agent results in real-time as they arrive (default mode)
- **Formatted Stream-JSON Output**: The output is parsed and formatted for better readability
- **Color-coded Output**: Different message types (system, user, thinking, assistant, tool_call) are displayed in different colors
- **Aggregated Output**: Messages of the same type are aggregated together instead of being displayed on separate lines
- **Session Management**: Automatic conversation logging with SQLite index and Markdown files
- **Shell Session Tracking**: `--resume` without args resumes last session; `--session` locks to a chat_id
- **File-based Tasks**: `--file` option to read task from a file
- **Extended Permissions Setup**: `--danger` flag for setting up cursor-agent permissions
- **One-click Installation**: `--install` flag for installing cursor-agent CLI and setting up PATH

## Usage

### Quick Start (推荐)

```bash
# 默认流式输出模式
cursor-cli "Analyze this project"

# 等效于:
cursor-cli --output-format stream-json --stream-partial-output -p "Analyze this project"
```

### Text Mode

```bash
# 使用 --text 切换到文本输出模式
cursor-cli --text "Analyze this project"

# 等效于:
cursor-cli --output-format text -p "Analyze this project"
```

### Install cursor-agent

Install cursor-agent CLI and setup PATH environment variable:

```bash
cursor-cli --install
```

This will:

1. Check if cursor-agent is already installed
2. If not installed, run `curl https://cursor.com/install -fsS | bash`
3. Add `$HOME/.local/bin` to PATH in `.bashrc` and/or `.zshrc`

### Session Management

```bash
# 锁定当前 shell 到一个 chat_id（自动创建或使用上一个）
cursor-cli --session

# 锁定到新的 session
cursor-cli --session new

# 锁定到指定的 chat_id
cursor-cli --session abc123

# 再次运行解锁
cursor-cli --session

# 查看当前 shell 的最后一个 chat_id
cursor-cli --last-chat-id

# 继续上一次对话（无需记住 session ID）
cursor-cli --resume "Continue from where we left off"
```

Session 数据存储在 `.cursor-cli/` 目录下：

- `sessions.db` - SQLite 数据库，存储 session 索引和 shell session 追踪
- `{session_id}/` - 每个 session 的对话记录目录
- `{session_id}/{timestamp}.md` - Markdown 格式的对话记录

### File-based Tasks

```bash
# 从文件读取任务
cursor-cli --file /path/to/task.txt
# 等效于: cursor-cli "请尝试完成 /path/to/task.txt 中的任务"
```

### Danger Mode (Extended Permissions)

Setup extended permissions for cursor-agent in `.cursor/cli-config.json`:

```bash
# 在用户 home 目录下创建 ~/.cursor/cli-config.json
cursor-cli --danger

# 在指定目录下创建 .cursor/cli-config.json
cursor-cli --danger /path/to/project
```

在不同目录运行 `--danger` 会累加 Write 权限：

```json
{
  "permissions": {
    "allow": [
      "Shell(*)",
      "Read(*)",
      "Write(**/agents/**/*)",
      "Write(**/.agents/**/*)",
      "Write(/path/to/project1/**/*)",
      "Write(/path/to/project2/**/*)"
    ],
    "deny": []
  }
}
```

### Runner-specific Options

```bash
# 默认流式模式（推荐）
cursor-cli "Your prompt here"

# 文本输出模式
cursor-cli --text "Your prompt here"

# 禁用颜色
cursor-cli --no-color "Your prompt"

# 禁用格式化输出（原始 JSON）
cursor-cli --no-format "Your prompt"

# Show runner help
cursor-cli --runner-help
```

### Programmatic Usage

```python
from cursor_cli import cursor_cli, create_chat

# Simple function call (returns JSON by default)
result = cursor_cli("Hello, what can you do?")
print(result)

# Text output
result = cursor_cli("Hello", json=False)
print(result)

# Streaming output with auto-print
cursor_cli("Explain Python", stream=True, output_to=True)

# Write output to file in real-time
cursor_cli("Analyze this", stream=True, output_to="/path/to/output.txt")

# With specific workspace
result = cursor_cli("Analyze this", workspace="/path/to/project")

# Create and reuse chat session
chat_id = create_chat()
result1 = cursor_cli("First question", chat_id=chat_id)
result2 = cursor_cli("Follow up question", chat_id=chat_id)

# Session management
from cursor_cli import (
    list_sessions, get_session, search_sessions,
    get_conversation_files, read_conversation
)

# List recent sessions
sessions = list_sessions(limit=10)
for s in sessions:
    print(f"{s['id']}: {s['initial_prompt'][:50]}...")

# Search sessions by prompt
results = search_sessions("analyze project")

# Get conversation files for a session
files = get_conversation_files("session-id-here")
for f in files:
    content = read_conversation(f)
    print(content)

# Using the runner class
from cursor_cli import CursorCLIRunner
runner = CursorCLIRunner(use_colors=True)
exit_code = runner.run(["-p", "your prompt", "--output-format", "stream-json", "--stream-partial-output"])
```

### Using the Formatter Directly

```python
from cursor_cli import StreamJsonFormatter
import sys

# Create formatter
formatter = StreamJsonFormatter(output=sys.stdout, use_colors=True)

# Process JSON lines
formatter.process_line('{"type":"system","subtype":"init","model":"Composer 1"}')
formatter.process_line('{"type":"user","message":{"role":"user","content":[{"type":"text","text":"Hello"}]}}')

# Finalize when done
formatter.finalize()
```

## Output Format

When formatting is enabled, the output is displayed as:

```
[SYSTEM:init] Model: Composer 1 | CWD: /path/to/dir | Permission: default | Session: abc12345...

[USER] your prompt text here

[THINKING] (thinking content if any)

[ASSISTANT] Response from the assistant...

[TOOL_CALL:started] 🔧 Tool #1: $ command to execute

[TOOL_CALL:completed]    ✓ Success

[TOOL_CALL:started] 📝 Tool #2: Creating analysis.txt

[TOOL_CALL:completed]    ✓ Created 15 lines (1234 bytes)

[RESULT] 🎯 Completed in 2.5s | 📊 Stats: 2 tools, 350 chars generated
```

### Color Scheme

- **SYSTEM**: Cyan
- **USER**: Green
- **THINKING**: Dim gray
- **ASSISTANT**: Yellow
- **TOOL_CALL**: Magenta
- **RESULT**: Bold Green

## CLI Options

| Option                  | Description                                             |
| ----------------------- | ------------------------------------------------------- |
| `"prompt"`              | Default streaming mode with formatted output            |
| `--text "prompt"`       | Text output mode                                        |
| `--resume [session_id]` | Resume a session (no ID = last session from this shell) |
| `--session [chat_id]`   | Lock shell to chat_id (`new` = create new session)      |
| `--last-chat-id`        | Show the last chat_id for this shell                    |
| `--file <path>`         | Read task from file                                     |
| `--install`             | Install cursor-agent CLI and setup PATH                 |
| `--danger [path]`       | Setup extended permissions (default: ~/.cursor)         |
| `--no-color`            | Disable colored output                                  |
| `--no-format`           | Disable output formatting (raw JSON)                    |
| `--runner-help`         | Show help message                                       |

## API Reference

### `cursor_cli()` Function

```python
cursor_cli(
    prompt: str,
    model: str = "composer-1",
    stream: bool = False,
    json: bool = True,
    workspace: str = None,
    chat_id: str = None,
    output_to: Union[bool, str, None] = None,
    save_session: bool = True,
    **extra_args
) -> Union[str, dict, Iterator[str]]
```

| 参数           | 类型                | 默认值         | 说明                                     |
| -------------- | ------------------- | -------------- | ---------------------------------------- |
| `prompt`       | str                 | 必填           | 发送给 cursor-agent 的提示               |
| `model`        | str                 | `"composer-1"` | 使用的模型                               |
| `stream`       | bool                | `False`        | 是否使用流式输出                         |
| `json`         | bool                | `True`         | 是否返回 JSON 格式                       |
| `workspace`    | str \| None         | 当前目录       | 工作区目录，等效于 `--workspace`         |
| `chat_id`      | str \| None         | 自动创建       | Chat 会话 ID，等效于 `--resume`          |
| `output_to`    | bool \| str \| None | `None`         | `True`=打印到 stdout, `str`=写入文件路径 |
| `save_session` | bool                | `True`         | 是否保存对话到 session 文件              |
| `**extra_args` | -                   | -              | 额外的命令行参数                         |

**返回值:**

- `stream=False, json=False`: 返回 `str` 文本输出
- `stream=False, json=True`: 返回 `dict` 解析后的 JSON
- `stream=True`: 返回 `Iterator[str]` 生成器，逐行输出 JSON

**Note:** 如果不传入 `chat_id`，会自动创建一个新的 chat session。

### `create_chat()` Function

```python
create_chat(workspace: str = None) -> str
```

创建新的 chat session 并返回 chat_id。

| 参数        | 类型        | 默认值   | 说明       |
| ----------- | ----------- | -------- | ---------- |
| `workspace` | str \| None | 当前目录 | 工作区目录 |

**返回值:** `str` - 新创建的 chat_id

## Message Types

The formatter handles the following message types from cursor-agent's stream-json output:

| Type        | Description                                              |
| ----------- | -------------------------------------------------------- |
| `system`    | System initialization and configuration                  |
| `user`      | User input/prompt                                        |
| `thinking`  | AI thinking process (streaming deltas)                   |
| `assistant` | AI response                                              |
| `tool_call` | Tool invocations (shell commands, file operations, etc.) |
| `result`    | Task completion with duration and statistics             |

### Supported Tool Types

| Tool             | Icon | Description             |
| ---------------- | ---- | ----------------------- |
| `shellToolCall`  | 🔧   | Shell command execution |
| `writeToolCall`  | 📝   | File creation           |
| `readToolCall`   | 📖   | File reading            |
| `editToolCall`   | ✏️   | File editing            |
| `listToolCall`   | 📂   | Directory listing       |
| `searchToolCall` | 🔍   | Code search             |

## Development

### Release to PyPI

```bash
# Install build dependencies
pip install build twine

# Release to PyPI (will prompt for token)
python scripts/release.py

# Release to TestPyPI first
python scripts/release.py --test
```

## Requirements

- Python >= 3.8
- `cursor-agent` must be installed and available in PATH

## Contributing

Contributions are welcome! Please feel free to submit a [Pull Request](https://github.com/veictry/cursor-cli/pulls).

If you find a bug or have a feature request, please open an [Issue](https://github.com/veictry/cursor-cli/issues).

## License

MIT License - see the [LICENSE](https://github.com/veictry/cursor-cli/blob/main/LICENSE) file for details.
