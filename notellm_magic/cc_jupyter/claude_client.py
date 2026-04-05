"""
Claude API client integration for Jupyter magic.
Handles streaming queries and message processing by creating fresh ClaudeSDKClient instances.
"""

from __future__ import annotations

import asyncio
import contextlib
import traceback
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from .constants import EXECUTE_PYTHON_TOOL_NAME
from .jupyter_integration import is_in_jupyter_notebook

if TYPE_CHECKING:
    from .magics import ClaudeCodeMagics

MARKDOWN_PATTERNS = [
    "```",  # Code blocks
    "`",  # Inline code
    "    ",  # Indented code blocks
    "\t",  # Indented code blocks
    "**",  # Bold
    "##",  # Headers (checking for at least level 2)
    "](",  # Links/images
    "---",  # Tables
    ">",  # Blockquotes
    "~~",  # Strikethrough
]


def _display_cost(message: ResultMessage) -> None:
    """Print a compact cost/usage summary from a ResultMessage."""
    parts = []
    if message.total_cost_usd is not None:
        parts.append(f"💰 ${message.total_cost_usd:.4f}")
    if message.usage:
        inp = message.usage.get("input_tokens", 0)
        out = message.usage.get("output_tokens", 0)
        cache_read = message.usage.get("cache_read_input_tokens", 0)
        if inp or out:
            token_str = f"↑{inp:,} ↓{out:,}"
            if cache_read:
                token_str += f" cache↩{cache_read:,}"
            parts.append(token_str)
    if message.num_turns:
        parts.append(f"{message.num_turns} turn{'s' if message.num_turns != 1 else ''}")
    if message.duration_ms:
        parts.append(f"{message.duration_ms / 1000:.1f}s")
    if parts:
        print(f"\n{'  '.join(parts)}", flush=True)


def _display_claude_message_with_markdown(text: str) -> None:
    """Display a Claude message with markdown rendering if relevant and available."""
    claude_message = f"💭 Claude: {text}"

    # IPython displays markdown as <IPython.core.display.Markdown object>
    if not is_in_jupyter_notebook():
        print(claude_message, flush=True)
        return

    # Simple check: if text has any markdown elements, use markdown display
    has_markdown = any(pattern in text for pattern in MARKDOWN_PATTERNS)
    if not has_markdown:
        print(claude_message)
        return

    try:
        from IPython.display import Markdown, display

        display(Markdown(claude_message))
    except (ImportError, LookupError):
        # LookupError: Jupyter's parent_header ContextVar is not set in our
        # background asyncio context, so fall back to plain print.
        print(claude_message, flush=True)


