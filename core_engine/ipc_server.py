from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from typing import Any

from engine import OmniCodeEngine


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def emit_error(request_id: str | None, message: str, *, code: int = -32000) -> None:
    emit(
        {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message,
            },
            "id": request_id,
        }
    )


async def handle_request(request: dict[str, Any]) -> None:
    request_id = str(request.get("id") or uuid.uuid4().hex[:8])
    method = request.get("method")
    params = request.get("params") or {}

    if method not in {"run_workflow", "resume_workflow", "execute_task"}:
        emit_error(request_id, f"Unsupported method: {method}", code=-32601)
        return

    working_dir = (
        params.get("working_dir")
        or params.get("cwd")
        or os.getcwd()
    )
    prompt = params.get("prompt") or ""
    session_id = params.get("session_id") or uuid.uuid4().hex[:8]
    yolo = bool(params.get("yolo", False))

    engine = OmniCodeEngine(working_dir)
    result = await engine.run_workflow(
        session_id=session_id,
        prompt=prompt,
        emit=emit,
        yolo=yolo,
        resume=method == "resume_workflow",
    )

    emit(
        {
            "jsonrpc": "2.0",
            "result": {
                "success": True,
                "message": result,
                "session_id": session_id,
            },
            "id": request_id,
        }
    )


def main() -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            emit_error(None, f"Invalid JSON: {exc.msg}", code=-32700)
            continue

        try:
            asyncio.run(handle_request(request))
        except Exception as exc:  # pragma: no cover - CLI integration path
            request_id = request.get("id") if isinstance(request, dict) else None
            emit_error(str(request_id) if request_id is not None else None, str(exc))
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
