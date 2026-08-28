# Architecture

## 概览

多 Agent + ReAct + RAG：

```
User
  → CoordinatorAgent（主：分活）
       ├── math_agent        → CalculatorTool
       ├── writer_agent      → 无工具，只生成文字
       ├── knowledge_agent   → RetrieveTool（向量知识库）
       └── general_agent     → 无工具，只生成文字
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
        │     ├── tools/retrieve.py     ← RAG
        │     ├── rag/store.py
        │     └── core/agent_loop.py
        └── scope_coordinator.py        ← agentscope：官方 Agent
```

## RAG 流程

1. 切块：`chunker.py` 把长文档切成小段
2. 向量化：`embeddings.py` 把每段变成 64 维单位向量
3. 存储：`store.py` 写入内存，并持久化 `data/rag/index.json`
4. 检索：用户问题同样向量化，按余弦相似度取 top_k
5. 生成：knowledge_agent 把命中段落当 Observation，再写 Final Answer

## 设计原则

- **子 Agent 当工具**: 主循环无需知道「对方是 Agent 还是计算器」
- **记忆隔离**: 只有 Coordinator 持有 session 记忆；专家 `use_memory=False`
- **依赖注入**: Agent 接收 LLM/Tools/Memory，测试可注入假 LLM
- **工厂模式**: `create_main_agent()` 按 `AGENT_BACKEND` 选择手写或 AgentScope
- **知识与对话分离**: 对话窗口是短期记忆；制度/文档走向量库
