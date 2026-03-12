from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from context_builder import ContextBundle


@dataclass
class ArtifactRecord:
    path: Path
    content: str
    created: bool


def ensure_design_artifact(
    *,
    workspace: str | Path,
    session_id: str,
    prompt: str,
    context_bundle: ContextBundle,
    resume: bool,
) -> ArtifactRecord:
    artifacts_dir = _artifact_root(workspace) / "specs"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / f"{_today_prefix()}--{session_id}--design.md"

    if resume and path.exists():
        return ArtifactRecord(path=path, content=path.read_text(encoding="utf-8"), created=False)

    content = _render_design_document(
        session_id=session_id,
        prompt=prompt,
        context_bundle=context_bundle,
    )
    path.write_text(content, encoding="utf-8")
    return ArtifactRecord(path=path, content=content, created=True)


def ensure_plan_artifact(
    *,
    workspace: str | Path,
    session_id: str,
    prompt: str,
    context_bundle: ContextBundle,
    design_artifact: ArtifactRecord,
    task_plan: dict[str, Any],
    resume: bool,
) -> ArtifactRecord:
    artifacts_dir = _artifact_root(workspace) / "plans"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / f"{_today_prefix()}--{session_id}--implementation-plan.md"

    if resume and path.exists():
        return ArtifactRecord(path=path, content=path.read_text(encoding="utf-8"), created=False)

    content = _render_plan_document(
        session_id=session_id,
        prompt=prompt,
        context_bundle=context_bundle,
        design_path=design_artifact.path,
        task_plan=task_plan,
    )
    path.write_text(content, encoding="utf-8")
    return ArtifactRecord(path=path, content=content, created=True)


def _artifact_root(workspace: str | Path) -> Path:
    return Path(workspace).resolve() / ".omnicode" / "docs"


def _today_prefix() -> str:
    return datetime.now(timezone.utc).astimezone().date().isoformat()


def _render_design_document(
    *,
    session_id: str,
    prompt: str,
    context_bundle: ContextBundle,
) -> str:
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    selected_skills = context_bundle.metadata.get("skills_selected", [])
    discovered_skills = context_bundle.metadata.get("skills_discovered", 0)

    sections = [
        "# Superpowers-Inspired Design",
        "",
        f"- Session: `{session_id}`",
        f"- Generated: `{generated_at}`",
        f"- Methodology: `superpowers-inspired`",
        "",
        "## Request",
        prompt,
        "",
        "## Problem Statement",
        "Deliver the requested change through a staged OmniCode workflow instead of dispatching work with only the raw prompt.",
        "",
        "## Recommended Approach",
        "Use a design-first, plan-driven execution flow. Preserve workspace rules, surface relevant skills, then dispatch isolated sub-agents with explicit verification expectations.",
        "",
        "## Alternatives Considered",
        "- Dispatch immediately with only the raw prompt. Faster upfront, but weaker consistency and reviewability.",
        "- Use a single monolithic execution context. Simpler plumbing, but weaker task isolation and harder resume behavior.",
        "- Preferred: generate persistent design and plan artifacts, then dispatch focused sub-agent tasks with those artifacts in context.",
        "",
        "## Constraints And Inputs",
        f"- Workspace rules available: `{context_bundle.metadata.get('has_agents_md', False)}`",
        f"- Skills discovered: `{discovered_skills}`",
        f"- Skills selected: `{', '.join(selected_skills) if selected_skills else 'none'}`",
        f"- Tape events summarized: `{context_bundle.metadata.get('tape_events_used', 0)}`",
        "",
        "## Execution Guardrails",
        "- Follow workspace rules before methodology defaults.",
        "- Prefer small, bounded tasks that can be reviewed independently.",
        "- Expect testing and verification before considering a task complete.",
        "- Keep resume flows anchored to persisted artifacts and tape history.",
        "",
        "## Context Snapshot",
        context_bundle.planner_context[:6000],
        "",
    ]
    return "\n".join(sections).strip() + "\n"


def _render_plan_document(
    *,
    session_id: str,
    prompt: str,
    context_bundle: ContextBundle,
    design_path: Path,
    task_plan: dict[str, Any],
) -> str:
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    tasks = task_plan.get("tasks", [])
    task_sections: list[str] = []

    if not tasks:
        tasks = [{"type": "general", "desc": prompt}]

    for index, task in enumerate(tasks, start=1):
        target = _target_for_task(task.get("type", "general"))
        verification = _verification_hint(task.get("type", "general"))
        task_sections.extend(
            [
                f"### Task {index}: {task.get('type', 'general')}",
                f"- Target executor: `{target}`",
                f"- Goal: {task.get('desc', prompt)}",
                "- [ ] Inspect relevant files and confirm the smallest responsible surface area.",
                "- [ ] Add or update a failing check first when the codebase supports it.",
                "- [ ] Implement the smallest change that satisfies the task goal.",
                f"- [ ] Run verification: `{verification}`",
                "- [ ] Review the diff against the design and workspace rules.",
                "",
            ]
        )

    sections = [
        "# Superpowers-Inspired Implementation Plan",
        "",
        f"> Session `{session_id}` should follow design-first execution, sub-agent isolation, TDD where practical, and review before completion.",
        "",
        f"- Generated: `{generated_at}`",
        f"- Design artifact: `{design_path}`",
        "",
        "## Goal",
        prompt,
        "",
        "## Architecture Summary",
        "Execute the request through explicit tasks dispatched to focused executors, using persistent design and plan artifacts as the stable source of truth.",
        "",
        "## Context Notes",
        f"- Selected skills: `{', '.join(context_bundle.metadata.get('skills_selected', [])) or 'none'}`",
        f"- Workspace rules present: `{context_bundle.metadata.get('has_agents_md', False)}`",
        "",
        "## Tasks",
        *task_sections,
        "## Completion Criteria",
        "- Every task has a verification pass recorded in logs or tape.",
        "- Output still aligns with the design artifact.",
        "- Any follow-up risk is surfaced before workflow completion.",
        "",
    ]
    return "\n".join(sections).strip() + "\n"


def _target_for_task(task_type: str) -> str:
    if task_type == "frontend":
        return "gemini"
    return "codex"


def _verification_hint(task_type: str) -> str:
    if task_type == "frontend":
        return "Run the relevant frontend test, build, or visual verification command."
    if task_type == "backend":
        return "Run the relevant backend test or integration verification command."
    return "Run the narrowest available verification for the edited surface."
