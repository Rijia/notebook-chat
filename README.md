# `notebook-chat`

**A Jupyter magic extension for running Claude Code inside your notebook — built for data science workflows.**

`notebook-chat` is revised from [`notellm`](https://github.com/prairie-guy/notellm), which adapts Anthropic's `claude-code-jupyter-staging`. It adds the `%cc` magic command so Claude can work *inside* your notebook cells, access your variables and dataframes, execute code, and continue the conversation as you iterate.

```python
%%cc
Load the penguins CSV, compute mean body mass by species and sex,
and plot it as a grouped bar chart using matplotlib
```

Claude creates new cells for you to review. Run `%cc` again (with or without additional instructions) to keep iterating.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Magic Commands](#magic-commands)
- [Skills](#skills)
- [Hooks](#hooks)
- [Environment Variables](#environment-variables)
- [Using Any OpenAI-Compatible Model](#using-any-openai-compatible-model)
- [Attribution](#attribution)

---

## Installation

### Prerequisites

**1. Install Claude Code CLI.**

Default (Anthropic's Claude):
```bash
npm install -g @anthropic-ai/claude-code
export ANTHROPIC_API_KEY=sk-ant-...
```

Or use [openclaude](https://github.com/gitlawb/openclaude) for any OpenAI-compatible model:
```bash
npm install -g @gitlawb/openclaude
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o
```

**2. Install Python dependencies:**
```bash
pip install claude-agent-sdk
```

> Use `pip`, not conda. `claude-agent-sdk` is only on PyPI.

### Install notebook-chat

```bash
git clone https://github.com/Rijia/notebook-chat.git
cd notebook-chat
bash setup.sh
```

To uninstall:
```bash
bash uninstall.sh
```

---

## Quick Start

```python
%load_ext notebook_chat
```

A security warning and confirmation banner will appear on load (Claude can run shell commands and access files). A `.claude/settings.local.json` is created in your project directory with default permissions.

```python
# One-line prompt
%cc Summarize the shape, dtypes, and missing values in df

# Multi-line prompt
%%cc
Fit a logistic regression on X_train and y_train,
evaluate on X_test, and plot the ROC curve
```

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
| `--model <name>` | Model alias (default: `sonnet`) |
| `--cli-path <path>` | Path to CLI binary (e.g. `openclaude`) |
| `--max-cells <n>` | Max cells Claude can create per turn (default: 3) |
| `--cells-to-load <n>` | Cells to include when starting a new conversation (default: 0) |
| `--import <file>` | Add a file to the conversation context |
| `--add-dir <dir>` | Add a directory to Claude's accessible directories |
| `--skill <name>` | Inject a skill into this prompt (repeatable) |
| `--no-skill <name>` | Remove an active session skill |
| `--hooks-file <path>` | Load Python hooks from a file |
| `--no-cost` | Suppress cost/token display for this run |
| `--verbose` / `-v` | Show full tool arguments and error tracebacks |

---

## Skills

Skills are markdown files with domain instructions injected into your prompt as context. They keep your system prompt lean while making expertise available on demand — especially useful for data science tasks.

### Using skills

```python
%cc_skills                                  # list all available skills

%cc --skill ds-eda describe the dataset

%%cc --skill ds-experiment
Analyze the A/B test results in results_df,
check for censoring issues and compute incremental ROI
```

Activate a skill for the whole session:
```python
%cc --skill ds-review          # active for all subsequent %cc calls
%cc --no-skill ds-review       # deactivate
```

### Built-in data science skills

| Skill | What it does |
|-------|-------------|
| `ds-eda` | Comprehensive EDA: distributions, temporal patterns, missing data, actionable findings |
| `ds-experiment` | Full A/B test analysis with censoring audit, incremental ROI, subgroup caution protocol |
| `ds-model` | ML pipeline: time-based splits, baseline, tuning, gains/lift table, business impact |
| `ds-segment` | Customer segmentation: RFM features, elbow + silhouette k-selection, stability check |
| `ds-review` | Code review checklist: censored windows, ROI math, subgroup noise, data leakage |
| `ds-report` | Executive report: plain-English findings, sensitivity ranges, concrete recommendation |

These are installed to `~/.claude/commands/` and available immediately as skills.

### Adding your own skills

Create `~/.claude/skills/my-skill.md`:

```markdown
---
description: My domain expertise
---

# My Skill

Instructions for Claude when this skill is active...
```

Then use with `%cc --skill my-skill your prompt`.

Skills are also discovered at:
- `~/.claude/skills/<name>/SKILL.md`
- `~/.claude/commands/<name>.md` (Claude Code slash commands double as skills)
- `./skills/<name>.md` (project-local)

---

## Hooks

Hooks run Python callbacks at lifecycle events — useful for logging tool calls, cost alerts, custom approval flows, or audit trails on model decisions.

### Defining hooks

Create `~/.claude/notebook_chat_hooks.py`:

```python
from claude_agent_sdk import HookMatcher

async def log_tool(input, event_name, ctx):
    print(f"[hook] {input.get('tool_name')}", flush=True)
    return {}

async def on_stop(input, event_name, ctx):
    print("[hook] session complete", flush=True)
    return {}

HOOKS = {
    "PreToolUse": [HookMatcher(hooks=[log_tool])],
    "Stop":       [HookMatcher(hooks=[on_stop])],
}
```

This file is loaded automatically on every `%cc` call. Use a different file:
```python
%cc --hooks-file /path/to/my_hooks.py your prompt
```

Or set once for the session:
```bash
export NOTEBOOK_CHAT_HOOKS_FILE=/path/to/my_hooks.py
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

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | API key for Claude (Anthropic) | required |
| `NOTEBOOK_CHAT_CLI_PATH` | Path to CLI binary | `claude` in PATH |
| `NOTEBOOK_CHAT_SKILLS_PATH` | Extra directory to search for skills | — |
| `NOTEBOOK_CHAT_HOOKS_FILE` | Path to Python hooks file | `~/.claude/notebook_chat_hooks.py` |
| `CLAUDE_CODE_USE_OPENAI` | Enable OpenAI-compatible mode (openclaude) | — |
| `OPENAI_API_KEY` | API key for OpenAI-compatible provider | — |
| `OPENAI_MODEL` | Model name for OpenAI-compatible provider | — |
| `OPENAI_BASE_URL` | Base URL for OpenAI-compatible provider | — |

---

## Using Any OpenAI-Compatible Model

notebook-chat works with [openclaude](https://github.com/gitlawb/openclaude), a drop-in CLI that routes Claude Code to any OpenAI-compatible API.

**From the terminal (before launching Jupyter):**
```bash
export NOTEBOOK_CHAT_CLI_PATH=$(which openclaude)
export CLAUDE_CODE_USE_OPENAI=1
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o
jupyter notebook
```

**Supported providers:**

| Provider | `OPENAI_MODEL` example | `OPENAI_BASE_URL` |
|----------|------------------------|-------------------|
| OpenAI | `gpt-4o` | *(default)* |
| DeepSeek | `deepseek-chat` | `https://api.deepseek.com/v1` |
| Gemini | `gemini-2.0-flash` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| Ollama (local) | `llama3.2` | `http://localhost:11434/v1` |

---

## Attribution

`notebook-chat` is revised from [`notellm`](https://github.com/prairie-guy/notellm) by prairie-guy, which is itself adapted from `claude-code-jupyter-staging` by Anthropic. Released under the MIT License — see [LICENSE](LICENSE) for details.
