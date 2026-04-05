# `notellm`

**Lightweight Jupyter magic extension for Claude Code integration — with support for any OpenAI-compatible model, skill injection, Python hooks, and cost tracking.**

`notellm` provides the `%cc` magic command that lets Claude work *inside* your notebook — executing code, accessing your variables, searching the web, and creating new cells:

```python
%%cc
Import the penguin dataset and plot body mass by species using a violin chart
```

This differs from sidebar-based chat tools. With `notellm`, code development happens iteratively from **within** notebook cells. Claude sees your notebook state, creates new cells for you to review, and continues the conversation when you run `%cc` again.

![notellm demo](docs/demo.png)

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Magic Commands](#magic-commands)
- [Using Any Model (OpenAI-compatible)](#using-any-model-openai-compatible)
- [Skills](#skills)
- [Hooks](#hooks)
- [Cost Tracking](#cost-tracking)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Attribution](#attribution)

---

## Installation

### Prerequisites

**1. Install a Claude Code CLI.**

Default (Anthropic's Claude):
```bash
npm install -g @anthropic-ai/claude-code
export ANTHROPIC_API_KEY=sk-ant-...
```

Or use [openclaude](https://github.com/gitlawb/openclaude) for any OpenAI-compatible model:
```bash
npm install -g @gitlawb/openclaude
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o   # or deepseek-chat, gemini-2.0-flash, etc.
```

**2. Install Python dependencies:**
```bash
pip install claude-agent-sdk
```

> Use `pip`, not conda. `claude-agent-sdk` is only on PyPI.

### Install notellm

```bash
git clone https://github.com/prairie-guy/notellm.git
cd notellm
bash setup.sh
```

`setup.sh` copies `notellm_magic/` to your Python user site-packages directory.

To uninstall:
```bash
bash uninstall.sh
```

---

## Quick Start

```python
# In a Jupyter notebook cell:
%load_ext notellm_magic
```

On load you'll see a security warning (Claude can run shell commands and access files) and a confirmation banner. A `.claude/settings.local.json` file is created in your project directory with default permissions.

```python
# One-line prompt
%cc Create a hello world function

# Multi-line prompt
%%cc
Load the penguins CSV, compute mean body mass by species and sex,
and plot it as a grouped bar chart using matplotlib
```

Claude creates new cells for you to review. Run `%cc` (with or without additional instructions) to continue the conversation after executing those cells.

Start a fresh conversation:
```python
%cc_new  # or %ccn
```

---

## Magic Commands

### Core

| Command | Description |
|---------|-------------|
| `%cc <prompt>` | Continue conversation (one-line) |
| `%%cc <prompt>` | Continue conversation (multi-line cell) |
| `%cc_new <prompt>` / `%ccn` | Start a fresh conversation |
| `%cc_skills` | List available skills |
| `%cc --help` | Show all options |

### Options

| Flag | Description |
|------|-------------|
| `--model <name>` | Model alias to use (default: `sonnet`) |
| `--cli-path <path>` | Path to CLI binary (e.g. `openclaude`) |
| `--max-cells <n>` | Max cells Claude can create per turn (default: 3) |
| `--cells-to-load <n>` | Cells to load into a new conversation (default: 0) |
| `--import <file>` | Add a file to the conversation context |
| `--add-dir <dir>` | Add a directory to Claude's accessible directories |
| `--mcp-config <file>` | Path to a `.mcp.json` MCP server config file |
| `--clean` / `--no-clean` | Replace/keep prompt cells after Claude responds |
| `--skill <name>` | Inject a skill into this prompt (repeatable) |
| `--no-skill <name>` | Remove an active session skill |
| `--no-cost` | Suppress cost/token display for this run |
| `--hooks-file <path>` | Load Python hooks from a file |
| `--verbose` / `-v` | Show full tool arguments and error tracebacks |

---

## Using Any OpenAI-Compatible Model

notellm works with [openclaude](https://github.com/gitlawb/openclaude), a drop-in CLI that routes Claude Code to any OpenAI-compatible API.

**From the terminal (before launching Jupyter):**
```bash
export NOTELLM_CLI_PATH=$(which openclaude)
export CLAUDE_CODE_USE_OPENAI=1
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o
jupyter notebook
```

**From inside the notebook:**
```python
import os
os.environ["CLAUDE_CODE_USE_OPENAI"] = "1"
os.environ["OPENAI_API_KEY"] = "sk-..."
os.environ["OPENAI_MODEL"] = "gpt-4o"

%cc --cli-path /usr/local/bin/openclaude your prompt here
```

**Supported providers** (anything with an OpenAI-compatible API):

| Provider | `OPENAI_MODEL` example | `OPENAI_BASE_URL` |
|----------|------------------------|-------------------|
| OpenAI | `gpt-4o` | *(default)* |
| DeepSeek | `deepseek-chat` | `https://api.deepseek.com/v1` |
| Gemini | `gemini-2.0-flash` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| Ollama (local) | `llama3.2` | `http://localhost:11434/v1` |
| Any other | model name | provider's base URL |

---

## Skills

Skills are markdown files containing domain knowledge or structured instructions that get injected into your prompt as context. This keeps your system prompt lean while making expertise available on demand.

### Using skills

```python
%cc_skills                             # list all available skills

%cc --skill ds-review review this notebook

%%cc --skill ds-experiment --skill pdf
Analyze the attached PDF experiment report for statistical issues
```

Skills can also be activated for a whole session:
```python
%cc --skill ds-review          # now active for all subsequent %cc calls
%cc --no-skill ds-review       # deactivate
```

### Where skills live

notellm searches in this order:
1. `~/.claude/skills/<name>/SKILL.md` — subdirectory format
2. `~/.claude/skills/<name>.md` — flat file format
3. `~/.claude/commands/<name>.md` — Claude Code slash commands double as skills
4. `./skills/<name>/SKILL.md` and `./skills/<name>.md` — project-local

### Built-in skills (from `~/.claude/commands/`)

| Skill | What it does |
|-------|-------------|
| `ds-eda` | Comprehensive EDA: distributions, temporal patterns, missing data, actionable findings |
| `ds-experiment` | Full A/B test analysis with censoring audit, incremental ROI, subgroup caution protocol |
| `ds-model` | ML pipeline: time-based splits, baseline, tuning, gains/lift table, business impact |
| `ds-segment` | Customer segmentation: RFM features, elbow + silhouette k-selection, stability check |
| `ds-review` | Code review checklist: censored windows, ROI math, subgroup noise, data leakage |
| `ds-report` | Executive report: plain-English findings, sensitivity ranges, concrete recommendation |

These are installed to `~/.claude/commands/` and immediately available as skills.

### Adding your own skills

Create `~/.claude/skills/my-skill.md` (or `~/.claude/skills/my-skill/SKILL.md`):

```markdown
---
description: My domain expertise
---

# My Skill

Instructions for Claude when this skill is active...
```

Then `%cc --skill my-skill do something`.

---

## Hooks

Hooks let you run Python callbacks at lifecycle events (before/after tool calls, on session stop, etc.). This enables logging, cost alerting, custom approval flows, or any side effect you need.

### Defining hooks

Create `~/.claude/notellm_hooks.py`:

```python
from claude_agent_sdk import HookMatcher

async def log_tool(input, event_name, ctx):
    print(f"[hook] {input.get('tool_name')}", flush=True)
    return {}

async def on_stop(input, event_name, ctx):
    # Runs when the Claude session ends
    print("[hook] session complete", flush=True)
    return {}

HOOKS = {
    "PreToolUse":  [HookMatcher(hooks=[log_tool])],
    "Stop":        [HookMatcher(hooks=[on_stop])],
}
```

notellm loads this file automatically on every `%cc` call.

To use a different file:
```python
%cc --hooks-file /path/to/my_hooks.py your prompt
```

Or set once for the session:
```bash
export NOTELLM_HOOKS_FILE=/path/to/my_hooks.py
```

### Available hook events

| Event | Fires when |
|-------|-----------|
| `PreToolUse` | Before any tool call |
| `PostToolUse` | After a successful tool call |
| `PostToolUseFailure` | After a failed tool call |
| `UserPromptSubmit` | When the user submits a prompt |
| `Stop` | When the Claude session ends |
| `SubagentStop` | When a subagent finishes |
| `PreCompact` | Before context compaction |
| `Notification` | On Claude notifications |
| `SubagentStart` | When a subagent starts |
| `PermissionRequest` | When Claude requests a permission |

Each hook receives `(input: HookInput, event_name: str, ctx: HookContext)` and returns a dict.

> Shell-command hooks defined in `~/.claude/settings.json` also work automatically via the Claude Code CLI's own hook system.

---

## Cost Tracking

After every `%cc` run, notellm displays a compact usage summary:

```
💰 $0.0034  ↑1,204 ↓387  cache↩2,100  3 turns  4.2s
```

- `💰` — total cost in USD
- `↑` / `↓` — input / output tokens
- `cache↩` — cache read tokens (cheaper)
- turns — number of agentic turns
- seconds — wall-clock time

Suppress for one call: `%cc --no-cost your prompt`

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | API key for Claude (Anthropic) | required |
| `NOTELLM_CLI_PATH` | Path to CLI binary | `claude` in PATH |
| `NOTELLM_SKILLS_PATH` | Extra directory to search for skills | — |
| `NOTELLM_HOOKS_FILE` | Path to Python hooks file | `~/.claude/notellm_hooks.py` |
| `CLAUDE_CODE_USE_OPENAI` | Enable OpenAI-compatible mode (openclaude) | — |
| `OPENAI_API_KEY` | API key for OpenAI-compatible provider | — |
| `OPENAI_MODEL` | Model name for OpenAI-compatible provider | — |
| `OPENAI_BASE_URL` | Base URL for OpenAI-compatible provider | — |

---

## Project Structure

```
notellm/
├── notellm_magic/
│   ├── __init__.py              # Extension loader + permissions setup
│   └── cc_jupyter/
│       ├── magics.py            # %cc, %cc_new, %cc_skills magic commands
│       ├── claude_client.py     # Asyncio-based SDK client with cost display
│       ├── config_manager.py    # All session configuration
│       ├── skill_loader.py      # Skill discovery and injection
│       ├── hooks_loader.py      # Python hooks file loader
│       ├── jupyter_integration.py  # Cell creation and queue management
│       ├── prompt_builder.py    # Prompt construction with notebook context
│       ├── history_manager.py   # Shell output and cell history
│       ├── variable_tracker.py  # Notebook variable inspection
│       ├── capture_helpers.py   # Image capture from cell output
│       ├── cell_watcher.py      # Detects queued cell execution
│       └── constants.py
├── archive/                     # Pristine upstream cc_jupyter (reference)
├── build/
│   └── build_notellm_magic.sh  # Rebuild from archive
├── docs/
│   └── demo.ipynb
├── setup.sh
├── uninstall.sh
└── LICENSE
```

---

## Patches vs. Upstream

notellm is a fork of `claude-code-jupyter-staging` by Anthropic. Changes from the original:

| Area | Change |
|------|--------|
| Async runtime | Replaced `trio` throughout with `asyncio` (SDK requires asyncio) |
| Event loop | Use `loop.run_until_complete()` instead of `asyncio.run()` to avoid `parent_header` ContextVar conflicts with ipykernel |
| Markdown display | Catch `LookupError` from Jupyter's ZMQ `parent_header` ContextVar and fall back to `print()` |
| Model support | `--cli-path` + `NOTELLM_CLI_PATH` for openclaude and any OpenAI-compatible CLI |
| Skills | `--skill` flag, `%cc_skills` magic, `SkillLoader` searching `~/.claude/skills/` and `~/.claude/commands/` |
| Hooks | `--hooks-file` flag, `NOTELLM_HOOKS_FILE` env, Python callable hooks via `ClaudeAgentOptions.hooks` |
| Cost display | Extracts `total_cost_usd`, token counts, turn count, and duration from `ResultMessage` |

---

## Attribution

Adapted from `claude-code-jupyter-staging` by Anthropic, released under the MIT License.

See [LICENSE](LICENSE) for details.
