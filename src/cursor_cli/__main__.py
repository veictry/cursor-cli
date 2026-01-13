"""
Main entry point for running cursor_cli as a module.

Usage:
    python -m cursor_cli [cursor-agent args...]

Or if installed with entry point:
    cursor-cli [cursor-agent args...]

Default (streaming mode):
    cursor-cli "your prompt"
    # Equivalent to:
    cursor-cli --output-format stream-json --stream-partial-output -p "your prompt"

Text mode:
    cursor-cli --text "your prompt"
    # Equivalent to:
    cursor-cli --output-format text -p "your prompt"

Danger mode (setup permissions):
    cursor-cli --danger
    # Creates ~/.cursor/cli-config.json with extended permissions (default)

    cursor-cli --danger /path/to/folder
    # Creates /path/to/folder/.cursor/cli-config.json with extended permissions

Install cursor-agent:
    cursor-cli --install
    # Installs cursor-agent CLI and sets up PATH environment variable
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path
from io import StringIO
from .runner import CursorCLIRunner, create_chat
from .formatter import StreamJsonFormatter
from . import session as session_mgr


# Base permissions to ensure in cli-config.json (always added)
BASE_PERMISSIONS = {
    "allow": [
        "Shell(*)",
        "Read(*)",
    ],
    "deny": [],
}

# cursor-agent subcommands that should be passed through without formatting
CURSOR_AGENT_SUBCOMMANDS = {
    "install-shell-integration",
    "uninstall-shell-integration",
    "login",
    "logout",
    "mcp",
    "status",
    "whoami",
    "update",
    "upgrade",
    "create-chat",
    "agent",
    "ls",
    "resume",
    "help",
}


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for the runner."""
    parser = argparse.ArgumentParser(
        prog="cursor-cli",
        description="A wrapper for cursor-agent with formatted output support. "
        "Default mode is streaming with formatted output.",
        epilog="All unknown arguments are passed directly to cursor-agent.",
        add_help=False,  # We'll handle help ourselves to allow passthrough
    )

    # Runner-specific arguments
    runner_group = parser.add_argument_group("Runner Options")
    runner_group.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Prompt to send to cursor-agent (streaming mode by default)",
    )
    runner_group.add_argument(
        "--text",
        metavar="PROMPT",
        nargs="?",
        const="__TEXT_MODE__",
        help="Use text output mode instead of streaming. "
        "Equivalent to: --output-format text -p PROMPT",
    )
    runner_group.add_argument(
        "--danger",
        metavar="FOLDER_PATH",
        nargs="?",
        const="__DEFAULT_HOME__",
        help="Setup .cursor/cli-config.json with extended permissions. "
        "Default: ~/.cursor (user home directory)",
    )
    runner_group.add_argument(
        "--no-format",
        action="store_true",
        help="Disable formatted output for stream-json mode",
    )
    runner_group.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )
    runner_group.add_argument(
        "--runner-help", action="store_true", help="Show this help message and exit"
    )
    runner_group.add_argument(
        "--install",
        action="store_true",
        help="Install cursor-agent CLI and setup PATH environment variable",
    )
    runner_group.add_argument(
        "--resume",
        metavar="SESSION_ID",
        nargs="?",
        const="__LAST_SESSION__",
        help="Resume a previous session. If no session ID provided, "
        "resumes the last session from this shell.",
    )
    runner_group.add_argument(
        "--file",
        metavar="FILE_PATH",
        help="Read task from a file. The prompt will be: "
        "'请尝试完成 {absolute_path} 中的任务'",
    )
    runner_group.add_argument(
        "--session",
        nargs="?",
        const="__TOGGLE__",
        metavar="CHAT_ID",
        help="Lock shell to a chat_id. Use 'new' to create a new session. "
        "Run again without args to unlock.",
    )
    runner_group.add_argument(
        "--last-chat-id",
        nargs="?",
        const="__CURRENT_SHELL__",
        metavar="SHELL_PID",
        help="Show the last chat_id for a shell session. "
        "If no SHELL_PID provided, shows info for current shell.",
    )

    return parser


