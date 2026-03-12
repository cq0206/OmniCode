from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable

try:
    import pluggy
except ImportError:  # pragma: no cover - bootstrap fallback
    pluggy = None

import hookspecs
from context_builder import ContextBundle, build_context_bundle
from superpowers_workflow import ensure_design_artifact, ensure_plan_artifact
from tape_memory import TapeMemory
from plugins.codex_runner import CodexRunnerPlugin
from plugins.gemini_runner import GeminiRunnerPlugin
from plugins.planner import PlannerPlugin


EventEmitter = Callable[[dict[str, Any]], None]
SUPERPOWERS_REQUIRED_SKILLS = [
    "using-superpowers",
    "brainstorming",
    "writing-plans",
    "subagent-driven-development",
    "test-driven-development",
    "requesting-code-review",
]


class _FallbackHookRelay:
    def __init__(self, plugins: list[object]) -> None:
        self._plugins = plugins

    def _call_first(self, name: str, **kwargs: Any) -> Any:
        for plugin in self._plugins:
            hook = getattr(plugin, name, None)
            if hook is None:
                continue
            result = hook(**kwargs)
            if result is not None:
                return result
        return None

    def _call_all(self, name: str, **kwargs: Any) -> list[Any]:
        results: list[Any] = []
        for plugin in self._plugins:
            hook = getattr(plugin, name, None)
            if hook is None:
                continue
            results.append(hook(**kwargs))
        return results

    def agent_plan(self, **kwargs: Any) -> Any:
        return self._call_first("agent_plan", **kwargs)

    def agent_dispatch(self, **kwargs: Any) -> Any:
        return self._call_all("agent_dispatch", **kwargs)

    def agent_review(self, **kwargs: Any) -> Any:
        return self._call_first("agent_review", **kwargs)


class _FallbackPluginManager:
    def __init__(self) -> None:
        self._plugins: list[object] = []
        self.hook = _FallbackHookRelay(self._plugins)

    def add_hookspecs(self, _specs: object) -> None:
        return None

    def register(self, plugin: object) -> None:
        self._plugins.append(plugin)


