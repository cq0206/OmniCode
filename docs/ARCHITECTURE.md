# OmniCode 架构说明

## 1. 系统分层

OmniCode 采用三层结构：

1. TypeScript CLI Shell
2. Python Core Engine
3. External Executors

它的设计目标是把交互与渲染放在 Node.js 生态里，把调度、上下文运行时和执行编排放在 Python 中心层。

## 2. TypeScript CLI Shell

关键文件：

- `src/cli.ts`
- `src/processManager.ts`
- `src/uiRenderer.ts`

职责：

- 暴露 `run` / `resume` 命令。
- 将用户输入转换为 JSON-RPC 风格请求。
- 使用 `execa` 启动 `python3 -u core_engine/ipc_server.py`。
- 监听 Python `stdout` / `stderr` 并转换成 UI 事件。

### 2.1 事件模型

CLI 目前识别以下事件：

- `planning`
- `dispatch`
- `sub_agent_log`
- `review`
- `done`
- `error`
- `info`

## 3. Python Core Engine

关键文件：

- `core_engine/ipc_server.py`
- `core_engine/engine.py`
- `core_engine/context_builder.py`
- `core_engine/subprocess_executor.py`
- `core_engine/tape_memory.py`
- `core_engine/superpowers_workflow.py`

### 3.1 IPC Server

`ipc_server.py` 是 stdio 守护进程，负责：

- 循环读取单行 JSON 请求。
- 校验 `method` 与 `params`。
- 实例化 `OmniCodeEngine`。
- 将执行结果重新输出为 JSON-RPC 响应。

当前支持的方法：

- `run_workflow`
- `resume_workflow`
- `execute_task`

## 4. 上下文运行时

上下文由 `context_builder.py` 构建，主要输入包括：

- 工作区根目录 `AGENTS.md`
- 工作区 `.agent/skills/**/SKILL.md`
- 内建 workflow skills
- 当前 session 的最近 tape 事件

### 4.1 ContextBundle

当前拆分为两种上下文：

- `planner_context`
- `executor_context`

这样可以让 planner 拿到更全的 skills index，而 executor 只拿更聚焦的上下文与相关技能详情。

### 4.2 Skills 选择策略

OmniCode 会同时加载两类 skills：

- `workspace`：用户项目自己提供的 skills
- `builtin`：OmniCode 自带的 workflow methodology skills

选择规则：

- 命中 required workflow skills 的内建能力会强制进入上下文。
- 与 prompt 高相关的 workspace skill 会追加进入上下文。
- 当前 prompt 匹配是启发式 token scoring。

## 5. Superpowers-Inspired 工作流

`superpowers_workflow.py` 负责在执行前自动生成两个文档工件：

- design artifact
- implementation plan artifact

默认落盘位置：

- `.omnicode/docs/specs/`
- `.omnicode/docs/plans/`

这两个工件会被：

- 写入 tape
- 输出到 CLI 事件流
- 注入后续子代理 prompt

## 6. Tape Memory

`tape_memory.py` 使用 append-only JSONL 维护会话状态。

默认位置：

```text
<workspace>/.omnicode/sessions/<session-id>.jsonl
```

典型事件包括：

- `intent`
- `resume`
- `context`
- `design_artifact`
- `plan`
- `plan_artifact`
- `dispatch`
- `<target>_output`
- `review`
- `done`
- `error`

## 7. Hook / Plugin 体系

OmniCode 通过 `pluggy` 组织核心能力；如果本地没装 `pluggy`，会回退到内置 fallback plugin manager。

当前 hook：

- `agent_plan`
- `agent_dispatch`
- `agent_review`

当前插件：

- `PlannerPlugin`
- `CodexRunnerPlugin`
- `GeminiRunnerPlugin`

## 8. 执行层

### 8.1 Planner

`PlannerPlugin` 当前还是启发式拆解：

- frontend 相关关键词路由到 `frontend`
- backend 相关关键词路由到 `backend`
- 否则回退到 `general`

### 8.2 Codex Runner

`CodexRunnerPlugin` 负责：

- 接收 `backend` / `general` 任务
- 构造 `codex exec` 命令
- 调用统一子进程执行器

### 8.3 Gemini Runner

`GeminiRunnerPlugin` 负责：

- 接收 `frontend` 任务
- 构造 `gemini --prompt` 命令
- 调用统一子进程执行器

### 8.4 Async Subprocess Executor

`subprocess_executor.py` 是统一执行器抽象，负责：

- `asyncio.create_subprocess_exec`
- 并发消费 `stdout` / `stderr`
- 实时推送日志到上层事件流
- 返回退出码、耗时与日志 tail

## 9. Resume 模式

`resume` 并不会简单地重放旧 prompt，而是：

- 重新读取当前 session tape
- 复用或重建 design / plan 工件
- 在子代理 prompt 中显式写入 `resume` 模式和续跑说明

## 10. 当前演进方向

- 引入真实 LLM-based planner / review
- 增加宿主级依赖修复与 resume 闭环
- 接入 git diff / test results 作为 review 上下文
- 为 Tauri Desktop Shell 复用同一个 Python Core
