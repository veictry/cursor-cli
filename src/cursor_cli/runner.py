"""
Main runner module for cursor-agent wrapper.

Provides functionality to run cursor-agent with real-time output streaming
and optional formatted output for stream-json mode.
"""

import os
import subprocess
import sys
import shlex
import json as json_module
import threading
from io import StringIO
from typing import List, Optional, TextIO, Union, Iterator, Any
from .formatter import StreamJsonFormatter
from . import session as session_mgr


# Sentinel value to distinguish "not set" from "explicitly set to None"
class _Unset:
    """Sentinel class for unset parameter values."""

    pass


_OUTPUT_UNSET = _Unset()


class CursorCLIRunner:
    """
    A wrapper for running cursor-agent with real-time output streaming.

    Supports both raw output mode and formatted stream-json mode.
    """

    def __init__(
        self,
        output: Optional[TextIO] = None,
        error: Optional[TextIO] = None,
        use_colors: bool = True,
    ):
        """
        Initialize the runner.

        Args:
            output: Output stream for stdout (defaults to sys.stdout)
            error: Output stream for stderr (defaults to sys.stderr)
            use_colors: Whether to use ANSI colors in formatted output
        """
        self.output = output or sys.stdout
        self.error = error or sys.stderr
        self.use_colors = use_colors

    def _is_stream_json_mode(self, args: List[str]) -> bool:
        """
        Check if the arguments specify stream-json output format.

        Args:
            args: List of command-line arguments

        Returns:
            True if --output-format stream-json is specified
        """
        for i, arg in enumerate(args):
            if arg == "--output-format" and i + 1 < len(args):
                if args[i + 1] == "stream-json":
                    return True
            elif arg.startswith("--output-format="):
                if "stream-json" in arg:
                    return True
        return False

    def _has_stream_partial_output(self, args: List[str]) -> bool:
        """
        Check if --stream-partial-output is specified.

        Args:
            args: List of command-line arguments

        Returns:
            True if --stream-partial-output is specified
        """
        return "--stream-partial-output" in args

    def run(self, args: List[str], format_output: bool = True) -> int:
        """
        Run cursor-agent with the given arguments.

        Args:
            args: List of arguments to pass to cursor-agent
            format_output: Whether to format stream-json output (if applicable)

        Returns:
            Exit code from cursor-agent
        """
        cmd = ["cursor-agent"] + args

        # Determine if we should use formatted output
        use_formatter = (
            format_output
            and self._is_stream_json_mode(args)
            and self._has_stream_partial_output(args)
        )

        if use_formatter:
            return self._run_formatted(cmd)
        else:
            return self._run_raw(cmd)

    def _run_raw(self, cmd: List[str]) -> int:
        """
        Run cursor-agent with raw output streaming.

        Args:
            cmd: Full command to run

        Returns:
            Exit code from cursor-agent
        """
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line-buffered
            )

            assert process.stdout is not None
            assert process.stderr is not None

            # Stream stdout in real-time
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    self.output.write(line)
                    self.output.flush()

            # Get any remaining stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                self.error.write(stderr_output)
                self.error.flush()

            return process.returncode or 0

        except FileNotFoundError:
            self.error.write(
                "Error: cursor-agent not found. Please ensure it's installed and in PATH.\n"
            )
            return 1
        except Exception as e:
            self.error.write(f"Error running cursor-agent: {e}\n")
            return 1

    def _run_formatted(self, cmd: List[str]) -> int:
        """
        Run cursor-agent with formatted stream-json output.

        Args:
            cmd: Full command to run

        Returns:
            Exit code from cursor-agent
        """
        formatter = StreamJsonFormatter(output=self.output, use_colors=self.use_colors)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line-buffered
            )

            assert process.stdout is not None
            assert process.stderr is not None

            # Stream and format stdout in real-time
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    formatter.process_line(line)

            # Finalize the formatter
            formatter.finalize()

            # Get any remaining stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                self.error.write(stderr_output)
                self.error.flush()

            return process.returncode or 0

        except FileNotFoundError:
            self.error.write(
                "Error: cursor-agent not found. Please ensure it's installed and in PATH.\n"
            )
            return 1
        except Exception as e:
            self.error.write(f"Error running cursor-agent: {e}\n")
            return 1

    def run_from_string(self, args_string: str, format_output: bool = True) -> int:
        """
        Run cursor-agent with arguments specified as a string.

        Args:
            args_string: Arguments as a single string (will be parsed with shlex)
            format_output: Whether to format stream-json output (if applicable)

        Returns:
            Exit code from cursor-agent
        """
        args = shlex.split(args_string)
        return self.run(args, format_output)