def _format_tool_call(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Format tool calls to match Claude CLI style with meaningful details."""
    # Map tool names to their user-facing names
    tool_display_names = {
        "LS": "List",
        "GrepToolv2": "Search",
        EXECUTE_PYTHON_TOOL_NAME: "CreateNotebookCell",
    }

    display_name = tool_display_names.get(tool_name, tool_name)

    # Format based on tool type with most relevant info
    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        parts = [f"{display_name}({file_path})"]
        if "offset" in tool_input:
            parts.append(f"offset: {tool_input['offset']}")
        if "limit" in tool_input:
            parts.append(f"limit: {tool_input['limit']}")
        return " ".join(parts)

    if tool_name == "LS":
        path = tool_input.get("path", "")
        return f"{display_name}({path})"

    if tool_name == "GrepToolv2":
        pattern = tool_input.get("pattern", "")
        parts = [f'{display_name}(pattern: "{pattern}"']

        # Add path if not current directory
        path = tool_input.get("path")
        parts.append(f'path: "{path}"')

        # Add other relevant options
        if "glob" in tool_input:
            parts.append(f'glob: "{tool_input["glob"]}"')
        if "type" in tool_input:
            parts.append(f'type: "{tool_input["type"]}"')
        if (
            tool_input.get("output_mode")
            and tool_input["output_mode"] != "files_with_matches"
        ):
            parts.append(f'output_mode: "{tool_input["output_mode"]}"')
        if "head_limit" in tool_input:
            parts.append(f"head_limit: {tool_input['head_limit']}")

        return ", ".join(parts) + ")"

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        return f'{display_name}("{command}")'

    if tool_name in ["Write", "Edit", "MultiEdit"]:
        file_path = tool_input.get("file_path", "")
        return f"{display_name}({file_path})"

    if tool_name == "Glob":
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", "")
        if path:
            return f'{display_name}(pattern: "{pattern}", path: "{path}")'
        return f'{display_name}("{pattern}")'

    if tool_name == "WebFetch":
        url = tool_input.get("url", "")
        return f'{display_name}("{url}")'

    if tool_name == "WebSearch":
        query = tool_input.get("query", "")
        return f'{display_name}("{query}")'

    if tool_name == "TodoWrite":
        todos = tool_input.get("todos", [])
        return f"{display_name}({len(todos)} items)"

    return display_name


class ClaudeClientManager:
    """Manages ClaudeSDKClient instances for Jupyter magic, creating fresh clients per query."""

    def __init__(self) -> None:
        """Initialize the client manager."""
        self._session_id: str | None = None
        self._interrupt_requested: bool = False
        self._current_client: ClaudeSDKClient | None = None

    async def query_sync(
        self,
        prompt: str | list[dict[str, Any]],
        options: ClaudeAgentOptions,
        is_new_conversation: bool,
        verbose: bool = False,
        enable_interrupt: bool = True,
        show_cost: bool = True,
    ) -> tuple[list[str], list[str]]:
        """
        Send a query and collect all responses synchronously.
        Creates a new ClaudeSDKClient for each query.

        Args:
            prompt: The prompt to send to Claude (string or list of content blocks)
            options: Claude Code options to use for this query
            is_new_conversation: Whether this is a new conversation
            verbose: Whether to show verbose output
            enable_interrupt: If True, enables interrupt handling

        Returns:
            Tuple of (assistant_messages, tool_calls)
        """
        # Ensure we have an async checkpoint at the start
        await asyncio.sleep(0)

        tool_calls: list[str] = []
        assistant_messages: list[str] = []
        self._interrupt_requested = False

        # If we have a stored session ID and this is not a new conversation, use it for resumption
        # But only if the options don't already have a resume value set
        if self._session_id and not is_new_conversation:
            if not options.resume:
                options.resume = self._session_id
            # Also set continue_conversation to true when resuming
            options.continue_conversation = True

        # Create a new client for this query
        client = ClaudeSDKClient(options=options)
        self._current_client = client

        try:
            # Connect the client
            await client.connect()

            # Send the query based on prompt type
            if isinstance(prompt, list):
                # Structured content with images
                async def content_generator() -> Any:  # noqa: ANN401
                    await asyncio.sleep(0)
                    message = {
                        "type": "user",
                        "message": {"role": "user", "content": prompt},
                        "parent_tool_use_id": None,
                    }
                    yield message
                    await asyncio.sleep(0)

                await client.query(content_generator())
            else:
                # Simple string prompt
                await client.query(prompt)

            # Process responses
            has_printed_model = not is_new_conversation

            # If interrupt support is enabled, we need to handle messages differently
            if enable_interrupt:
                # Collect messages with interrupt checking
                messages_to_process: list[Any] = []

                async def collect_messages() -> None:
                    await asyncio.sleep(0)
                    async for message in client.receive_response():
                        messages_to_process.append(message)
                        if isinstance(message, ResultMessage):
                            break

                collect_task = asyncio.create_task(collect_messages())

                # Monitor for interrupts
                while True:
                    if self._interrupt_requested:
                        collect_task.cancel()
                        await client.interrupt()
                        print("\n⚠️ Query interrupted by user", flush=True)
                        break

                    # Check if we're done
                    if messages_to_process and isinstance(
                        messages_to_process[-1], ResultMessage
                    ):
                        break

                    await asyncio.sleep(0.05)

                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await collect_task

                # Process collected messages
                for message in messages_to_process:
                    if isinstance(message, AssistantMessage):
                        if hasattr(message, "model") and not has_printed_model:
                            print(f"🧠 Claude model: {message.model}")
                            has_printed_model = True
                        for block in message.content:
                            if isinstance(block, TextBlock) and block.text.strip():
                                _display_claude_message_with_markdown(block.text)
                                assistant_messages.append(block.text)
                            elif isinstance(block, ToolUseBlock):
                                tool_display = _format_tool_call(
                                    block.name, block.input
                                )
                                print(f"⏺ {tool_display}", flush=True)
                                if verbose:
                                    print(f"  ⎿  Arguments: {block.input}", flush=True)
                                tool_calls.append(f"{block.name}: {block.input}")
                    elif isinstance(message, ResultMessage):
                        if (
                            message.session_id
                            and message.session_id != self._session_id
                        ):
                            self._session_id = message.session_id
                            print(
                                f"📍 Claude Code Session ID: {self._session_id}",
                                flush=True,
                            )
                        if show_cost:
                            _display_cost(message)
            else:
                # Simple mode without interrupt support
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        if hasattr(message, "model") and not has_printed_model:
                            print(f"🧠 Claude model: {message.model}")
                            has_printed_model = True
                        for block in message.content:
                            if isinstance(block, TextBlock) and block.text.strip():
                                _display_claude_message_with_markdown(block.text)
                                assistant_messages.append(block.text)
                            elif isinstance(block, ToolUseBlock):
                                tool_display = _format_tool_call(
                                    block.name, block.input
                                )
                                print(f"\n⏺ {tool_display}", flush=True)
                                if verbose:
                                    print(f"  ⎿  Arguments: {block.input}", flush=True)
                                tool_calls.append(f"{block.name}: {block.input}")
                    elif isinstance(message, ResultMessage):
                        if (
                            message.session_id
                            and message.session_id != self._session_id
                        ):
                            self._session_id = message.session_id
                            print(
                                f"\n📍 Claude Code Session ID: {self._session_id}",
                                flush=True,
                            )
                        if show_cost:
                            _display_cost(message)
                        break

        except Exception as e:
            # Check if this is a broken pipe/resource error
            error_type_str = str(type(e))
            error_msg_str = str(e)
            if any(
                err in error_type_str or err in error_msg_str
                for err in [
                    "BrokenResourceError",
                    "BrokenPipeError",
                    "ClosedResourceError",
                ]
            ):
                if not self._interrupt_requested:
                    print(
                        "\n⚠️ Connection was lost. A new connection will be created automatically.",
                        flush=True,
                    )
            else:
                print(f"\n❌ Error during Claude execution: {e!s}")
                if verbose:
                    print(traceback.format_exc())
        finally:
            # Always disconnect and clean up the client
            try:
                await asyncio.wait_for(client.disconnect(), timeout=2)
            except Exception:
                pass  # Ignore disconnect errors
            self._current_client = None

        return assistant_messages, tool_calls

    async def handle_interrupt(self) -> None:
        """Send an interrupt signal to the current client if one exists."""
        self._interrupt_requested = True
        if self._current_client is not None:
            with contextlib.suppress(Exception):
                await self._current_client.interrupt()
        await asyncio.sleep(0)

    def reset_session(self) -> None:
        """Clear the stored session ID to start a new conversation."""
        self._session_id = None

    @property
    def session_id(self) -> str | None:
        """Get the current session ID if available."""
        return self._session_id


async def run_streaming_query(
    parent: ClaudeCodeMagics,
    prompt: str | list[dict[str, Any]],
    options: ClaudeAgentOptions,
    verbose: bool,
) -> None:
    """
    Run Claude query with real-time message streaming using a fresh client.
    This function maintains compatibility with the existing interface.
    """
    # Ensure client manager exists
    if not hasattr(parent, "_client_manager") or parent._client_manager is None:
        parent._client_manager = ClaudeClientManager()

    # Run the query with a fresh client
    await parent._client_manager.query_sync(
        prompt,
        options,
        parent._config_manager.is_new_conversation,
        verbose,
        show_cost=parent._config_manager.show_cost,
    )

    # Update last output line
    parent._history_manager.update_last_output_line()
