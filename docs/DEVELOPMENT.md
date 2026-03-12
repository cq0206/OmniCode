# OmniCode 开发说明

## 1. 本地环境

推荐环境：

- Node.js >= 20
- Python >= 3.10

## 2. 安装

```bash
npm install
```

如果希望启用正式的 Python plugin manager：

```bash
cd core_engine
python3 -m pip install pluggy
```

## 3. 常用命令

### 安装依赖

```bash
npm install
```

### 构建

```bash
npm run build
```

### 开发模式运行

```bash
npm run dev -- run "your prompt"
```

### 编译 Python Core

```bash
python3 -m compileall core_engine
```

## 4. Mock 执行器调试

如果本机没有真实 `codex` / `gemini`，可以通过环境变量覆盖命令前缀：

```bash
export OMNICODE_CODEX_PREFIX="/tmp/mock-codex"
export OMNICODE_GEMINI_PREFIX="/tmp/mock-gemini"
```

这对于调试：

- IPC 是否正常
- prompt 注入是否正确
- artifact 是否落盘
- tape 是否记录完整

非常有用。

## 5. 提交前建议验证

至少执行：

```bash
npm run build
python3 -m compileall core_engine
```

如果本机安装了真实执行器，建议再额外跑一次：

```bash
node dist/cli.js run "small real-world prompt"
```

## 6. 当前工程约定

- TypeScript 负责 shell、渲染与进程管理。
- Python 负责上下文、工作流、会话状态与子进程调度。
- 所有会话状态都落盘到 `.omnicode/`，不依赖进程内内存恢复。
- 设计与计划工件默认是工作流的一部分，不是可选附属产物。

## 7. 后续建议

- 增加 integration tests fixtures
- 接入真实 planner / reviewer
- 增加 desktop shell
- 增加 package 发布与 postinstall Python bootstrap
