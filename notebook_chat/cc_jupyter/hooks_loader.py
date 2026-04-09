"""
Python hooks loader for notebook-chat.

Users can define their own hooks in a Python file (default: ~/.claude/notebook_chat_hooks.py
or set NOTEBOOK_CHAT_HOOKS_FILE env var).

The file must define a module-level dict called HOOKS:

    from claude_agent_sdk import HookMatcher
    from claude_agent_sdk.types import PreToolUseHookInput, StopHookInput, HookContext

    async def log_tool(input, event_name, ctx):
        print(f"[hook] {input['tool_name']}", flush=True)
        return {}

    async def on_stop(input, event_name, ctx):
        print("[hook] session ended", flush=True)
        return {}

    HOOKS = {
        "PreToolUse": [HookMatcher(hooks=[log_tool])],
        "Stop":       [HookMatcher(hooks=[on_stop])],
    }

Supported events:
  PreToolUse, PostToolUse, PostToolUseFailure,
  UserPromptSubmit, Stop, SubagentStop,
  PreCompact, Notification, SubagentStart, PermissionRequest
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any


_DEFAULT_HOOKS_FILE = Path.home() / ".claude" / "notebook_chat_hooks.py"


def load_hooks(hooks_file: str | None = None) -> dict[str, Any] | None:
    """
    Load hooks from a Python file and return the HOOKS dict.

    Args:
        hooks_file: Path to the hooks file. Defaults to ~/.claude/notebook_chat_hooks.py
                    or NOTEBOOK_CHAT_HOOKS_FILE env var.

    Returns:
        The HOOKS dict from the file, or None if file not found / no HOOKS defined.
    """
    if hooks_file is None:
        hooks_file = os.environ.get("NOTEBOOK_CHAT_HOOKS_FILE") or str(_DEFAULT_HOOKS_FILE)

    path = Path(hooks_file).expanduser()
    if not path.exists():
        return None

    try:
        spec = importlib.util.spec_from_file_location("_notebook_chat_hooks", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        hooks = getattr(module, "HOOKS", None)
        if hooks is not None:
            print(f"🪝 Loaded hooks from {path}", flush=True)
        return hooks
    except Exception as e:
        print(f"⚠️  Failed to load hooks from {path}: {e}", flush=True)
        return None
