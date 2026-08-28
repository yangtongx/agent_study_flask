"""
ReAct Agent — Reasoning + Acting 模式实现。

主 Agent 和子 Agent 都复用这个类，差别只在：
- 叫什么名字
- 装备哪些工具
- 人设（role_prompt）写什么
- 要不要记忆
"""

from __future__ import annotations

from src.agents.base_agent import BaseAgent
from src.core.agent_loop import AgentLoop
from src.llm.base_client import BaseLLMClient
from src.llm.factory import LLMFactory
from src.memory.manager import MemoryManager
from src.tools.base_tool import BaseTool
from src.tools.calculator import CalculatorTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ReactAgent(BaseAgent):
    """
    ReAct 模式 Agent。

    内部通过 AgentLoop 驱动 Thought → Action → Observation 循环。
    """

    def __init__(
        self,
        name: str = "ReactAgent",
        *,
        llm_client: BaseLLMClient | None = None,
        tools: list[BaseTool] | None = None,
        memory: MemoryManager | None = None,
        max_iterations: int = 10,
        role_prompt: str = "",
        session_id: str | None = None,
        use_memory: bool = True,
    ) -> None:
        """
        Args:
            name: Agent 名称，出现在日志里。
            llm_client: 不传则用 LLMFactory 创建（对接 .env 里的模型）。
            tools: 不传则默认只给计算器。传空列表 [] 表示没有工具。
            memory: 不传且 use_memory=True 时自动创建 MemoryManager。
            max_iterations: ReAct 最多转几圈。
            role_prompt: 人设/职责说明，会写进 system prompt。
            session_id: 会话 ID，传给记忆系统。
            use_memory: 子 Agent 一般设 False（一次任务一结束就忘，避免污染主对话）。
        """
        if memory is not None:
            resolved_memory = memory
        elif use_memory:
            resolved_memory = MemoryManager(session_id=session_id)
        else:
            resolved_memory = None

        if tools is None:
            resolved_tools = [CalculatorTool()]
        else:
            resolved_tools = list(tools)

        super().__init__(
            name=name,
            llm_client=llm_client or LLMFactory.create(),
            tools=resolved_tools,
            memory=resolved_memory,
            max_iterations=max_iterations,
        )

        self.loop = AgentLoop(
            llm_client=self.llm_client,
            tools=self.tools,
            memory=self.memory,
            max_iterations=self.max_iterations,
            role_prompt=role_prompt,
        )

    async def run(self, user_input: str) -> str:
        """执行 ReAct 循环处理用户输入。"""
        logger.info("[%s] User input: %s", self.name, user_input[:200])
        result = await self.loop.execute(user_input)
        logger.info("[%s] Final answer: %s", self.name, result[:200])
        return result
