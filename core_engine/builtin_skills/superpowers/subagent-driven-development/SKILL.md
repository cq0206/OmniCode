---
name: subagent-driven-development
description: Use during implementation to dispatch isolated workers per task, preserve context boundaries, and review each task before moving forward.
---

# Subagent-Driven Development

Implementation should be broken into focused tasks that can be executed and reviewed independently.

## Operating Model

- Give each sub-agent one clear task and the minimum context it needs.
- Preserve design and plan artifacts as the source of truth.
- Keep task outputs observable through logs and tape events.
- Do not let one task silently redefine the plan for the next.
