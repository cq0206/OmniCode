# OmniCode

OmniCode 是一个面向本地开发环境的多智能体调度框架，采用 `TypeScript CLI Shell + Python Core Engine` 的异构架构。它的目标不是直接替代底层编码代理，而是作为总调度者统一完成上下文收集、需求拆解、任务路由、会话记忆、执行日志汇总，以及设计驱动的工作流编排。

当前版本已经打通以下主链路：

- TypeScript CLI 接收用户请求并通过 `stdio` 与 Python 引擎通信。
- Python 引擎按会话构建上下文，生成设计文档与实现计划，并通过插件机制分发任务。
- `codex` 与 `gemini` 执行器使用真实 `asyncio.create_subprocess_exec` 拉起外部 CLI。
- 会话轨迹与中间状态写入 append-only `.jsonl` tape，支持 `resume` 续跑。
- 内建一套受 [superpowers](https://github.com/obra/superpowers) 启发的工作流约束：先设计、再计划、再隔离执行、最后验证与复核。

## 当前能力

- 双端架构基础骨架：CLI Shell 已可运行，Desktop GUI 后续可复用 Python Core。
- JSON-RPC 风格 `stdio` IPC。
- Workspace 规则注入：自动读取工作区根目录 `AGENTS.md`。
- Skills 上下文加载：读取工作区 `.agent/skills/**/SKILL.md`，同时注入内建 workflow skills。
- Tape Memory：会话事件写入 `<workspace>/.omnicode/sessions/<session-id>.jsonl`。
- Superpowers-inspired artifacts：每个会话自动生成 design / implementation plan 文档。
- 子代理执行：按任务类型分派到 `codex` 或 `gemini`。

## 目录结构

```text
OmniCode/
├── src/                        # TypeScript CLI shell
│   ├── cli.ts
│   ├── processManager.ts
│   ├── types.ts
│   └── uiRenderer.ts
├── core_engine/                # Python core engine
│   ├── ipc_server.py
│   ├── engine.py
│   ├── context_builder.py
│   ├── subprocess_executor.py
│   ├── superpowers_workflow.py
│   ├── tape_memory.py
│   ├── hookspecs.py
│   ├── plugins/
│   └── builtin_skills/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── WORKFLOW.md
│   └── DEVELOPMENT.md
├── package.json
├── tsconfig.json
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
npm install
```

如果你希望使用完整的 Python 插件管理体验，可以在本地安装 Python 依赖：

```bash
cd core_engine
python3 -m pip install pluggy
```

说明：即使没有安装 `pluggy`，当前版本也提供了 fallback plugin manager，方便先跑通主链路。

### 2. 构建 CLI

```bash
npm run build
```

### 3. 运行一个工作流

```bash
node dist/cli.js run "Implement login API and Tailwind React login page"
```

或者开发模式直接运行：

```bash
npm run dev -- run "Implement login API and Tailwind React login page"
```

### 4. 续跑某个会话

```bash
node dist/cli.js resume <session-id> "Continue from the previous failure and finish the task"
```

## CLI 命令

### `run`

```bash
omnicode run "<prompt>" [-C <cwd>] [--session-id <id>] [--yolo]
```

### `resume`

```bash
omnicode resume <session-id> "[extra instruction]" [-C <cwd>] [--yolo]
```

## 环境变量

### `OMNICODE_PYTHON_BIN`

指定启动 Python 引擎时使用的解释器路径。

### `OMNICODE_CODEX_PREFIX`

覆盖后端执行器前缀。默认是：

```text
codex
```

例如：

```bash
export OMNICODE_CODEX_PREFIX="codex"
```

### `OMNICODE_GEMINI_PREFIX`

覆盖前端执行器前缀。默认是：

```text
gemini
```

例如：

```bash
export OMNICODE_GEMINI_PREFIX="gemini"
```

这两个环境变量也可用于本地 mock：

```bash
export OMNICODE_CODEX_PREFIX="/path/to/mock-codex"
export OMNICODE_GEMINI_PREFIX="/path/to/mock-gemini"
```

## 运行时输出

工作流运行后会在工作区生成：

- `.omnicode/sessions/<session-id>.jsonl`
- `.omnicode/docs/specs/<date>--<session-id>--design.md`
- `.omnicode/docs/plans/<date>--<session-id>--implementation-plan.md`

## 架构概览

### TypeScript Shell

- 接收命令行输入。
- 生成 JSON-RPC 请求。
- 拉起 Python IPC 进程。
- 渲染 `planning / dispatch / sub_agent_log / review / done / error` 事件。

### Python Core Engine

- 读取 `AGENTS.md`、workspace skills、builtin skills、历史 tape。
- 生成 planner context 与 executor context。
- 自动生成 design / implementation plan 文档。
- 通过 hook/plugin 机制路由任务。
- 使用异步子进程执行器流式消费底层代理输出。

### Execution Layer

- `codex`：面向 backend / general 任务。
- `gemini`：面向 frontend 任务。

## 文档索引

- [架构说明](docs/ARCHITECTURE.md)
- [工作流与会话机制](docs/WORKFLOW.md)
- [开发与发布说明](docs/DEVELOPMENT.md)

## 当前限制

- `planner` 仍然是启发式拆解，并未接入真实 LLM planner。
- `review` 当前是轻量占位实现，还没有接入真实 diff-based code review 模型。
- `codex` / `gemini` 参数兼容性仍取决于本机安装版本。
- 桌面 GUI 尚未开始实现，但当前 Python Core 已为 Tauri/Sidecar 路线预留了边界。

## 下一步建议

- 接入真实大模型做 `plan/review`。
- 增加宿主级依赖补全与自动 resume。
- 为 desktop 端补一个 Tauri + React 外壳。
- 增加自动化测试和 fixture-based integration tests。