class OmniCodeEngine:
    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()
        self.tape = TapeMemory(self.workspace)
        self.plugin_manager = self._build_plugin_manager()
        self._register_plugins()

    def _build_plugin_manager(self):
        if pluggy:
            manager = pluggy.PluginManager("omnicode")
            manager.add_hookspecs(hookspecs)
            return manager
        return _FallbackPluginManager()

    def _register_plugins(self) -> None:
        self.plugin_manager.register(PlannerPlugin())
        self.plugin_manager.register(CodexRunnerPlugin())
        self.plugin_manager.register(GeminiRunnerPlugin())

    async def _resolve_hook_result(self, result: Any) -> Any:
        if inspect.isawaitable(result):
            return await result
        return result

    async def _resolve_dispatch_result(self, results: Any) -> Any:
        if not isinstance(results, list):
            return await self._resolve_hook_result(results)

        resolved_result = None
        for index, candidate in enumerate(results):
            if resolved_result is not None:
                self._discard_unawaited_candidate(candidate)
                continue

            resolved = await self._resolve_hook_result(candidate)
            if resolved is not None:
                resolved_result = resolved
                for remaining in results[index + 1 :]:
                    self._discard_unawaited_candidate(remaining)
                break
        return resolved_result

    def _discard_unawaited_candidate(self, candidate: Any) -> None:
        if inspect.iscoroutine(candidate):
            candidate.close()

    def _build_context(self, session_id: str, prompt: str) -> tuple[ContextBundle, list[dict[str, Any]]]:
        previous_events = self.tape.load_events(session_id)
        bundle = build_context_bundle(
            self.workspace,
            prompt,
            previous_events,
            required_skill_names=SUPERPOWERS_REQUIRED_SKILLS,
        )
        return bundle, previous_events

    def _render_subagent_prompt(
        self,
        *,
        session_id: str,
        user_prompt: str,
        task_type: str,
        task_desc: str,
        context_bundle: ContextBundle,
        design_path: Path,
        design_content: str,
        plan_path: Path,
        plan_content: str,
        resume: bool,
    ) -> str:
        mode = "resume" if resume else "run"
        sections = [
            f"OmniCode dispatch mode: {mode}",
            f"Session ID: {session_id}",
            f"Workspace: {self.workspace}",
            "Workflow methodology:",
            "Use the superpowers-inspired flow: design artifact first, then implementation plan, then isolated execution with verification and review.",
            f"Assigned task type: {task_type}",
            "Persistent artifacts:",
            f"- Design: {design_path}",
            f"- Plan: {plan_path}",
            "Design artifact excerpt:",
            design_content[:4000],
            "Implementation plan excerpt:",
            plan_content[:4000],
            "User request:",
            user_prompt,
            "Assigned subtask:",
            task_desc,
            "Workspace context:",
            context_bundle.executor_context,
        ]
        if resume:
            sections.extend(
                [
                    "Resume instruction:",
                    "Continue from the existing tape context and focus on unresolved work instead of restarting from scratch.",
                ]
        )
        return "\n\n".join(section for section in sections if section)

    def _expected_target_for_task(self, task_type: str) -> str:
        if task_type == "frontend":
            return "gemini"
        if task_type in {"backend", "general"}:
            return "codex"
        return "executor"

    async def run_workflow(
        self,
        session_id: str,
        prompt: str,
        emit: EventEmitter,
        *,
        yolo: bool = False,
        resume: bool = False,
    ) -> str:
        self.tape.append_event(
            session_id,
            "user",
            "resume" if resume else "intent",
            prompt,
            yolo=yolo,
        )

        emit(
            {
                "event": "planning",
                "message": "Planning workflow from prompt and workspace context...",
            }
        )

        context_bundle, previous_events = self._build_context(session_id, prompt)
        self.tape.append_event(
            session_id,
            "system",
            "context",
            context_bundle.metadata,
            previous_event_count=len(previous_events),
        )

        design_artifact = ensure_design_artifact(
            workspace=self.workspace,
            session_id=session_id,
            prompt=prompt,
            context_bundle=context_bundle,
            resume=resume,
        )
        self.tape.append_event(
            session_id,
            "system",
            "design_artifact",
            str(design_artifact.path),
            created=design_artifact.created,
        )
        emit(
            {
                "event": "info",
                "message": (
                    f"Superpowers-inspired design artifact "
                    f"{'created' if design_artifact.created else 'reused'}: {design_artifact.path}"
                ),
            }
        )

        plan = await self._resolve_hook_result(
            self.plugin_manager.hook.agent_plan(
                prompt=prompt,
                context=context_bundle.planner_context,
            )
        ) or {
            "tasks": [{"type": "general", "desc": prompt}]
        }
        self.tape.append_event(session_id, "system", "plan", plan)

        plan_artifact = ensure_plan_artifact(
            workspace=self.workspace,
            session_id=session_id,
            prompt=prompt,
            context_bundle=context_bundle,
            design_artifact=design_artifact,
            task_plan=plan,
            resume=resume,
        )
        self.tape.append_event(
            session_id,
            "system",
            "plan_artifact",
            str(plan_artifact.path),
            created=plan_artifact.created,
        )
        emit(
            {
                "event": "info",
                "message": (
                    f"Superpowers-inspired implementation plan "
                    f"{'created' if plan_artifact.created else 'reused'}: {plan_artifact.path}"
                ),
            }
        )

        summaries: list[str] = []
        for task in plan.get("tasks", []):
            expected_target = self._expected_target_for_task(task["type"])
            task_prompt = self._render_subagent_prompt(
                session_id=session_id,
                user_prompt=prompt,
                task_type=task["type"],
                task_desc=task["desc"],
                context_bundle=context_bundle,
                design_path=design_artifact.path,
                design_content=design_artifact.content,
                plan_path=plan_artifact.path,
                plan_content=plan_artifact.content,
                resume=resume,
            )

            emit(
                {
                    "event": "dispatch",
                    "target": expected_target,
                    "message": f"Dispatching {task['type']} task to {expected_target}...",
                }
            )

            def emit_task_log(message: str, target: str | None = None) -> None:
                emit(
                    {
                        "event": "sub_agent_log",
                        "target": target or expected_target,
                        "message": message,
                    }
                )
                self.tape.append_event(
                    session_id,
                    "agent",
                    f"{(target or expected_target or 'executor')}_output",
                    message,
                    target=target or expected_target,
                )

            result = await self._resolve_dispatch_result(
                self.plugin_manager.hook.agent_dispatch(
                    task_type=task["type"],
                    task_desc=task_prompt,
                    working_dir=str(self.workspace),
                    emit_log=emit_task_log,
                    session_id=session_id,
                    yolo=yolo,
                    resume=resume,
                )
            ) or {
                "target": "executor",
                "command_text": "",
                "success": False,
                "exit_code": None,
                "summary": f"Skipped unsupported task type: {task['type']}",
            }

            self.tape.append_event(
                session_id,
                "system",
                "dispatch",
                result.get("command_text") or result.get("summary"),
                target=result.get("target"),
                task_type=task["type"],
            )

            if result.get("success") is False:
                failure_message = result.get("summary") or f"{result.get('target', task['type'])} failed."
                self.tape.append_event(
                    session_id,
                    "system",
                    "error",
                    failure_message,
                    target=result.get("target"),
                    exit_code=result.get("exit_code"),
                )
                emit({"event": "error", "message": failure_message})
                raise RuntimeError(str(failure_message))

            summaries.append(result.get("summary") or f"Completed {task['type']} task.")

        emit({"event": "review", "message": "Reviewing orchestration summary..."})
        review_passed = await self._resolve_hook_result(
            self.plugin_manager.hook.agent_review(diff_content="\n".join(summaries))
        )
        self.tape.append_event(
            session_id,
            "system",
            "review",
            {"passed": bool(review_passed)},
        )

        if review_passed is False:
            message = "Review rejected the current workflow output."
            self.tape.append_event(session_id, "system", "error", message)
            emit({"event": "error", "message": message})
            raise RuntimeError(message)

        final_message = " | ".join(summaries) if summaries else "No tasks were generated."
        self.tape.append_event(session_id, "system", "done", final_message)
        return final_message
