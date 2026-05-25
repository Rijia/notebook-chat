"""
Cell-diff tracking for notebook-chat — the capture signal for the instinct system.

When the user runs an *edited* version of a cell Claude generated, that edit is the
strongest "correction" signal there is: the user looked at Claude's code and changed
it before trusting it. This module detects those edits so they can be reviewed and,
later, distilled into "instincts" (lightweight learned conventions).

Detection is content-based, not marker-based. Claude-generated cells briefly carry a
`# Claude cell [<id>]` marker, but `adjust_cell_queue_markers` strips it before the
cell is handed to the user, so by execution time there is nothing to match on. Instead
we remember each code block Claude generates and, when a cell runs, compare it against
the outstanding ones:

  * exact match            -> ran as-is, no capture
  * high similarity, edited -> user modified Claude's cell  => CAPTURE
  * low similarity          -> the user's own unrelated cell, ignored

This is capture-only. Detected edits are appended to
`.claude/notebook_chat_instinct_captures.jsonl` for review. Nothing here changes
Claude's behavior yet — per the design, we look at what gets captured before wiring
any of it back into prompts.
"""

from __future__ import annotations

import difflib
import json
import time
from pathlib import Path
from typing import Any

# Below this SequenceMatcher ratio, an executed cell is treated as the user's own
# unrelated work rather than an edit of a Claude-generated cell.
EDIT_SIMILARITY_THRESHOLD = 0.6

# How many outstanding (un-consumed) generated cells to keep around. Bounds memory in
# long sessions where Claude cells are generated but never run.
_MAX_PENDING = 20

_DEFAULT_CAPTURE_FILE = ".claude/notebook_chat_instinct_captures.jsonl"
_MARKER_PREFIX = "# Claude cell ["


class CellDiffTracker:
    """Detects user edits to Claude-generated cells (capture-only)."""

    def __init__(self, capture_path: str | None = None) -> None:
        # Outstanding generated cells not yet matched to an execution.
        self._pending: list[tuple[str, str]] = []  # (marker_id, original_code)
        self._capture_path = (
            Path(capture_path)
            if capture_path is not None
            else Path.cwd() / _DEFAULT_CAPTURE_FILE
        )
        # In-memory log of captures detected this session.
        self.captures: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_generated(self, marker_id: str, code: str) -> None:
        """Remember a code block Claude generated, keyed by its cell marker id."""
        if not code or not code.strip():
            return
        self._pending.append((marker_id or "", code))
        if len(self._pending) > _MAX_PENDING:
            self._pending = self._pending[-_MAX_PENDING:]

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def inspect_execution(self, executed_source: str) -> dict[str, Any] | None:
        """Compare a just-executed cell against outstanding Claude cells.

        Returns a capture dict if the cell looks like an edited Claude cell, else None.
        Matching cells (whether run as-is or edited) are consumed so a later cell can't
        re-match them.
        """
        if not executed_source or not executed_source.strip():
            return None
        if not self._pending:
            return None

        ran_norm = self._normalize(self._strip_marker(executed_source))

        best_index: int | None = None
        best_ratio = 0.0
        for i, (_marker_id, original) in enumerate(self._pending):
            ratio = difflib.SequenceMatcher(
                None, self._normalize(original), ran_norm
            ).ratio()
            if ratio > best_ratio:
                best_index, best_ratio = i, ratio

        if best_index is None:
            return None

        marker_id, original = self._pending[best_index]

        # Ran exactly as Claude wrote it: consume, no capture.
        if self._normalize(original) == ran_norm:
            self._pending.pop(best_index)
            return None

        # Not similar enough to be an edit of this cell — the user's own cell.
        if best_ratio < EDIT_SIMILARITY_THRESHOLD:
            return None

        ran_code = self._strip_marker(executed_source)
        capture = {
            "marker_id": marker_id,
            "timestamp": time.time(),
            "similarity": round(best_ratio, 3),
            "original": original,
            "edited": ran_code,
            "diff": self._unified_diff(original, ran_code),
        }
        self._pending.pop(best_index)
        self.captures.append(capture)
        self._persist(capture)
        return capture

    # ------------------------------------------------------------------
    # Persistence / review
    # ------------------------------------------------------------------

    def load_captures(self) -> list[dict[str, Any]]:
        """Read all persisted captures (session-independent) for review."""
        if not self._capture_path.exists():
            return []
        out: list[dict[str, Any]] = []
        try:
            with self._capture_path.open() as f:
                for line in f:
                    line = line.strip()
                    if line:
                        out.append(json.loads(line))
        except Exception:
            pass
        return out

    def _persist(self, capture: dict[str, Any]) -> None:
        # Best-effort: a failure to log must never disrupt the notebook.
        try:
            self._capture_path.parent.mkdir(parents=True, exist_ok=True)
            with self._capture_path.open("a") as f:
                f.write(json.dumps(capture) + "\n")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_marker(source: str) -> str:
        """Drop a leading `# Claude cell [...]` marker line if one survived."""
        lines = source.splitlines()
        if lines and lines[0].startswith(_MARKER_PREFIX):
            return "\n".join(lines[1:])
        return source

    @staticmethod
    def _normalize(code: str) -> str:
        """Normalize for comparison: strip trailing whitespace and blank edges."""
        return "\n".join(line.rstrip() for line in code.strip().splitlines())

    @staticmethod
    def _unified_diff(original: str, edited: str) -> str:
        return "\n".join(
            difflib.unified_diff(
                original.splitlines(),
                edited.splitlines(),
                fromfile="claude",
                tofile="user",
                lineterm="",
            )
        )