def create_chat(workspace: Optional[str] = None) -> str:
    """
    Create a new chat session and return the chat_id.

    Args:
        workspace: Workspace directory (default: current directory)

    Returns:
        str: The chat_id of the newly created chat session

    Raises:
        FileNotFoundError: If cursor-agent is not found
        RuntimeError: If chat creation fails
    """
    if workspace is None:
        workspace = os.getcwd()

    cmd = ["cursor-agent", "create-chat", f"--workspace={workspace}"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        chat_id = result.stdout.strip()
        if not chat_id:
            raise RuntimeError("cursor-agent create-chat returned empty chat_id")
        return chat_id
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        raise RuntimeError(f"Failed to create chat: {error_msg}") from e
    except FileNotFoundError:
        raise FileNotFoundError(
            "cursor-agent not found. Please ensure it's installed and in PATH."
        )


def cursor_cli(
    prompt: str,
    model: str = "composer-1",
    stream: bool = False,
    json: bool = True,
    workspace: Optional[str] = None,
    chat_id: Optional[str] = None,
    output_to: Union[None, bool, str, TextIO, _Unset] = _OUTPUT_UNSET,
    save_session: bool = True,
    **extra_args,
) -> Union[str, dict, Iterator[str], None]:
    """
    Run cursor-agent with the given prompt and return the output.

    Args:
        prompt: The prompt to send to cursor-agent
        model: Model to use (default: "composer-1")
        stream: If True, use streaming output and return a generator
        json: If True, return output as parsed JSON dict (default: True)
        workspace: Workspace directory (default: current directory)
        chat_id: Chat session ID to resume (default: creates new chat)
        output_to: Output destination for streaming (automatically enables stream=True):
            - Not set (default): Normal behavior based on stream/json parameters
            - None: Silent mode, runs streaming but doesn't output anywhere
            - True or sys.stdout: Print to stdout in real-time
            - TextIO object: Write to the specified stream in real-time
            - str (file path): Write to the specified file in real-time
        save_session: If True (default), save conversation to .cursor-cli directory
        **extra_args: Additional arguments to pass to cursor-agent

    Returns:
        - If output_to is set: None (output is already written to the destination)
        - If stream=True: Iterator[str] yielding JSON lines
        - If json=True: dict with parsed JSON response
        - Otherwise: str with text output

    Raises:
        FileNotFoundError: If cursor-agent is not found
        RuntimeError: If cursor-agent returns non-zero exit code

    Examples:
        # Simple JSON output (default)
        result = cursor_cli("Hello, what can you do?")
        print(result)

        # Text output
        result = cursor_cli("Hello", json=False)
        print(result)

        # Streaming output (manual iteration)
        for line in cursor_cli("Explain Python", stream=True):
            print(line)

        # Auto-print to stdout (no manual iteration needed)
        cursor_cli("Explain Python", output_to=True)

        # Auto-print to a file
        cursor_cli("Explain Python", output_to="/path/to/output.txt")

        # Silent mode (run but don't output)
        cursor_cli("Do something", output_to=None)

        # With specific workspace
        result = cursor_cli("Analyze this", workspace="/path/to/project")

        # Resume existing chat
        result = cursor_cli("Continue", chat_id="abc123")
    """
    # Default workspace to current directory
    if workspace is None:
        workspace = os.getcwd()

    # Track if this is a new session
    is_new_session = chat_id is None

    # Create chat if not provided
    if chat_id is None:
        chat_id = create_chat(workspace)

    # Save session ID for this shell and update index if new session
    if save_session:
        session_mgr.set_last_session_id(chat_id, workspace)
        if is_new_session:
            session_mgr.update_index(chat_id, prompt, workspace)
            # Periodically cleanup stale shell sessions
            session_mgr.cleanup_stale_sessions(workspace)
        else:
            # For resumed sessions, check if they exist in the index
            # (they might have been created outside cursor-cli)
            existing = session_mgr.get_session(chat_id, workspace)
            if not existing:
                session_mgr.update_index(chat_id, prompt, workspace)

    # Check if output_to is set (not the sentinel value)
    use_output_to = not isinstance(output_to, _Unset)
    if use_output_to:
        # Force streaming mode when output_to is set
        stream = True

    # Build command arguments
    cmd = [
        "cursor-agent",
        "-p",
        prompt,
        f"--model={model}",
        f"--workspace={workspace}",
        f"--resume={chat_id}",
    ]

    # Add output format based on mode
    if stream:
        cmd.extend(["--output-format", "stream-json", "--stream-partial-output"])
    elif json:
        cmd.extend(["--output-format", "json"])
    else:
        cmd.extend(["--output-format", "text"])

    # Add any extra arguments
    for key, value in extra_args.items():
        arg_name = key.replace("_", "-")
        if isinstance(value, bool):
            if value:
                cmd.append(f"--{arg_name}")
        else:
            cmd.append(f"--{arg_name}={value}")

    if use_output_to:
        # Auto-consume streaming and write to destination, capture for saving
        captured_output = _run_streaming_with_output(cmd, output_to)
        if save_session and captured_output:
            session_mgr.save_conversation(chat_id, prompt, captured_output, workspace)
        return None
    elif stream:
        # For streaming mode, wrap the generator to save after consumption
        return _create_saving_generator(
            _run_streaming(cmd), chat_id, prompt, workspace, save_session
        )
    else:
        result = _run_blocking(cmd, parse_json=json)
        if save_session:
            # Save the output (convert to string if needed)
            output_str = (
                json_module.dumps(result, ensure_ascii=False, indent=2)
                if isinstance(result, dict)
                else str(result)
            )
            session_mgr.save_conversation(chat_id, prompt, output_str, workspace)
        return result


def _create_saving_generator(
    gen: Iterator[str],
    chat_id: str,
    prompt: str,
    workspace: str,
    save_session: bool,
) -> Iterator[str]:
    """
    Wrap a generator to save conversation after it's fully consumed.

    Args:
        gen: The original generator
        chat_id: Session ID
        prompt: User prompt
        workspace: Workspace directory
        save_session: Whether to save the session

    Yields:
        str: Lines from the original generator
    """
    lines = []
    try:
        for line in gen:
            lines.append(line)
            yield line
    finally:
        if save_session and lines:
            output = "\n".join(lines)
            session_mgr.save_conversation(chat_id, prompt, output, workspace)


def _run_blocking(cmd: List[str], parse_json: bool = False) -> Union[str, dict]:
    """
    Run cursor-agent and return complete output.

    Args:
        cmd: Command to execute
        parse_json: If True, parse output as JSON

    Returns:
        str or dict depending on parse_json
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        output = result.stdout

        if parse_json:
            return json_module.loads(output)
        return output

    except subprocess.CalledProcessError as e:
        # Include stderr in error message
        error_msg = e.stderr if e.stderr else str(e)
        raise RuntimeError(f"cursor-agent failed: {error_msg}") from e
    except FileNotFoundError:
        raise FileNotFoundError(
            "cursor-agent not found. Please ensure it's installed and in PATH."
        )


def _run_streaming(cmd: List[str]) -> Iterator[str]:
    """
    Run cursor-agent with streaming output.

    Args:
        cmd: Command to execute

    Yields:
        str: Each line of JSON output
    """
    # Collect stderr in a separate thread to avoid deadlock
    stderr_chunks: List[str] = []

    def read_stderr(pipe: TextIO) -> None:
        """Read stderr in a separate thread to prevent buffer deadlock."""
        try:
            for line in pipe:
                stderr_chunks.append(line)
        except Exception:
            pass

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line-buffered
        )

        assert process.stdout is not None
        assert process.stderr is not None

        # Start stderr reader thread to prevent deadlock
        stderr_thread = threading.Thread(
            target=read_stderr, args=(process.stderr,), daemon=True
        )
        stderr_thread.start()

        # Yield lines as they come
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                yield line.rstrip("\n")

        # Wait for stderr thread to finish
        stderr_thread.join(timeout=1.0)

        # Check for errors after completion
        stderr_output = "".join(stderr_chunks)
        if process.returncode != 0:
            raise RuntimeError(
                f"cursor-agent failed with exit code {process.returncode}: {stderr_output}"
            )

    except FileNotFoundError:
        raise FileNotFoundError(
            "cursor-agent not found. Please ensure it's installed and in PATH."
        )


def _run_streaming_with_output(
    cmd: List[str],
    output: Union[None, bool, str, TextIO],
) -> Optional[str]:
    """
    Run cursor-agent with streaming output and automatically write to destination.

    Uses StreamJsonFormatter to format output with aggregated sections (similar to
    --stream mode in CLI), making output more readable.

    Args:
        cmd: Command to execute
        output: Output destination:
            - None: Silent mode, don't output anywhere
            - True: Output to sys.stdout
            - TextIO: Output to the specified stream
            - str: Output to file at this path

    Returns:
        Captured output string for saving, or None if no formatter was used
    """
    # Determine the actual output stream
    should_close = False
    out_stream: Optional[TextIO] = None
    formatter: Optional[StreamJsonFormatter] = None
    # Capture output to a buffer for saving
    capture_buffer = StringIO()
    capture_formatter: Optional[StreamJsonFormatter] = None

    if output is None or output is False:
        # Silent mode - still capture for saving
        capture_formatter = StreamJsonFormatter(output=capture_buffer, use_colors=False)
        formatter = None
    elif output is True:
        formatter = StreamJsonFormatter(output=sys.stdout, use_colors=True)
        capture_formatter = StreamJsonFormatter(output=capture_buffer, use_colors=False)
    elif isinstance(output, str):
        out_stream = open(output, "w")
        should_close = True
        # File output - disable colors
        formatter = StreamJsonFormatter(output=out_stream, use_colors=False)
        capture_formatter = StreamJsonFormatter(output=capture_buffer, use_colors=False)
    else:
        # Assume it's a TextIO-like object
        out_stream = output
        # Check if output supports colors (is a tty)
        use_colors = hasattr(out_stream, "isatty") and out_stream.isatty()
        formatter = StreamJsonFormatter(output=out_stream, use_colors=use_colors)
        capture_formatter = StreamJsonFormatter(output=capture_buffer, use_colors=False)

    # Collect stderr in a separate thread to avoid deadlock
    stderr_chunks: List[str] = []

    def read_stderr(pipe: TextIO) -> None:
        """Read stderr in a separate thread to prevent buffer deadlock."""
        try:
            for line in pipe:
                stderr_chunks.append(line)
        except Exception:
            pass

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line-buffered
        )

        assert process.stdout is not None
        assert process.stderr is not None

        # Start stderr reader thread to prevent deadlock
        stderr_thread = threading.Thread(
            target=read_stderr, args=(process.stderr,), daemon=True
        )
        stderr_thread.start()

        # Stream lines and format output using StreamJsonFormatter
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                if formatter is not None:
                    formatter.process_line(line)
                if capture_formatter is not None:
                    capture_formatter.process_line(line)

        # Wait for stderr thread to finish
        stderr_thread.join(timeout=1.0)

        # Finalize the formatters
        if formatter is not None:
            formatter.finalize()
        if capture_formatter is not None:
            capture_formatter.finalize()

        # Check for errors after completion
        stderr_output = "".join(stderr_chunks)
        if process.returncode != 0:
            raise RuntimeError(
                f"cursor-agent failed with exit code {process.returncode}: {stderr_output}"
            )

        # Return captured output
        return capture_buffer.getvalue()

    except FileNotFoundError:
        raise FileNotFoundError(
            "cursor-agent not found. Please ensure it's installed and in PATH."
        )
    finally:
        if should_close and out_stream is not None:
            out_stream.close()
        capture_buffer.close()
