# API Reference

Python 类接口和扩展示例。HTTP 的逐步说明见根目录 `README.md` 第 9 节。

## HTTP（Flask）

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/` | 服务简介，含 `backend` |
| GET | `/health` | 状态、`sub_agents`、`knowledge_chunks` |
| GET | `/docs` | 接口说明 JSON |
| POST | `/chat` | `{message, session_id?}` → `{answer, agent, iterations, session_id}` |
| POST | `/knowledge` | `{content, source?}` 切块写入向量库 |
| GET | `/knowledge/search` | `?q=&top_k=` 直接检索，不经过 Agent |

入口：`server.py` → `src/api/routes.py`。主 Agent 由 `create_main_agent()` 创建。

## 核心接口

### create_main_agent

```python
from src.agents.factory import create_main_agent

agent = create_main_agent(session_id="demo")
answer = await agent.run("年假有几天")
```

`.env` 的 `AGENT_BACKEND=handmade|agentscope` 决定返回 `CoordinatorAgent` 还是 `ScopeCoordinator`。两者都有 `name`、`async run(str) -> str`、`loop._iteration_count`。

### BaseAgent

```python
from src.agents.base_agent import BaseAgent

class BaseAgent(ABC):
    name: str
    llm_client: BaseLLMClient
    tools: list[BaseTool]
    memory: MemoryManager
    max_iterations: int

    async def run(self, user_input: str) -> str
    def get_tool(self, name: str) -> BaseTool | None
    def add_tool(self, tool: BaseTool) -> None
```

### AgentLoop

```python
from src.core.agent_loop import AgentLoop

class AgentLoop:
    llm_client: BaseLLMClient
    tools: list[BaseTool]
    memory: MemoryManager
    max_iterations: int

    async def execute(self, user_input: str) -> str
```

### BaseTool

```python
from src.tools.base_tool import BaseTool

class BaseTool(ABC):
    @property
    def name(self) -> str
    @property
    def description(self) -> str
    async def run(self, args: str) -> str
```

现成工具：`CalculatorTool`、`RetrieveTool`、`DelegateTool`。

### RetrieveTool / 向量库

```python
from src.tools.retrieve import RetrieveTool
from src.rag.ingest import ingest_text
from src.rag.store import get_vector_store, VectorStore

ingest_text("年假每年 10 天", source="leave.md")
hits = get_vector_store().query("年假几天", top_k=3)

# 测试用临时库，避免写磁盘
store = VectorStore(persist_path=None)
await RetrieveTool(store=store).run("年假天数")
```

知识专家在 ReAct 里调用：`Action[retrieve](年假天数)`。

### BaseLLMClient

```python
from src.llm.base_client import BaseLLMClient

class BaseLLMClient(ABC):
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str
```

## 扩展指南

### 添加新子 Agent

```python
from src.agents.react_agent import ReactAgent
from src.tools.delegate import DelegateTool

weather = ReactAgent(
    name="WeatherAgent",
    tools=[],          # 或挂上天气工具
    use_memory=False,
    role_prompt="你是天气专家。必须直接用 Final Answer 作答。",
)

# 加入 CoordinatorAgent 的 tools 列表，并在 COORD_ROLE 里写路由规则
DelegateTool(weather, "weather_agent", "查询某城市天气。")
```

AgentScope 后端要在 `scope_coordinator.py` 同样加一个专家，并用 `delegate_tool()` 包一层。

### 添加新工具

```python
from src.tools.base_tool import BaseTool

class SearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Search the web for information."

    async def run(self, args: str) -> str:
        return f"Search results for: {args}"
```

交给**该用这个工具的那个专家**（例如只给 MathAgent），不要无脑挂到主管上。

### 添加新 LLM 客户端

1. 实现 `BaseLLMClient`
2. 在 `LLMFactory.create()` 中注册

### 切换到 AgentScope 2.0

选修：先把手写 ReAct 和 RAG 走通，再切。见 README 第 20 节。

```python
# .env: AGENT_BACKEND=agentscope
from src.agents.factory import create_main_agent

agent = create_main_agent(session_id="demo")
answer = await agent.run("15 * 23 等于多少")
```

实现见 `src/agents/scope_coordinator.py`。自定义工具需用 `AllowFunctionTool`（默认 ASK 会卡住 Flask）。
