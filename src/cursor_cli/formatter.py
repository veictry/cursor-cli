"""
Formatter for cursor-agent stream-json output.

Handles the parsing and formatting of JSON stream output from cursor-agent,
aggregating outputs from the same module type for better readability.
"""

import json
import sys
from dataclasses import dataclass, field
from typing import Optional, TextIO
from enum import Enum


class OutputType(Enum):
    SYSTEM = "system"
    USER = "user"
    THINKING = "thinking"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    RESULT = "result"
    UNKNOWN = "unknown"


# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


# Color mapping for different output types
TYPE_COLORS = {
    OutputType.SYSTEM: Colors.BRIGHT_CYAN,
    OutputType.USER: Colors.BRIGHT_GREEN,
    OutputType.THINKING: Colors.DIM + Colors.BRIGHT_BLACK,
    OutputType.ASSISTANT: Colors.BRIGHT_YELLOW,
    OutputType.TOOL_CALL: Colors.BRIGHT_MAGENTA,
    OutputType.RESULT: Colors.BRIGHT_GREEN + Colors.BOLD,
    OutputType.UNKNOWN: Colors.WHITE,
}


@dataclass
class StreamState:
    """Tracks the current state of output stream for aggregation."""

    current_type: Optional[OutputType] = None
    current_subtype: Optional[str] = None
    current_call_id: Optional[str] = None
    needs_newline: bool = False
    thinking_buffer: str = ""
    assistant_buffer: str = ""
    tool_call_buffers: dict = field(default_factory=dict)
    # Statistics tracking
    tool_count: int = 0
    chars_generated: int = 0


