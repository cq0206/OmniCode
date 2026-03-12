from __future__ import annotations

import shlex
from typing import Any

from hookspecs import hookimpl
from subprocess_executor import command_prefix_from_env, run_subprocess_command


class CodexRunnerPlugin:
    @hookimpl
    async def agent_dispatch(
        self,
        task_type: str,
        task_desc: str,
        working_dir: str,
        emit_log,
        session_id: str,
        yolo: bool,
        resume: bool,
    ) -> dict[str, Any] | None:
        if task_type not in {"backend", "general"}:
            return None

        command = [
            *command_prefix_from_env("OMNICODE_CODEX_PREFIX", "codex"),
            "exec",
            "-C",
            working_dir,
        ]
        if yolo:
            command.append("--full-auto")
        command.append(task_desc)

        command_preview = shlex.join(
            [
                *command[:-1],
                "<resume-prompt>" if resume else "<task-prompt>",
            ]
        )

        emit_log(f"Command preview: {command_preview}")
        emit_log(f"Launching Codex for session {session_id} in {working_dir}.")

        return await run_subprocess_command(
            target="codex",
            command=command,
            command_preview=command_preview,
            cwd=working_dir,
            emit_log=emit_log,
            extra_env={
                "OMNICODE_SESSION_ID": session_id,
                "OMNICODE_RUN_MODE": "resume" if resume else "run",
            },
        )
