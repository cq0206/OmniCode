# OmniCode 工作流与会话机制

## 1. 一次 `run` 的完整流程

1. 用户执行 `omnicode run "<prompt>"`。
2. TypeScript Shell 将请求封装成 JSON-RPC 并发送给 Python IPC Server。
3. Python 引擎加载：
   - `AGENTS.md`
   - workspace skills
   - builtin workflow skills
   - 最近的 session tape
4. 引擎生成 design artifact。
5. 引擎执行 planner，生成任务计划。
6. 引擎生成 implementation plan artifact。
7. 对每个 task 选择目标 executor。
8. 执行器启动外部 CLI，流式回传日志。
9. 引擎记录 review 结果。
10. 写入 `done` 或 `error` 到 tape。

## 2. `resume` 的语义

`resume` 的关键价值不只是“再次执行”，而是“带着历史状态继续执行”。

当前 resume 行为：

- 保留原 `session_id`
- 重新构建上下文
- 重新读取最近 tape 事件
- 在子代理 prompt 中写入 resume instruction
- 尝试复用已有 design / plan artifact

## 3. 设计先行的执行约束

借鉴 Superpowers 的工作方法，OmniCode 现在会在正式 dispatch 前固定执行：

1. Brainstorming
2. Writing Plans
3. Subagent-Driven Development
4. Test-Driven Development
5. Requesting Code Review

这套约束既体现在：

- builtin skills 注入
- design / plan artifact 自动生成
- 子代理 prompt 中的 methodology section

## 4. 会话产物

每个 session 至少会产生三类产物：

### 4.1 Tape

```text
.omnicode/sessions/<session-id>.jsonl
```

### 4.2 Design

```text
.omnicode/docs/specs/<date>--<session-id>--design.md
```

### 4.3 Plan

```text
.omnicode/docs/plans/<date>--<session-id>--implementation-plan.md
```

## 5. 子代理 prompt 组成

当前 executor 接收到的 prompt 由以下部分拼接而成：

- run / resume 模式
- session id
- workspace path
- workflow methodology
- design artifact path
- plan artifact path
- design artifact excerpt
- implementation plan excerpt
- user request
- assigned subtask
- executor context

## 6. 错误处理

当前错误处理模型以“可观测性优先”为主：

- 外部 CLI 启动失败会直接记录为 error 事件
- 非零退出码会导致当前 workflow 失败
- `stderr` 会实时透传到日志流

后续可以继续扩展为：

- 依赖缺失自动修复
- git diff review 不通过后的自动迭代
- 测试失败后的 resume 策略
