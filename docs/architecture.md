# Architecture

给已经走过 README 的人看的草图。逐步说明仍以根目录 `README.md` 第 4、5、6 节为准：先手写 ReAct 和 RAG，AgentScope 放最后选修。

## 概览

多 Agent + ReAct + RAG：

```
User
  → create_main_agent()          ← AGENT_BACKEND 选择实现
       CoordinatorAgent 或 ScopeCoordinator
       ├── math_agent        → CalculatorTool
       ├── writer_agent      → 无工具，只生成文字
       ├── knowledge_agent   → RetrieveTool（向量知识库）
       └── general_agent     → 无工具，只生成文字
```

手写版每个 Agent 内部仍是：

```
[Perceive] → [Decide] → [Act] → [Observe] → ... → Final Answer
```

子 Agent 通过 `DelegateTool`（AgentScope 里是 `delegate_tool()`）伪装成主 Agent 的工具，因此不必改 `AgentLoop`。

Flask / `main.py` 只调用 `create_main_agent()`，不关心具体实现。

## 模块依赖

```
main.py / server.py → api/routes.py
  └── agents/factory.py                 ← AGENT_BACKEND
        ├── coordinator_agent.py        ← handmade
        │     ├── tools/delegate.py
        │     ├── tools/retrieve.py
        │     ├── rag/store.py
        │     └── core/agent_loop.py
        └── scope_coordinator.py        ← agentscope
              └── scope_tools.py        ← calculator / retrieve / delegate 适配
```

HTTP 另有：`POST /knowledge`、`GET /knowledge/search` 直接读写 `get_vector_store()`，不经过 Agent。这和 Agent 检索必须是**同一份单例库**。

## RAG 流程

1. 切块：`chunker.py`
2. 向量化：`embeddings.py`（教学用 n-gram 哈希，64 维）
3. 存储：`store.py` → 内存 + `data/rag/index.json`
4. 检索：问句同样向量化，余弦相似度取 `RAG_TOP_K`
5. 生成：knowledge_agent 把命中段落当 Observation，再写最终答案

空库时 `get_vector_store()` 会灌入 `data/knowledge/*.md|txt`（跳过 README.md）。  
索引文件一旦存在，改 knowledge 目录**不会**自动刷新；删 `data/rag/` 或 `POST /knowledge`。

对话窗口（短期记忆）和知识库（向量）是分开的：聊天记录不进 RAG，制度文档不进 deque。

## 尚未接到主流程

`safety/`、`cache/`、`prompts/*.md` 有代码，当前 `AgentLoop` / `OpenAIClient` **没有调用**。见 README 第 14 节。

## 设计原则

- **子 Agent 当工具**：主循环无需知道对方是 Agent 还是计算器
- **记忆隔离**：只有主管持有 session 记忆；专家 `use_memory=False`
- **依赖注入**：测试可注入假 LLM / 临时 VectorStore
- **工厂**：`create_main_agent()` 按 `AGENT_BACKEND` 切换
- **知识与对话分离**：制度走向量库，多轮闲聊走短期记忆
