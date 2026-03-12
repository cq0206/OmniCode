from __future__ import annotations

from typing import Any
from collections.abc import Callable

try:
    import pluggy
except ImportError:  # pragma: no cover - bootstrap fallback
    pluggy = None


class _Marker:
    def __call__(self, func=None, **_kwargs):
        if func is None:
            return self
        return func


hookspec = pluggy.HookspecMarker("omnicode") if pluggy else _Marker()
hookimpl = pluggy.HookimplMarker("omnicode") if pluggy else _Marker()


@hookspec(firstresult=True)
def agent_plan(prompt: str, context: str) -> dict[str, Any]:
    """Break a user prompt into executable tasks."""


@hookspec
def agent_dispatch(
    task_type: str,
    task_desc: str,
    working_dir: str,
    emit_log: Callable[[str], None],
    session_id: str,
    yolo: bool,
    resume: bool,
) -> dict[str, Any] | None:
    """Route a task to the right executor."""


@hookspec(firstresult=True)
def agent_review(diff_content: str) -> bool | None:
    """Review the final result before completion."""