def install_cursor_agent() -> int:
    """
    Install cursor-agent CLI by running the official install script
    and setting up PATH environment variable.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Check if cursor-agent is already installed
        print("Checking for existing cursor-agent installation...")
        try:
            check_result = subprocess.run(
                ["cursor-agent", "--help"],
                capture_output=True,
                check=False,
            )
            if check_result.returncode == 0:
                print("✓ cursor-agent is already installed!")
                print("\nTo check the version, run:")
                print("  cursor-agent --version")
                print("\nTo update to the latest version, run:")
                print("  cursor-agent update")
                return 0
        except FileNotFoundError:
            # cursor-agent not found, proceed with installation
            pass

        print("cursor-agent not found, proceeding with installation...")
        print("-" * 40)

        # Run the install script
        result = subprocess.run(
            ["bash", "-c", "curl https://cursor.com/install -fsS | bash"],
            check=False,
        )

        if result.returncode != 0:
            print(f"\nError: Installation failed with exit code {result.returncode}")
            return 1

        print("\n" + "-" * 40)
        print("Setting up PATH environment variable...")

        # Detect shell and update appropriate rc file
        shell = os.environ.get("SHELL", "")
        home = Path.home()
        path_export = 'export PATH="$HOME/.local/bin:$PATH"'

        rc_files_updated = []

        # Check for bash
        bashrc = home / ".bashrc"
        if bashrc.exists() or "bash" in shell:
            if bashrc.exists():
                content = bashrc.read_text()
            else:
                content = ""

            if path_export not in content:
                with open(bashrc, "a") as f:
                    f.write(f"\n{path_export}\n")
                rc_files_updated.append(str(bashrc))
                print(f"  ✓ Added PATH to {bashrc}")
            else:
                print(f"  ✓ PATH already configured in {bashrc}")

        # Check for zsh
        zshrc = home / ".zshrc"
        if zshrc.exists() or "zsh" in shell:
            if zshrc.exists():
                content = zshrc.read_text()
            else:
                content = ""

            if path_export not in content:
                with open(zshrc, "a") as f:
                    f.write(f"\n{path_export}\n")
                rc_files_updated.append(str(zshrc))
                print(f"  ✓ Added PATH to {zshrc}")
            else:
                print(f"  ✓ PATH already configured in {zshrc}")

        print("\n" + "=" * 40)
        print("✓ Installation complete!")
        print("\nTo start using cursor-agent, either:")
        print("  1. Open a new terminal, or")
        print("  2. Run one of the following commands:")

        if "zsh" in shell:
            print("     source ~/.zshrc")
        elif "bash" in shell:
            print("     source ~/.bashrc")
        else:
            if rc_files_updated:
                for rc_file in rc_files_updated:
                    print(f"     source {rc_file}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: Required command not found: {e}")
        return 1
    except PermissionError as e:
        print(f"Error: Permission denied: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def setup_danger_permissions(folder_path: str) -> int:
    """
    Setup .cursor/cli-config.json with extended permissions.

    Adds Write permission for the current working directory.
    Running in different directories will accumulate Write permissions.

    Args:
        folder_path: Path to the folder where .cursor directory will be created

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        folder = Path(folder_path).resolve()

        if not folder.exists():
            print(f"Error: Folder does not exist: {folder}")
            return 1

        if not folder.is_dir():
            print(f"Error: Path is not a directory: {folder}")
            return 1

        # Create .cursor directory
        cursor_dir = folder / ".cursor"
        cursor_dir.mkdir(exist_ok=True)

        # Config file path
        config_file = cursor_dir / "cli-config.json"

        # Load existing config or create new
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Invalid JSON in {config_file}, creating new config")
                config = {}
        else:
            config = {}

        # Ensure permissions structure exists
        if "permissions" not in config:
            config["permissions"] = {}

        permissions = config["permissions"]

        # Ensure allow list exists
        if "allow" not in permissions:
            permissions["allow"] = []

        # Ensure deny list exists
        if "deny" not in permissions:
            permissions["deny"] = []

        # Append base permissions if not already present
        for perm in BASE_PERMISSIONS["allow"]:
            if perm not in permissions["allow"]:
                permissions["allow"].append(perm)
                print(f"  Added permission: {perm}")

        # Add Write permission for current working directory
        cwd = Path.cwd().resolve()
        write_perm = f"Write({cwd}/**/*)"

        if write_perm not in permissions["allow"]:
            permissions["allow"].append(write_perm)
            print(f"  Added permission: {write_perm}")
        else:
            print(f"  Already exists: {write_perm}")

        # Write config back
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.write("\n")

        print(f"✓ Updated {config_file}")
        print(f"\nCurrent permissions.allow:")
        for perm in permissions["allow"]:
            print(f"  - {perm}")

        return 0

    except PermissionError as e:
        print(f"Error: Permission denied: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def expand_args(runner_args, cursor_args: list) -> list:
    """
    Expand shorthand arguments to full cursor-agent arguments.

    Default (streaming):
        "prompt" expands to:
        --output-format stream-json --stream-partial-output -p "prompt"

    --text "prompt" expands to:
        --output-format text -p "prompt"

    Note: --resume is handled separately in run_with_session_management
    """
    expanded = []

    # Check if --text mode is requested
    if runner_args.text is not None:
        # Text mode
        expanded.extend(["--output-format", "text"])

        # Add prompt: either from --text value or from positional prompt
        if runner_args.text != "__TEXT_MODE__":
            expanded.extend(["-p", runner_args.text])
        elif runner_args.prompt:
            expanded.extend(["-p", runner_args.prompt])

        # Append any additional cursor args
        expanded.extend(cursor_args)
        return expanded

    # Default: streaming mode
    if runner_args.prompt:
        expanded.extend(["--output-format", "stream-json", "--stream-partial-output"])
        expanded.extend(["-p", runner_args.prompt])
        expanded.extend(cursor_args)
        return expanded

    # No prompt provided, just pass through cursor_args
    expanded.extend(cursor_args)
    return expanded


def is_subcommand(argv: list) -> bool:
    """
    Check if the first argument is a cursor-agent subcommand.

    Args:
        argv: Command-line arguments

    Returns:
        True if the first argument is a subcommand
    """
    if not argv:
        return False
    first_arg = argv[0]
    # Check if it's a subcommand (not starting with -)
    if first_arg.startswith("-"):
        return False
    return first_arg in CURSOR_AGENT_SUBCOMMANDS


def run_with_session_management(
    cursor_args: list,
    prompt: str,
    resume_id: str | None,
    use_colors: bool,
    format_output: bool,
    initial_prompt: str | None = None,
) -> int:
    """
    Run cursor-agent with session management.

    Creates/resumes sessions and saves conversation logs.

    Args:
        cursor_args: Arguments to pass to cursor-agent
        prompt: The user prompt
        resume_id: Session ID to resume (or "__LAST_SESSION__" or None)
        use_colors: Whether to use colored output
        format_output: Whether to format stream-json output
        initial_prompt: The initial prompt to record in db (defaults to prompt)

    Returns:
        Exit code
    """
    # Use prompt as initial_prompt if not specified
    if initial_prompt is None:
        initial_prompt = prompt
    import subprocess
    import threading
    from typing import List, TextIO

    workspace = os.getcwd()

    # Check for locked session
    locked_session = session_mgr.get_locked_session_id(workspace)

    # Determine session ID
    # Priority: explicit --resume > locked session > new session
    session_id: str | None = None
    is_new_session = False

    if resume_id == "__LAST_SESSION__":
        # --resume without argument: use last session from this shell
        session_id = session_mgr.get_last_session_id(workspace)
        if not session_id:
            # No previous session, create new one
            print(
                "Warning: No previous session found for this shell. "
                "Starting a new session.",
                file=sys.stderr,
            )
            is_new_session = True
    elif resume_id:
        # Explicit --resume <chat_id>: use the specified session
        session_id = resume_id
    else:
        # Check if --resume is already in cursor_args
        for i, arg in enumerate(cursor_args):
            if arg.startswith("--resume="):
                session_id = arg.split("=", 1)[1]
                break
            elif arg == "--resume" and i + 1 < len(cursor_args):
                session_id = cursor_args[i + 1]
                break

        if not session_id:
            # No --resume specified, check for locked session
            if locked_session:
                session_id = locked_session
                print(f"[🔒 Using locked session: {session_id}]", file=sys.stderr)
            else:
                is_new_session = True

    # Create new session if needed
    if is_new_session:
        session_id = create_chat(workspace)

    assert session_id is not None

    # Add --resume to args if not already there
    has_resume = any(
        arg.startswith("--resume=") or arg == "--resume"
        for arg in cursor_args
    )
    if not has_resume:
        cursor_args = [f"--resume={session_id}"] + cursor_args

    # Update session tracking
    session_mgr.set_last_session_id(session_id, workspace)
    if is_new_session:
        session_mgr.update_index(session_id, initial_prompt, workspace)
        session_mgr.cleanup_stale_sessions(workspace)
    else:
        # For resumed sessions, check if they exist in the index
        # (they might have been created outside cursor-cli, e.g., via cursor-agent create-chat)
        existing = session_mgr.get_session(session_id, workspace)
        if not existing:
            session_mgr.update_index(session_id, initial_prompt, workspace)

    # Build command
    cmd = ["cursor-agent"] + cursor_args

    # Create conversation file immediately for real-time writing
    # Use initial_prompt for the file header (original file content if --file was used)
    conv_writer = session_mgr.ConversationWriter(session_id, initial_prompt, workspace)

    # Collect stderr in a separate thread
    stderr_chunks: List[str] = []

    def read_stderr(pipe: TextIO) -> None:
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
            bufsize=1,
        )

        assert process.stdout is not None
        assert process.stderr is not None

        # Start stderr reader thread
        stderr_thread = threading.Thread(
            target=read_stderr, args=(process.stderr,), daemon=True
        )
        stderr_thread.start()

        # Determine if we should format output
        is_stream_json = "--output-format" in cursor_args and any(
            "stream-json" in arg for arg in cursor_args
        )
        should_format = format_output and is_stream_json

        if should_format:
            # Use formatter for display, and a capture formatter for file writing
            display_formatter = StreamJsonFormatter(
                output=sys.stdout, use_colors=use_colors
            )
            # Create a wrapper that writes to the conversation file
            file_buffer = StringIO()
            capture_formatter = StreamJsonFormatter(
                output=file_buffer, use_colors=False
            )

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    display_formatter.process_line(line)
                    # Capture formatted output
                    old_pos = file_buffer.tell()
                    capture_formatter.process_line(line)
                    # Write any new content to file in real-time
                    new_pos = file_buffer.tell()
                    if new_pos > old_pos:
                        file_buffer.seek(old_pos)
                        new_content = file_buffer.read()
                        conv_writer.write(new_content)

            display_formatter.finalize()
            # Capture final content
            old_pos = file_buffer.tell()
            capture_formatter.finalize()
            new_pos = file_buffer.tell()
            if new_pos > old_pos:
                file_buffer.seek(old_pos)
                new_content = file_buffer.read()
                conv_writer.write(new_content)

            file_buffer.close()
        else:
            # Raw output - write directly to both stdout and file
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    conv_writer.write(line)

        # Wait for stderr thread
        stderr_thread.join(timeout=1.0)

        # Print any stderr
        stderr_output = "".join(stderr_chunks)
        if stderr_output:
            sys.stderr.write(stderr_output)
            sys.stderr.flush()

        return process.returncode or 0

    except FileNotFoundError:
        sys.stderr.write(
            "Error: cursor-agent not found. Please ensure it's installed and in PATH.\n"
        )
        return 1
    except Exception as e:
        sys.stderr.write(f"Error running cursor-agent: {e}\n")
        return 1
    finally:
        conv_writer.close()


