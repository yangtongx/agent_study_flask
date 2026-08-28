"""
委派工具 — 把「调用另一个 Agent」包装成普通工具。

=== 为什么要这个文件？===
主 Agent 的循环（AgentLoop）只会调用 tool.run(args)。
它不知道「子 Agent」是什么。

所以我们把子 Agent 伪装成一个工具：
    主 Agent: Action[math_agent](15 * 23)
    → DelegateTool.run("15 * 23")
    → 内部 await math_agent.run("15 * 23")
    → 把子 Agent 的答案当成 Observation 交回主 Agent

主 Agent 眼里：math_agent 和 calculator 一样，都是工具。
这就是多 Agent 最简单的接法，不必改 AgentLoop。
"""

from __future__ import annotations

from src.tools.base_tool import BaseTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DelegateTool(BaseTool):
    """
    把一个子 Agent 包装成工具，供主 Agent 调用。
    """

    def __init__(self, agent: object, name: str, description: str) -> None:
        """
        Args:
            agent: 被调用的子 Agent，只要有 async run(str) -> str 即可。
            name: 出现在 Action[name](...) 里的名字，只能用英文和下划线。
            description: 写进主 Agent 的 system prompt，告诉它何时调用这个子 Agent。
        """
        self._agent = agent
        self._name = name
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    async def run(self, args: str) -> str:
        """
        把任务交给子 Agent，返回它的最终答案。

        前缀 [math_agent] 让主管在 Observation 里一眼看出是谁回的，
        再决定要不要接着叫 writer_agent。
        """
        logger.info("Delegate → %s: %s", self._name, args[:200])
        # 子 Agent 自己再跑一轮完整的 ReAct（可能还会调 calculator）
        result = await self._agent.run(args)
        logger.info("Delegate ← %s: %s", self._name, str(result)[:200])
        return f"[{self._name}] {result}"
