# Architecture

## 概览

多 Agent + ReAct：

```
User
  → CoordinatorAgent（主：分活）
       ├── math_agent     → CalculatorTool
       ├── writer_agent   → 无工具，只生成文字
       └── general_agent  → 无工具，只生成文字
```

每个 Agent 内部仍是：

```
[Perceive] → [Decide] → [Act] → [Observe] → ... → Final Answer
```

子 Agent 通过 `DelegateTool` 伪装成主 Agent 的工具，因此不必改 `AgentLoop`。

可选后端：`.env` 里 `AGENT_BACKEND=agentscope` 时，同一张分工图改由
`ScopeCoordinator`（AgentScope 2.0 `Agent` + 原生 tool calling）执行。
Flask / `main.py` 只调用 `create_main_agent()`，不关心具体实现。

## 模块依赖

```
main.py / server.py
  └── agents/factory.py                 ← AGENT_BACKEND 开关
        ├── coordinator_agent.py        ← handmade：手写 ReAct
        │     ├── tools/delegate.py
        │     ├── agents/react_agent.py
        │     └── core/agent_loop.py
        └── scope_coordinator.py        ← agentscope：官方 Agent
              ├── scope_tools.py        ← CalculatorTool + 子 Agent 适配
              └── agentscope.agent.Agent
```

## 认知循环流程

1. **Perceive**: 构建 system prompt +（主 Agent）加载历史记忆 + 用户输入
2. **Decide**: LLM 输出 `Thought + Action[tool](args)` 或 `Final Answer`
3. **Act**: 解析 Action；若是 `math_agent` 则进入子 Agent 的循环
4. **Observe**: 将工具或子 Agent 返回结果回传给当前 Agent 的 LLM
5. **Loop**: 重复直到 Final Answer 或 max_iterations

## 设计原则

- **子 Agent 当工具**: 主循环无需知道「对方是 Agent 还是计算器」
- **记忆隔离**: 只有 Coordinator 持有 session 记忆；专家 `use_memory=False`
- **依赖注入**: Agent 接收 LLM/Tools/Memory，测试可注入假 LLM
- **工厂模式**: `create_main_agent()` 按 `AGENT_BACKEND` 选择手写或 AgentScope
