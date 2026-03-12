---
name: using-superpowers
description: Use at the start of orchestration to enforce the superpowers-inspired workflow and required skill checks before execution.
---

# Using Superpowers In OmniCode

This built-in skill applies a strict workflow discipline before OmniCode dispatches work.

## Core Rules

- Start with design before implementation whenever the task changes behavior or adds functionality.
- Write or refresh a concrete implementation plan before dispatching sub-agents.
- Prefer small, reviewable tasks with explicit verification.
- Keep user instructions and workspace rules above methodology defaults.

## Workflow Order

1. Brainstorm the design and save it as a persistent artifact.
2. Write an implementation plan that can guide sub-agents with minimal ambiguity.
3. Execute tasks with sub-agent isolation.
4. Require testing and code review before considering the workflow complete.
