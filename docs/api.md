# API Reference

## 核心接口

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
    role_prompt="You are WeatherAgent. ...",
)

# 加入 CoordinatorAgent 的 tools 列表：
DelegateTool(weather, "weather_agent", "Look up weather for a city.")
```

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
        # 实现搜索逻辑
        return f"Search results for: {args}"
```

### 添加新 LLM 客户端

1. 实现 `BaseLLMClient`
2. 在 `LLMFactory.create()` 中注册

### 切换到 AgentScope 2.0

```python
from src.agents.factory import create_main_agent

# .env: AGENT_BACKEND=agentscope
agent = create_main_agent(session_id="demo")
answer = await agent.run("15 * 23 等于多少")
```

实现见 `src/agents/scope_coordinator.py`。分工与手写 `CoordinatorAgent` 相同。

### 灌入知识（RAG）

```python
from src.rag.ingest import ingest_text
from src.rag.store import get_vector_store

ingest_text("年假每年 10 天", source="leave.md")
hits = get_vector_store().query("年假几天", top_k=3)
```

HTTP：`POST /knowledge`、`GET /knowledge/search?q=...`
知识专家工具：`RetrieveTool`（`Action[retrieve](年假天数)`）。
