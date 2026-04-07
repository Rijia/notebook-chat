"""
Skill loading for notellm - based on the s05_skill_loading pattern from
learn-claude-code. Skills are on-demand knowledge files injected into the
agent's context rather than bloating the system prompt.

Search order:
  1. ~/.claude/skills/{name}/SKILL.md  (standard skill directories)
  2. ~/.claude/skills/{name}.md        (flat skill files)
  3. ~/.claude/commands/{name}.md      (slash commands double as skills)
  4. {cwd}/skills/{name}/SKILL.md
  5. {cwd}/skills/{name}.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class SkillLoader:
    """Loads skill files by name from known skill directories."""

    def __init__(self, extra_path: str | None = None) -> None:
        base = Path.home() / ".claude"
        cwd_skills = Path.cwd() / "skills"
        self._search_roots: list[tuple[Path, bool]] = [
            # (directory, is_commands_dir)
            (base / "skills", False),
            (base / "commands", True),   # commands/*.md can be used as skills
            (cwd_skills, False),
        ]
        if extra_path:
            self._search_roots.insert(0, (Path(extra_path).expanduser(), False))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_skills(self) -> list[dict[str, str]]:
        """Return all discoverable skills with name, description, path."""
        skills: list[dict[str, str]] = []
        seen: set[str] = set()

        for root, is_commands in self._search_roots:
            if not root.exists():
                continue

            if is_commands:
                # Flat *.md files in commands dir
                for f in sorted(root.glob("*.md")):
                    name = f.stem
                    if name not in seen:
                        seen.add(name)
                        skills.append({
                            "name": name,
                            "description": self._first_line(f),
                            "path": str(f),
                            "source": "commands",
                        })
            else:
                # Subdirectory format: skills/{name}/SKILL.md
                for d in sorted(root.iterdir()):
                    if d.is_dir():
                        skill_file = d / "SKILL.md"
                        if skill_file.exists() and d.name not in seen:
                            seen.add(d.name)
                            skills.append({
                                "name": d.name,
                                "description": self._parse_description(skill_file),
                                "path": str(skill_file),
                                "source": "skills",
                            })
                # Flat format: skills/{name}.md
                for f in sorted(root.glob("*.md")):
                    name = f.stem
                    if name not in seen:
                        seen.add(name)
                        skills.append({
                            "name": name,
                            "description": self._first_line(f),
                            "path": str(f),
                            "source": "skills",
                        })

        return skills

    def load(self, name: str) -> str | None:
        """Load skill content by name. Returns None if not found."""
        for root, is_commands in self._search_roots:
            if not root.exists():
                continue

            candidates = [
                root / name / "SKILL.md",
                root / f"{name}.md",
            ]
            for path in candidates:
                if path.exists():
                    return path.read_text()

        return None

    def inject(self, names: list[str], prompt: str) -> str:
        """Prepend named skills into a prompt as XML-tagged context blocks."""
        if not names:
            return prompt

        blocks: list[str] = []
        missing: list[str] = []

        for name in names:
            content = self.load(name)
            if content is None:
                missing.append(name)
            else:
                blocks.append(f"<skill name=\"{name}\">\n{content.strip()}\n</skill>")

        if missing:
            print(f"⚠️  Skills not found: {', '.join(missing)}", flush=True)

        if not blocks:
            return prompt

        skill_section = "\n\n".join(blocks)
        return f"{skill_section}\n\n{prompt}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _first_line(self, path: Path) -> str:
        """Return the first non-empty, non-frontmatter line as description."""
        try:
            content = path.read_text()
            in_frontmatter = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped == "---":
                    in_frontmatter = not in_frontmatter
                    continue
                if in_frontmatter:
                    continue
                if stripped.startswith("#"):
                    return stripped.lstrip("#").strip()
                if stripped:
                    return stripped[:120]
        except Exception:
            pass
        return ""

    def _parse_description(self, path: Path) -> str:
        """Parse description from YAML frontmatter or first heading."""
        try:
            content = path.read_text()
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    for line in content[3:end].splitlines():
                        if line.lower().startswith("description:"):
                            return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return self._first_line(path)
