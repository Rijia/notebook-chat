"""
Configuration management for Claude Code Jupyter magic.
Handles all configuration options and command-line argument processing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .constants import (
    CLEANUP_PROMPTS_TEXT,
    HELP_TEXT,
    QUEUED_EXECUTION_TEXT,
)

if TYPE_CHECKING:
    from .cell_watcher import CellWatcher


class ConfigManager:
    """Manages configuration state for Claude Code magic."""

    def __init__(self) -> None:
        """Initialize configuration with defaults."""
        # Cleanup settings
        self.should_cleanup_prompts = False
        self.editing_current_cell = False

        # Conversation settings
        self.is_new_conversation: bool = True
        self.is_current_execution_verbose: bool = False

        # Cell limits
        # 3 cells per turn allows multi-step exploration without forcing everything
        # into a single cell. With proper prompting and enforcement, this should be
        # reasonable while still encouraging focused, incremental work.
        self.max_cells = 3
        # Track create_python_cell calls in current conversation
        self.create_python_cell_count = 0

        # Model selection
        self.model = "sonnet"

        # CLI path (for openclaude or other compatible CLIs)
        self.cli_path: str | None = os.environ.get("NOTELLM_CLI_PATH") or None

        # Skill loading
        self.skills_path: str | None = os.environ.get("NOTELLM_SKILLS_PATH") or None
        self.active_skills: list[str] = []  # skills loaded for current session

        # Cost/usage display
        self.show_cost: bool = True

        # Python hooks file
        self.hooks_file: str | None = os.environ.get("NOTELLM_HOOKS_FILE") or None

        # Import tracking
        self.imported_files: list[str] = []

        # Directory permissions
        self.added_directories: list[str] = []

        # MCP configuration
        self.mcp_config_file: str | None = None

        # Cell loading settings
        self.cells_to_load: int = -1  # Default to -1 (load all) for initial %cc
        self.cells_to_load_user_set: bool = False  # Track if explicitly set by user

    def reset_for_new_conversation(self) -> None:
        """Reset settings for a new conversation."""
        self.is_new_conversation = True
        # Reset create_python_cell counter for new conversation
        self.create_python_cell_count = 0
        # For cc_new, default to not loading previous cells (0)
        # But only if user hasn't explicitly set a value
        if not self.cells_to_load_user_set:
            self.cells_to_load = 0

    def handle_cc_options(self, args: Any, cell_watcher: CellWatcher) -> bool:
        """
        Handle all command-line options for the cc magic command.

        Args:
            args: Parsed arguments from argparse
            cell_watcher: Cell watcher instance for execution detection

        Returns:
            True if any option was handled (meaning the command should return early)
        """
        if args.help:
            print(HELP_TEXT)
            return True

        if args.clean is not None:
            self.should_cleanup_prompts = args.clean
            maybe_not = "" if self.should_cleanup_prompts else "not "
            print(CLEANUP_PROMPTS_TEXT.format(maybe_not=maybe_not))
            return True

        # Determine the appropriate message for settings that require a new conversation
        pickup_message = (
            "Will be used in next new conversation."
            if self.is_new_conversation
            else "Use %cc_new to pick up the setting."
        )

        if args.max_cells is not None:
            old_max_cells = self.max_cells
            self.max_cells = args.max_cells
            print(
                f"📝 Set max_cells from {old_max_cells} to {self.max_cells}. {pickup_message}"
            )
            return True

        if args.import_file is not None:
            file_path = Path(args.import_file).expanduser().resolve()

            try:
                with file_path.open() as f:
                    # Try to read first few bytes to check if it's text
                    f.read(1024)

                file_str = str(file_path)
                if file_str not in self.imported_files:
                    self.imported_files.append(file_str)
                    print(f"✅ Added {file_path.name} to import list. {pickup_message}")
                else:
                    print(f"ℹ️ {file_path} is already in the import list.")
            except Exception:
                print(
                    f"❌ Import failed: {file_path.name} does not exist or is not a plaintext file."
                )
            return True

        if args.add_dir is not None:
            dir_path = Path(args.add_dir).expanduser().resolve()

            if not dir_path.exists():
                print(f"❌ Directory not found: {dir_path}")
                return True

            if not dir_path.is_dir():
                print(f"❌ Path is not a directory: {dir_path}")
                return True

            # Add to added directories list if not already there
            dir_str = str(dir_path)
            if dir_str not in self.added_directories:
                self.added_directories.append(dir_str)
                print(
                    f"✅ Added {dir_path} to accessible directories. {pickup_message}"
                )
            else:
                print(f"ℹ️ {dir_path} is already in the accessible directories list.")
            return True

        if args.mcp_config is not None:
            config_path = Path(args.mcp_config).expanduser().resolve()

            # Store the config file path
            config_str = str(config_path)
            self.mcp_config_file = config_str
            print(f"✅ Set MCP config file to {config_path}. {pickup_message}")
            return True

        if args.model is not None:
            self.model = args.model
            print(f"✅ Set model to {self.model}. {pickup_message}")
            return True

        if args.cli_path is not None:
            self.cli_path = args.cli_path
            print(f"✅ Set CLI path to {self.cli_path}. {pickup_message}")
            return True

        if args.skill:
            for skill in args.skill:
                if skill not in self.active_skills:
                    self.active_skills.append(skill)
                    print(f"✅ Added skill '{skill}' to session. {pickup_message}")
                else:
                    print(f"ℹ️  Skill '{skill}' already active.")
            return True

        if args.no_skill:
            for skill in args.no_skill:
                if skill in self.active_skills:
                    self.active_skills.remove(skill)
                    print(f"✅ Removed skill '{skill}' from session.")
                else:
                    print(f"ℹ️  Skill '{skill}' was not active.")
            return True

        if args.no_cost is not None:
            self.show_cost = not args.no_cost
            state = "disabled" if args.no_cost else "enabled"
            print(f"✅ Cost display {state}.")
            return True

        if args.hooks_file is not None:
            self.hooks_file = args.hooks_file
            print(f"✅ Set hooks file to {self.hooks_file}. {pickup_message}")
            return True

        if args.cells_to_load is not None:
            if args.cells_to_load < -1:
                print("❌ Number of cells must be -1 (all), 0 (none), or positive")
                return True
            self.cells_to_load = args.cells_to_load
            self.cells_to_load_user_set = True  # Mark as explicitly set by user
            if args.cells_to_load == 0:
                print(
                    "✅ Disabled loading recent cells when starting new conversations"
                )
            elif args.cells_to_load == -1:
                print(
                    "✅ Will load all available cells when starting new conversations"
                )
            else:
                print(
                    f"✅ Will load up to {args.cells_to_load} recent cell(s) when starting new conversations"
                )
            return True

        # Handle queued execution check
        if cell_watcher.was_execution_probably_queued() and not args.allow_run_all:
            print(QUEUED_EXECUTION_TEXT)
            return True

        # No options were handled
        return False

    def get_claude_code_options_settings(self) -> str | None:
        """Get the settings JSON for ClaudeAgentOptions if needed.

        Returns:
            JSON string with settings or None
        """
        if self.added_directories:
            permissions_dict = {
                "permissions": {"additionalDirectories": self.added_directories}
            }
            return json.dumps(permissions_dict)
        return None

    def get_mcp_servers(self, mcp_server_script: str) -> dict[str, Any]:
        """Get the MCP servers configuration.

        Args:
            mcp_server_script: Path to the local executor MCP server script

        Returns:
            Dictionary of MCP server configurations
        """
        mcp_servers: dict[str, Any] = {}

        # Add the local executor if a script path is provided
        if mcp_server_script:
            mcp_servers["local_executor"] = {
                "command": "python",
                "args": [mcp_server_script],
            }

        # If we have an MCP config file, load servers from it
        if self.mcp_config_file:
            try:
                with Path(self.mcp_config_file).open() as f:
                    config_data = json.load(f)
                    if "mcpServers" in config_data and isinstance(
                        config_data["mcpServers"], dict
                    ):
                        mcp_servers.update(config_data["mcpServers"])
            except json.JSONDecodeError as e:
                print(f"⚠️ Error parsing MCP config file {self.mcp_config_file}: {e}")
            except Exception as e:
                print(f"⚠️ Error loading MCP config file {self.mcp_config_file}: {e}")

        return mcp_servers
