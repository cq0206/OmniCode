from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
import os
import shlex
import time
from typing import Any


async def run_subprocess_command(
    *,
    target: str,
    command: list[str],
    command_preview: str,
    cwd: str,
    emit_log: Callable[[str], None],
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    log_tail: deque[str] = deque(maxlen=20)
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    started_at = time.monotonic()

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        message = f"Executable not found for {target}: {command[0]}"
        emit_log(message)
        return {
            "target": target,
            "command_text": command_preview,
            "success": False,
            "exit_code": None,
            "summary": message,
            "tail": [message],
            "duration_sec": round(time.monotonic() - started_at, 3),
        }

    stdout_task = asyncio.create_task(
        _drain_stream(process.stdout, emit_log, log_tail, prefix="")
    )
    stderr_task = asyncio.create_task(
        _drain_stream(process.stderr, emit_log, log_tail, prefix="[stderr] ")
    )

    exit_code = await process.wait()
    await asyncio.gather(stdout_task, stderr_task)

    duration_sec = round(time.monotonic() - started_at, 3)
    success = exit_code == 0
    summary = (
        f"{target} finished successfully in {duration_sec}s."
        if success
        else f"{target} exited with code {exit_code} after {duration_sec}s."
    )

    return {
        "target": target,
        "command_text": command_preview,
        "success": success,
        "exit_code": exit_code,
        "summary": summary,
        "tail": list(log_tail),
        "duration_sec": duration_sec,
    }


def command_prefix_from_env(env_var: str, default_binary: str) -> list[str]:
    value = os.environ.get(env_var, default_binary).strip()
    parsed = shlex.split(value)
    return parsed or [default_binary]


async def _drain_stream(
    stream: asyncio.StreamReader | None,
    emit_log: Callable[[str], None],
    log_tail: deque[str],
    *,
    prefix: str,
) -> None:
    if stream is None:
        return

    while True:
        line = await stream.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="replace").rstrip()
        if not text:
            continue
        rendered = f"{prefix}{text}" if prefix else text
        log_tail.append(rendered)
        emit_log(rendered)
