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