class StreamJsonFormatter:
    """
    Formats cursor-agent stream-json output for better readability.

    Aggregates outputs from the same module type together, appending to previous
    output instead of creating new lines for each JSON message.
    """

    def __init__(self, output: TextIO = None, use_colors: bool = True):
        """
        Initialize the formatter.

        Args:
            output: Output stream (defaults to sys.stdout)
            use_colors: Whether to use ANSI colors in output
        """
        self.output = output or sys.stdout
        self.use_colors = use_colors and self._supports_color()
        self.state = StreamState()

    def _supports_color(self) -> bool:
        """Check if the output stream supports colors."""
        if hasattr(self.output, "isatty"):
            return self.output.isatty()
        return False

    def _colorize(self, text: str, output_type: OutputType) -> str:
        """Apply color to text based on output type."""
        if not self.use_colors:
            return text
        color = TYPE_COLORS.get(output_type, Colors.WHITE)
        return f"{color}{text}{Colors.RESET}"

    def _format_header(self, output_type: OutputType, subtype: str = None) -> str:
        """Format the header for a new output section."""
        type_name = output_type.value.upper()
        if subtype:
            header = f"[{type_name}:{subtype}]"
        else:
            header = f"[{type_name}]"

        if self.use_colors:
            color = TYPE_COLORS.get(output_type, Colors.WHITE)
            return f"{Colors.BOLD}{color}{header}{Colors.RESET} "
        return header + " "

    def _write(self, text: str, end: str = ""):
        """Write text to output stream."""
        self.output.write(text + end)
        self.output.flush()

    def _end_current_section(self):
        """End the current output section with a newline if needed."""
        if self.state.needs_newline:
            self._write("\n")
            self.state.needs_newline = False

    def _start_new_section(
        self, output_type: OutputType, subtype: str = None, call_id: str = None
    ):
        """Start a new output section."""
        self._end_current_section()
        self._write("\n")
        self._write(self._format_header(output_type, subtype))
        self.state.current_type = output_type
        self.state.current_subtype = subtype
        self.state.current_call_id = call_id
        self.state.needs_newline = True

    def _is_same_section(
        self, output_type: OutputType, subtype: str = None, call_id: str = None
    ) -> bool:
        """Check if the new output belongs to the current section."""
        if self.state.current_type != output_type:
            return False
        if output_type == OutputType.TOOL_CALL:
            return self.state.current_call_id == call_id
        return True

    def process_line(self, line: str):
        """
        Process a single JSON line from cursor-agent output.

        Args:
            line: A single line of JSON output
        """
        line = line.strip()
        if not line:
            return

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            # Not JSON, output as-is
            self._end_current_section()
            self._write(line + "\n")
            return

        type_str = data.get("type", "unknown")
        subtype = data.get("subtype")

        # Handle known types
        try:
            output_type = OutputType(type_str)
        except ValueError:
            output_type = OutputType.UNKNOWN

        if output_type == OutputType.SYSTEM:
            self._handle_system(data)
        elif output_type == OutputType.USER:
            self._handle_user(data)
        elif output_type == OutputType.THINKING:
            self._handle_thinking(data, subtype)
        elif output_type == OutputType.ASSISTANT:
            self._handle_assistant(data)
        elif output_type == OutputType.TOOL_CALL:
            self._handle_tool_call(data, subtype)
        elif output_type == OutputType.RESULT:
            self._handle_result(data)
        else:
            self._handle_unknown(data)

    def _handle_system(self, data: dict):
        """Handle system type messages."""
        subtype = data.get("subtype", "")
        self._start_new_section(OutputType.SYSTEM, subtype)

        # Format system info nicely
        info_parts = []
        if data.get("session_id"):
            info_parts.append(f"Session: {data['session_id']}")
        if data.get("model"):
            info_parts.append(f"Model: {data['model']}")
        if data.get("cwd"):
            info_parts.append(f"CWD: {data['cwd']}")
        if data.get("permissionMode"):
            info_parts.append(f"Permission: {data['permissionMode']}")

        if info_parts:
            text = "\n".join(info_parts)
            self._write(self._colorize(text, OutputType.SYSTEM))

    def _handle_user(self, data: dict):
        """Handle user type messages."""
        self._start_new_section(OutputType.USER)

        message = data.get("message", {})
        content = message.get("content", [])

        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)

        text = "".join(text_parts)
        self._write(self._colorize(text, OutputType.USER))

    def _handle_thinking(self, data: dict, subtype: str):
        """Handle thinking type messages (streaming deltas)."""
        if subtype == "delta":
            text = data.get("text", "")
            if text:
                if not self._is_same_section(OutputType.THINKING):
                    self._start_new_section(OutputType.THINKING)
                    self.state.thinking_buffer = ""

                self.state.thinking_buffer += text
                self._write(self._colorize(text, OutputType.THINKING))

        elif subtype == "completed":
            # Thinking completed, just end the section
            if self.state.current_type == OutputType.THINKING:
                self.state.needs_newline = True

    def _handle_assistant(self, data: dict):
        """Handle assistant type messages."""
        message = data.get("message", {})
        content = message.get("content", [])

        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)

        text = "".join(text_parts)

        # Check if this is new content or continuation
        if not self._is_same_section(OutputType.ASSISTANT):
            self._start_new_section(OutputType.ASSISTANT)
            self.state.assistant_buffer = ""

        # Only output new content (cursor-agent may send accumulated content)
        if text.startswith(self.state.assistant_buffer):
            new_text = text[len(self.state.assistant_buffer) :]
            if new_text:
                self._write(self._colorize(new_text, OutputType.ASSISTANT))
                self.state.chars_generated += len(new_text)
            self.state.assistant_buffer = text
        else:
            # Different content, output all
            self._write(self._colorize(text, OutputType.ASSISTANT))
            self.state.chars_generated += len(text)
            self.state.assistant_buffer = text

    def _handle_tool_call(self, data: dict, subtype: str):
        """Handle tool_call type messages."""
        call_id = data.get("call_id", "")
        tool_call = data.get("tool_call", {})

        if subtype == "started":
            self.state.tool_count += 1
            self._start_new_section(OutputType.TOOL_CALL, "started", call_id)

            tool_num = self.state.tool_count

            # Extract tool call information based on type
            if "shellToolCall" in tool_call:
                shell_call = tool_call["shellToolCall"]
                args = shell_call.get("args", {})
                command = args.get("command", "")
                self._write(
                    self._colorize(
                        f"🔧 Tool #{tool_num}: $ {command}", OutputType.TOOL_CALL
                    )
                )
            elif "writeToolCall" in tool_call:
                write_call = tool_call["writeToolCall"]
                args = write_call.get("args", {})
                path = args.get("path", "unknown")
                self._write(
                    self._colorize(
                        f"📝 Tool #{tool_num}: Creating {path}", OutputType.TOOL_CALL
                    )
                )
            elif "readToolCall" in tool_call:
                read_call = tool_call["readToolCall"]
                args = read_call.get("args", {})
                path = args.get("path", "unknown")
                self._write(
                    self._colorize(
                        f"📖 Tool #{tool_num}: Reading {path}", OutputType.TOOL_CALL
                    )
                )
            elif "editToolCall" in tool_call:
                edit_call = tool_call["editToolCall"]
                args = edit_call.get("args", {})
                path = args.get("path", "unknown")
                self._write(
                    self._colorize(
                        f"✏️  Tool #{tool_num}: Editing {path}", OutputType.TOOL_CALL
                    )
                )
            elif "listToolCall" in tool_call:
                list_call = tool_call["listToolCall"]
                args = list_call.get("args", {})
                path = args.get("path", ".")
                self._write(
                    self._colorize(
                        f"📂 Tool #{tool_num}: Listing {path}", OutputType.TOOL_CALL
                    )
                )
            elif "searchToolCall" in tool_call:
                search_call = tool_call["searchToolCall"]
                args = search_call.get("args", {})
                query = args.get("query", "")
                self._write(
                    self._colorize(
                        f"🔍 Tool #{tool_num}: Searching '{query}'",
                        OutputType.TOOL_CALL,
                    )
                )
            else:
                # Other tool types
                tool_type = list(tool_call.keys())[0] if tool_call else "unknown"
                self._write(
                    self._colorize(
                        f"🔧 Tool #{tool_num}: [{tool_type}]", OutputType.TOOL_CALL
                    )
                )

        elif subtype == "completed":
            # Update section to show completion status
            self._start_new_section(OutputType.TOOL_CALL, "completed", call_id)

            # Handle different tool types
            result_info = self._extract_tool_result(tool_call)
            self._write(self._colorize(result_info, OutputType.TOOL_CALL))

    def _extract_tool_result(self, tool_call: dict) -> str:
        """Extract result information from a tool call."""
        if "shellToolCall" in tool_call:
            shell_call = tool_call["shellToolCall"]
            result = shell_call.get("result", {})

            if "rejected" in result:
                rejected = result["rejected"]
                reason = rejected.get("reason", "No reason provided")
                return f"   ✗ REJECTED: {reason}"
            elif "success" in result:
                success = result["success"]
                output = success.get("output", "")
                exit_code = success.get("exitCode", 0)
                if exit_code == 0:
                    msg = "   ✓ Success"
                    if output:
                        msg += f"\n{output}"
                    return msg
                else:
                    msg = f"   ✗ Exit code: {exit_code}"
                    if output:
                        msg += f"\n{output}"
                    return msg

        elif "writeToolCall" in tool_call:
            write_call = tool_call["writeToolCall"]
            result = write_call.get("result", {})
            if "success" in result:
                success = result["success"]
                lines = success.get("linesCreated", 0)
                size = success.get("fileSize", 0)
                return f"   ✓ Created {lines} lines ({size} bytes)"
            elif "rejected" in result:
                return f"   ✗ REJECTED"

        elif "readToolCall" in tool_call:
            read_call = tool_call["readToolCall"]
            result = read_call.get("result", {})
            if "success" in result:
                success = result["success"]
                lines = success.get("totalLines", 0)
                return f"   ✓ Read {lines} lines"

        elif "editToolCall" in tool_call:
            edit_call = tool_call["editToolCall"]
            result = edit_call.get("result", {})
            if "success" in result:
                return "   ✓ Edit applied"
            elif "rejected" in result:
                return "   ✗ REJECTED"

        # Default
        return "   Completed"

    def _handle_result(self, data: dict):
        """Handle result type messages - indicates task completion."""
        self._start_new_section(OutputType.RESULT)

        duration_ms = data.get("duration_ms", 0)

        # Format duration nicely
        if duration_ms >= 1000:
            duration_str = f"{duration_ms / 1000:.1f}s"
        else:
            duration_str = f"{duration_ms}ms"

        # Build result summary
        parts = [f"🎯 Completed in {duration_str}"]

        # Add statistics
        stats = []
        if self.state.tool_count > 0:
            stats.append(f"{self.state.tool_count} tools")
        if self.state.chars_generated > 0:
            stats.append(f"{self.state.chars_generated} chars generated")

        if stats:
            parts.append(f"📊 Stats: {', '.join(stats)}")

        self._write(self._colorize(" | ".join(parts), OutputType.RESULT))

    def _handle_unknown(self, data: dict):
        """Handle unknown type messages."""
        self._start_new_section(OutputType.UNKNOWN)
        self._write(json.dumps(data, indent=2))

    def finalize(self):
        """Finalize the output, ensuring proper line endings."""
        self._end_current_section()
        self._write("\n")