def main(argv: list | None = None) -> int:
    """
    Main entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    if argv is None:
        argv = sys.argv[1:]

    # Check if this is a cursor-agent subcommand (pass through without formatting)
    if is_subcommand(argv):
        runner = CursorCLIRunner(use_colors=True)
        return runner.run(argv, format_output=False)

    # Parse our known arguments, passing rest to cursor-agent
    parser = create_parser()
    runner_args, cursor_args = parser.parse_known_args(argv)

    # Handle --install mode
    if runner_args.install:
        return install_cursor_agent()

    # Handle --danger mode
    if runner_args.danger is not None:
        # Default to user home directory if no path specified
        if runner_args.danger == "__DEFAULT_HOME__":
            folder_path = str(Path.home())
        else:
            folder_path = runner_args.danger
        return setup_danger_permissions(folder_path)

    # Handle --last-chat-id
    if runner_args.last_chat_id is not None:
        workspace = os.getcwd()
        # Determine which shell to query
        if runner_args.last_chat_id == "__CURRENT_SHELL__":
            shell_pid = None  # Will use current shell
            shell_label = "this shell"
        else:
            shell_pid = runner_args.last_chat_id
            shell_label = f"shell {shell_pid}"

        session_id = session_mgr.get_last_session_id(workspace, shell_pid)
        locked_id = session_mgr.get_locked_session_id_for_shell(workspace, shell_pid)
        if session_id:
            if locked_id:
                print(f"{session_id} (🔒 locked to: {locked_id})")
            else:
                print(session_id)
        else:
            print(f"No session found for {shell_label}.")
        return 0

    # Handle --session (lock/unlock)
    if runner_args.session is not None:
        workspace = os.getcwd()
        current_locked = session_mgr.get_locked_session_id(workspace)

        if runner_args.session == "__TOGGLE__":
            # No chat_id specified - toggle lock
            if current_locked:
                # Currently locked, unlock it
                session_mgr.clear_session_lock(workspace)
                print(f"🔓 Session unlocked (was: {current_locked})")
                print("New commands will create new sessions.")
            else:
                # Not locked, try to lock to last session
                last_session = session_mgr.get_last_session_id(workspace)
                if last_session:
                    session_mgr.set_session_lock(last_session, workspace)
                    print(f"🔒 Session locked to: {last_session}")
                    print("All commands in this shell will use this chat_id.")
                else:
                    # No previous session, create a new one
                    new_session = create_chat(workspace)
                    session_mgr.set_session_lock(new_session, workspace)
                    session_mgr.set_last_session_id(new_session, workspace)
                    print(f"🔒 Created and locked to new session: {new_session}")
                    print("All commands in this shell will use this chat_id.")
        elif runner_args.session.lower() == "new":
            # Explicitly create a new session
            new_session = create_chat(workspace)
            session_mgr.set_session_lock(new_session, workspace)
            session_mgr.set_last_session_id(new_session, workspace)
            print(f"🔒 Created and locked to new session: {new_session}")
            print("All commands in this shell will use this chat_id.")
        else:
            # Specific chat_id provided
            chat_id = runner_args.session
            session_mgr.set_session_lock(chat_id, workspace)
            session_mgr.set_last_session_id(chat_id, workspace)
            print(f"🔒 Session locked to: {chat_id}")
            print("All commands in this shell will use this chat_id.")

        print("\nRun 'cursor-cli --session' again to unlock.")
        return 0

    # Show help if requested
    if runner_args.runner_help:
        parser.print_help()
        print("\n" + "=" * 60)
        print("Run 'cursor-agent --help' for cursor-agent specific options.")
        print("\nExamples:")
        print('  cursor-cli "Analyze this project"          # streaming mode (default)')
        print('  cursor-cli --text "Analyze this project"   # text mode')
        print('  cursor-cli --no-color "Hello"              # streaming without colors')
        print(
            '  cursor-cli --no-format "Hello"             # streaming without formatting'
        )
        print(
            "  cursor-cli --danger                        # setup permissions in ~/.cursor"
        )
        print(
            "  cursor-cli --danger /path/to/folder        # setup permissions in folder/.cursor"
        )
        print(
            "  cursor-cli --install                       # install cursor-agent and setup PATH"
        )
        print(
            '  cursor-cli --resume "Continue..."          # resume last session from this shell'
        )
        print(
            '  cursor-cli --resume abc123 "Continue..."   # resume specific session'
        )
        print("\nSession Management:")
        print("  Conversations are saved to .cursor-cli/ in your workspace:")
        print("    .cursor-cli/index.md              # index of all sessions")
        print("    .cursor-cli/<session_id>/         # session directory")
        print("    .cursor-cli/<session_id>/*.md     # conversation logs")
        return 0

    # Expand shorthand args
    cursor_args = expand_args(runner_args, cursor_args)

    # Show help if --help is in cursor_args
    if "--help" in cursor_args or "-h" in cursor_args:
        # First show cursor-cli help
        parser.print_help()
        sys.stdout.flush()
        print("\n" + "=" * 60)
        print("cursor-agent options:")
        print("=" * 60 + "\n")
        sys.stdout.flush()
        # Then show cursor-agent help
        import subprocess
        subprocess.run(["cursor-agent", "--help"], check=False)
        return 0

    # Check if we're using the simplified mode (with prompt)
    # In this case, we handle session management
    prompt = runner_args.prompt or (
        runner_args.text if runner_args.text and runner_args.text != "__TEXT_MODE__" else None
    )

    # Handle --file option: read file content and use absolute path in prompt
    file_content = None
    if runner_args.file:
        file_path = Path(runner_args.file).resolve()  # Get absolute path
        if not file_path.exists():
            print(f"Error: File not found: {runner_args.file}", file=sys.stderr)
            return 1
        try:
            # Read file content for recording in database
            file_content = file_path.read_text(encoding="utf-8")
            # Use absolute path in prompt (cursor-agent can read the file)
            prompt = f"请尝试完成 {file_path} 中的任务"
            # Add streaming format and prompt to cursor_args
            cursor_args = [
                "--output-format", "stream-json", "--stream-partial-output",
                "-p", prompt
            ] + cursor_args
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            return 1

    # Check if --resume was given with what looks like a prompt
    # (e.g., "cursor-cli --resume 'What did I say?'")
    resume_as_prompt = None
    if runner_args.resume and runner_args.resume != "__LAST_SESSION__":
        # If resume value contains spaces or is long, it's likely a prompt
        if " " in runner_args.resume or len(runner_args.resume) > 50:
            resume_as_prompt = runner_args.resume
            # Add streaming format and prompt to cursor_args
            cursor_args = [
                "--output-format", "stream-json", "--stream-partial-output",
                "-p", resume_as_prompt
            ] + cursor_args

    # If no arguments and no resume-as-prompt, show help
    if not cursor_args and not prompt and not resume_as_prompt and not runner_args.resume:
        parser.print_help()
        print("\n" + "=" * 60)
        print("No arguments provided. Run 'cursor-agent --help' for options.")
        print("\nQuick start:")
        print('  cursor-cli "Your prompt here"')
        return 0

    if prompt or resume_as_prompt or runner_args.resume:
        # Simplified mode with session management
        # Use file_content as initial_prompt for db recording if available
        initial_prompt = file_content if file_content else (prompt or resume_as_prompt)
        return run_with_session_management(
            cursor_args=cursor_args,
            prompt=prompt or resume_as_prompt,
            initial_prompt=initial_prompt,
            resume_id="__LAST_SESSION__" if resume_as_prompt else runner_args.resume,
            use_colors=not runner_args.no_color,
            format_output=not runner_args.no_format,
        )
    else:
        # Direct passthrough mode (no session management)
        runner = CursorCLIRunner(use_colors=not runner_args.no_color)
        return runner.run(cursor_args, format_output=not runner_args.no_format)


if __name__ == "__main__":
    sys.exit(main())
