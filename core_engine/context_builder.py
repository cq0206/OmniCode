from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


MAX_AGENTS_CHARS = 12_000
MAX_SKILL_EXCERPT_CHARS = 4_000
MAX_OPTIONAL_SKILLS_IN_DETAIL = 4
MAX_SKILL_SUMMARY_CHARS = 220
MAX_TAPE_EVENTS = 30
MAX_TAPE_CONTENT_CHARS = 280


@dataclass
class SkillDocument:
    name: str
    path: Path
    relative_path: str
    summary: str
    content: str
    score: int
    origin: str


@dataclass
class ContextBundle:
    planner_context: str
    executor_context: str
    metadata: dict[str, Any]


def build_context_bundle(
    workspace: str | Path,
    prompt: str,
    session_events: list[dict[str, Any]],
    *,
    required_skill_names: list[str] | None = None,
) -> ContextBundle:
    workspace_path = Path(workspace).resolve()
    agents_text = _load_agents_text(workspace_path)
    required_names = {name.lower() for name in (required_skill_names or [])}
    skills = _discover_skills(workspace_path, prompt, required_names)
    required_skills = [skill for skill in skills if skill.name.lower() in required_names]
    optional_skills = [
        skill
        for skill in skills
        if skill.name.lower() not in required_names and skill.score > 0
    ][:MAX_OPTIONAL_SKILLS_IN_DETAIL]
    selected_skills = required_skills + optional_skills
    tape_summary = _summarize_tape(session_events)

    planner_sections = [
        _render_workspace_rules_section(agents_text),
        _render_skills_index(skills),
        _render_skill_details(selected_skills),
        _render_tape_summary(tape_summary),
    ]
    executor_sections = [
        _render_workspace_rules_section(agents_text),
        _render_skill_details(selected_skills),
        _render_tape_summary(tape_summary),
    ]

    metadata = {
        "workspace": str(workspace_path),
        "has_agents_md": bool(agents_text),
        "skills_discovered": len(skills),
        "skills_selected": [f"{skill.origin}:{skill.relative_path}" for skill in selected_skills],
        "skills_selected_origins": [skill.origin for skill in selected_skills],
        "tape_events_used": min(len(session_events), MAX_TAPE_EVENTS),
    }

    return ContextBundle(
        planner_context="\n\n".join(section for section in planner_sections if section),
        executor_context="\n\n".join(section for section in executor_sections if section),
        metadata=metadata,
    )


def _load_agents_text(workspace: Path) -> str:
    agents_file = workspace / "AGENTS.md"
    if not agents_file.exists():
        return ""
    text = agents_file.read_text(encoding="utf-8")
    return text[:MAX_AGENTS_CHARS].strip()


def _discover_skills(
    workspace: Path,
    prompt: str,
    required_names: set[str],
) -> list[SkillDocument]:
    discovered: list[SkillDocument] = []

    search_roots = [
        ("workspace", workspace / ".agent" / "skills", workspace),
        ("builtin", Path(__file__).resolve().parent / "builtin_skills", Path(__file__).resolve().parent),
    ]

    for origin, skills_dir, relative_root in search_roots:
        if not skills_dir.exists():
            continue

        for skill_file in sorted(skills_dir.rglob("SKILL.md")):
            raw_content = skill_file.read_text(encoding="utf-8")
            metadata, content = _split_frontmatter(raw_content)
            name = metadata.get("name") or _extract_skill_name(skill_file, content)
            score = _score_skill(prompt, skill_file, name, metadata.get("description", ""), content)
            if name.lower() in required_names:
                score += 10_000

            discovered.append(
                SkillDocument(
                    name=name,
                    path=skill_file,
                    relative_path=str(skill_file.relative_to(relative_root)),
                    summary=metadata.get("description") or _extract_skill_summary(content),
                    content=content,
                    score=score,
                    origin=origin,
                )
            )

    discovered.sort(key=lambda item: (-item.score, item.origin, item.relative_path))
    return discovered


def _extract_skill_name(skill_file: Path, content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return skill_file.parent.name


def _extract_skill_summary(content: str) -> str:
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
        if len(" ".join(lines)) >= MAX_SKILL_SUMMARY_CHARS:
            break
    summary = " ".join(lines)
    return _truncate(summary, MAX_SKILL_SUMMARY_CHARS) or "No summary available."


def _score_skill(
    prompt: str,
    skill_file: Path,
    name: str,
    description: str,
    content: str,
) -> int:
    tokens = _tokenize(prompt)
    if not tokens:
        return 0

    haystacks = {
        "path": str(skill_file).lower(),
        "title": name.lower(),
        "summary": (description or _extract_skill_summary(content)).lower(),
        "content": content[:MAX_SKILL_EXCERPT_CHARS].lower(),
    }

    score = 0
    for token in tokens:
        if token in haystacks["title"]:
            score += 4
        if token in haystacks["path"]:
            score += 3
        if token in haystacks["summary"]:
            score += 2
        if token in haystacks["content"]:
            score += 1
    return score


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_./-]{3,}", text.lower())}


def _split_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        return {}, content

    lines = content.splitlines()
    if len(lines) < 3:
        return {}, content

    metadata: dict[str, str] = {}
    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()

    if closing_index is None:
        return {}, content

    body = "\n".join(lines[closing_index + 1 :]).strip()
    return metadata, body


def _summarize_tape(session_events: list[dict[str, Any]]) -> list[str]:
    recent_events = session_events[-MAX_TAPE_EVENTS:]
    lines: list[str] = []
    for event in recent_events:
        role = event.get("role", "unknown")
        event_type = event.get("type", "unknown")
        target = event.get("target")
        target_suffix = f"::{target}" if target else ""
        content = _truncate(str(event.get("content", "")), MAX_TAPE_CONTENT_CHARS)
        lines.append(f"- [{role}/{event_type}{target_suffix}] {content}")
    return lines


def _render_workspace_rules_section(agents_text: str) -> str:
    if not agents_text:
        return "## Workspace Rules\nNo AGENTS.md file was found in the workspace root."
    return f"## Workspace Rules (AGENTS.md)\n{agents_text}"


def _render_skills_index(skills: list[SkillDocument]) -> str:
    if not skills:
        return "## Skills Index\nNo workspace skills were found under .agent/skills/."

    lines = ["## Skills Index"]
    for skill in skills:
        lines.append(f"- {skill.name} [{skill.origin}:{skill.relative_path}]: {skill.summary}")
    return "\n".join(lines)


def _render_skill_details(skills: list[SkillDocument]) -> str:
    if not skills:
        return "## Relevant Skill Details\nNo workspace skill matched the current prompt closely enough."

    parts = ["## Relevant Skill Details"]
    for skill in skills:
        excerpt = _truncate(skill.content.strip(), MAX_SKILL_EXCERPT_CHARS)
        parts.append(
            "\n".join(
                [
                    f"### {skill.name}",
                    f"Origin: {skill.origin}",
                    f"Path: {skill.relative_path}",
                    f"Summary: {skill.summary}",
                    excerpt,
                ]
            )
        )
    return "\n\n".join(parts)


def _render_tape_summary(lines: list[str]) -> str:
    if not lines:
        return "## Recent Session Tape\nNo previous tape events exist for this session."
    return "## Recent Session Tape\n" + "\n".join(lines)


def _truncate(text: str, limit: int) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: max(0, limit - 3)].rstrip() + "..."
