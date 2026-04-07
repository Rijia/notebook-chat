"""
notellm IPython Extension

Fork of claude-code-jupyter-staging (MIT License, Anthropic)
Provides %cc magic for Claude Code integration in Jupyter notebooks.
"""

from pathlib import Path
import json

DEFAULT_PERMISSIONS = {
    "permissions": {
        "allow": [
            "Bash",
            "Glob",
            "Grep",
            "Read",
            "Edit",
            "Write",
            "WebSearch",
            "WebFetch"
        ]
    }
}


def _ensure_claude_settings():
    """Create .claude/settings.local.json if not present in cwd."""
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"
    settings_file = claude_dir / "settings.local.json"

    if not settings_file.exists():
        claude_dir.mkdir(exist_ok=True)
        settings_file.write_text(json.dumps(DEFAULT_PERMISSIONS, indent=2))
        print(f"Created {settings_file.relative_to(cwd)}")
        return True
    return False


def load_ipython_extension(ipython):
    """Load the cc_jupyter extension."""
    # Create settings file first if needed
    created = _ensure_claude_settings()

    # Show security warning
    print("")
    print("\033[1;31m" + "=" * 80 + "\033[0m")
    print("\033[1;31mWARNING: Claude has permissions for Bash, Read, Write, Edit, WebSearch, WebFetch\033[0m")
    print("")
    print("  Claude can execute shell commands, read/write/edit files, and access the web.")
    print("  Only use in trusted environments.")
    print("")
    if created:
        print("  Created .claude/settings.local.json with default permissions.")
    print("  Consider removing .claude/settings.local.json when done.")
    print("\033[1;31m" + "=" * 80 + "\033[0m")
    print("")

    from .cc_jupyter import load_ipython_extension as load_cc
    load_cc(ipython)

    # Disable Python syntax highlighting for %cc / %%cc magic cells.
    # Classic Notebook: register the magic prefixes as plain-text mode.
    # JupyterLab: inject a MutationObserver that strips CodeMirror colour
    # classes from cells whose content starts with %%cc or %cc.
    try:
        from IPython.display import display, Javascript
        display(Javascript("""
(function() {
  // ── Classic Jupyter Notebook ──────────────────────────────────────────────
  if (typeof IPython !== 'undefined' && IPython.CodeCell) {
    var modes = IPython.CodeCell.options_default.highlight_modes;
    var plain = { reg: [/^%%cc/, /^%cc/] };
    modes['magic_notellm'] = plain;
    // Re-apply to any already-rendered cells
    Jupyter.notebook.get_cells().forEach(function(cell) {
      if (cell.cell_type === 'code') { cell.auto_highlight(); }
    });
  }

  // ── JupyterLab (CodeMirror 6) ─────────────────────────────────────────────
  function stripHighlight(node) {
    if (!(node instanceof Element)) return;
    // Find the editor content element
    var editors = node.querySelectorAll
      ? node.querySelectorAll('.cm-content, .jp-CodeMirrorEditor')
      : [];
    editors.forEach(function(editor) {
      var text = editor.innerText || editor.textContent || '';
      if (/^%%?cc(\\b|\\s|$)/.test(text.trimStart())) {
        // Override all syntax-coloured spans to inherit the default colour
        editor.querySelectorAll('span[class*="cm-"]').forEach(function(span) {
          span.style.color = 'inherit';
        });
      }
    });
  }

  // Observe DOM mutations so newly typed / run cells are also handled
  if (typeof MutationObserver !== 'undefined') {
    var observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(m) {
        m.addedNodes.forEach(stripHighlight);
        if (m.type === 'characterData' && m.target.parentElement) {
          stripHighlight(
            m.target.parentElement.closest('.jp-Cell') ||
            m.target.parentElement
          );
        }
      });
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true
    });

    // Also run once on all existing cells
    document.querySelectorAll('.jp-Cell, .cell').forEach(stripHighlight);
  }
})();
"""))
    except Exception:
        pass  # Non-fatal: highlighting fix is cosmetic only


def unload_ipython_extension(ipython):
    """Unload the cc_jupyter extension."""
    try:
        from .cc_jupyter import unload_ipython_extension as unload_cc
        unload_cc(ipython)
    except (ImportError, AttributeError):
        pass
