from __future__ import annotations

from hookspecs import hookimpl


FRONTEND_KEYWORDS = (
    "react",
    "vue",
    "css",
    "tailwind",
    "frontend",
    "ui",
)
BACKEND_KEYWORDS = (
    "api",
    "backend",
    "database",
    "python",
    "go",
    "rust",
    "login",
    "service",
)


class PlannerPlugin:
    @hookimpl
    def agent_plan(self, prompt: str, context: str) -> dict[str, object]:
        lowered = prompt.lower()
        tasks: list[dict[str, str]] = []

        if any(keyword in lowered for keyword in FRONTEND_KEYWORDS):
            tasks.append(
                {
                    "type": "frontend",
                    "desc": f"Implement the frontend or UI portion of this request: {prompt}",
                }
            )

        if any(keyword in lowered for keyword in BACKEND_KEYWORDS):
            tasks.append(
                {
                    "type": "backend",
                    "desc": f"Implement the backend, data, or API portion of this request: {prompt}",
                }
            )

        if not tasks:
            tasks.append({"type": "general", "desc": prompt})

        return {
            "tasks": tasks,
            "planner": "heuristic-bootstrap",
            "context_chars": len(context),
        }

    @hookimpl
    def agent_review(self, diff_content: str) -> bool:
        return bool(diff_content.strip()) or diff_content == ""
