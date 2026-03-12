from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class TapeMemory:
    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace)
        self.sessions_dir = self.workspace / ".omnicode" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.jsonl"

    def append_event(
        self,
        session_id: str,
        role: str,
        event_type: str,
        content: Any,
        **extra: Any,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "timestamp": time.time(),
            "role": role,
            "type": event_type,
            "content": content,
        }
        entry.update(extra)

        session_file = self.session_path(session_id)
        with session_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return entry

    def load_events(self, session_id: str) -> list[dict[str, Any]]:
        session_file = self.session_path(session_id)
        if not session_file.exists():
            return []

        events: list[dict[str, Any]] = []
        with session_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                events.append(json.loads(line))
        return events
