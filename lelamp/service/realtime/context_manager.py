"""Realtime context manager — builds instructions from lamp identity, skills, and memory."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import lelamp.config as app_config
from lelamp.service.realtime.constants import RESOURCES_DIR

logger = logging.getLogger(__name__)


class RealtimeContextManager:
    """Builds rich instructions for the realtime voice agent from lamp context."""

    DEFAULT_PROMPT_PATH: Path = RESOURCES_DIR / "system_prompt.md"

    # Regex to extract YAML frontmatter from SKILL.md
    FRONTMATTER_RE: re.Pattern[str] = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
    NAME_RE: re.Pattern[str] = re.compile(r"^name:\s*(.+)$", re.MULTILINE)
    DESC_RE: re.Pattern[str] = re.compile(r"^description:\s*(.+)$", re.MULTILINE)

    def __init__(
        self,
        workspace_dir: str = app_config.REALTIME_WORKSPACE_DIR,
        realtime_memory_path: str = app_config.REALTIME_MEMORY_PATH,
        language: Optional[str] = None,
        max_memory_entries: int = app_config.REALTIME_MAX_MEMORY_ENTRIES,
        trim_keep: int = app_config.REALTIME_MEMORY_TRIM_KEEP,
        lamp_memory_count: int = app_config.REALTIME_LAMP_MEMORY_COUNT,
        realtime_memory_count: int = app_config.REALTIME_MEMORY_COUNT,
    ) -> None:
        self._workspace: Path = Path(workspace_dir)
        self._realtime_memory_path: Path = Path(realtime_memory_path)
        self._language: str = language or "English"
        self._max_memory_entries: int = max_memory_entries
        self._trim_keep: int = trim_keep
        self._lamp_memory_count: int = lamp_memory_count
        self._realtime_memory_count: int = realtime_memory_count

    # --- Public API ---

    def build_instructions(self) -> str:
        """Build the full instruction string from all context sources."""
        sections: list[str] = []

        # System prompt
        prompt: str = self._load_system_prompt()
        if prompt:
            sections.append(prompt)

        # Lamp identity
        identity: str = self._load_lamp_identity()
        if identity:
            sections.append(f"# LAMP IDENTITY\n\n{identity}")

        # Skills catalog
        catalog: str = self._load_skills_catalog()
        if catalog:
            sections.append(f"# SKILLS CATALOG\n\n{catalog}")

        # Lamp memory
        lamp_mem: str = self._load_lamp_memory()
        if lamp_mem:
            sections.append(f"# LAMP MEMORY\n\n{lamp_mem}")

        # Realtime memory
        rt_mem: str = self._load_realtime_memory()
        if rt_mem:
            sections.append(f"# REALTIME MEMORY\n\n{rt_mem}")

        return "\n\n".join(sections)

    def add_turn(self, user_text: str, agent_text: str) -> None:
        """Save a conversation turn to the realtime memory file."""
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "user": user_text,
            "agent": agent_text,
        }
        try:
            with open(self._realtime_memory_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._trim_memory_if_needed()
        except Exception as e:
            logger.warning("Failed to save realtime memory: %s", e)

    # --- Private loaders ---

    def _load_system_prompt(self) -> str:
        """Load system_prompt.md with {language} placeholder resolved."""
        try:
            template: str = self.DEFAULT_PROMPT_PATH.read_text(encoding="utf-8").strip()
            return template.replace("{language}", self._language)
        except FileNotFoundError:
            return ""

    def _load_lamp_identity(self) -> str:
        """Load SOUL.md and IDENTITY.md from the workspace."""
        parts: list[str] = []
        for filename in ("SOUL.md", "IDENTITY.md"):
            path: Path = self._workspace / filename
            try:
                content: str = path.read_text(encoding="utf-8").strip()
                if content:
                    parts.append(content)
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.warning("Failed to read %s: %s", path, e)
        return "\n\n".join(parts)

    def _load_skills_catalog(self) -> str:
        """Parse SKILL.md frontmatter from all skills, return a markdown table."""
        skills_dir: Path = self._workspace / "skills"
        if not skills_dir.is_dir():
            return ""

        rows: list[tuple[str, str]] = []
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            try:
                text: str = skill_md.read_text(encoding="utf-8")
                fm_match = self.FRONTMATTER_RE.match(text)
                if not fm_match:
                    continue
                frontmatter: str = fm_match.group(1)
                name_match = self.NAME_RE.search(frontmatter)
                desc_match = self.DESC_RE.search(frontmatter)
                name: str = (
                    name_match.group(1).strip() if name_match else skill_md.parent.name
                )
                desc: str = desc_match.group(1).strip() if desc_match else ""
                if name:
                    rows.append((name, desc))
            except Exception as e:
                logger.warning("Failed to parse %s: %s", skill_md, e)

        if not rows:
            return ""

        lines: list[str] = ["| Skill | Description |", "|-------|-------------|"]
        for name, desc in rows:
            lines.append(f"| {name} | {desc} |")
        return "\n".join(lines)

    def _load_lamp_memory(self) -> str:
        """Load the latest N entries from workspace/memory/*.md."""
        memory_dir: Path = self._workspace / "memory"
        if not memory_dir.is_dir():
            return ""

        md_files: list[Path] = sorted(memory_dir.glob("*.md"), reverse=True)
        selected: list[Path] = md_files[: self._lamp_memory_count]

        parts: list[str] = []
        for md_file in selected:
            try:
                content: str = md_file.read_text(encoding="utf-8").strip()
                if content:
                    parts.append(f"## {md_file.stem}\n\n{content}")
            except Exception as e:
                logger.warning("Failed to read memory %s: %s", md_file, e)
        return "\n\n".join(parts)

    def _load_realtime_memory(self) -> str:
        """Load the latest N entries from the realtime memory JSONL file."""
        if not self._realtime_memory_path.exists():
            return ""

        try:
            lines: list[str] = (
                self._realtime_memory_path.read_text(encoding="utf-8")
                .strip()
                .splitlines()
            )
        except Exception as e:
            logger.warning("Failed to read realtime memory: %s", e)
            return ""

        recent: list[str] = lines[-self._realtime_memory_count :]
        parts: list[str] = []
        for line in recent:
            try:
                entry: dict[str, Any] = json.loads(line)
                ts: str = entry.get("ts", "")
                user: str = entry.get("user", "")
                agent: str = entry.get("agent", "")
                parts.append(f"[{ts}] User: {user} | Agent: {agent}")
            except (json.JSONDecodeError, KeyError):
                continue
        return "\n".join(parts)

    def _trim_memory_if_needed(self) -> None:
        """If realtime memory exceeds max entries, keep only the most recent half."""
        try:
            lines: list[str] = (
                self._realtime_memory_path.read_text(encoding="utf-8")
                .strip()
                .splitlines()
            )
            if len(lines) <= self._max_memory_entries:
                return
            kept: list[str] = lines[-self._trim_keep :]
            self._realtime_memory_path.write_text(
                "\n".join(kept) + "\n", encoding="utf-8"
            )
            logger.info(
                "Trimmed realtime memory: %d → %d entries",
                len(lines),
                len(kept),
            )
        except Exception as e:
            logger.warning("Failed to trim realtime memory: %s", e)
