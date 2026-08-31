"""
ReAct Agent — Reasoning + Acting 模式实现。

=== 什么是 ReAct？===
ReAct 是一种 Agent 设计模式，名字来自两个词：
- Reasoning（推理）：Agent 先"想"一下该做什么
- Acting（行动）：然后"做"出来（调用工具）

完整流程是：
1. Thought（思考）：分析问题，决定下一步做什么
2. Action（行动）：调用某个工具执行操作
3. Observation（观察）：看工具返回了什么结果
4. 重复 1-3 直到能给出最终答案
5. Final Answer（最终答案）

=== 举个例子 ===
用户问："100 × 7 + 3 等于多少？"

Agent 第 1 轮：
  Thought: 用户要计算，我用计算器工具
  Action[calculator](100 * 7 + 3)
  Observation: 100 * 7 + 3 = 703

Agent 第 2 轮：
  Thought: 计算器返回 703，这就是答案
  Final Answer: 100 * 7 + 3 = 703
"""

from __future__ import annotations

# 导入基类
from src.agents.base_agent import BaseAgent

# 导入认知循环（Agent 的"大脑"，管理 Thought→Action→Observation 循环）
from src.core.agent_loop import AgentLoop

# 导入 LLM 工厂（用工厂模式创建客户端，解耦具体实现）
from src.llm.factory import LLMFactory

# 导入记忆管理器
from src.memory.manager import MemoryManager

# 默认工具列表：计算器 + 搜索 + fetch（加新工具只改 default_tools）
from src.tools import default_tools

# 导入日志
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ReactAgent(BaseAgent):
    """
    ReAct 模式 Agent。

    继承 BaseAgent，实现了 run() 方法。
    内部通过 AgentLoop 驱动 Thought → Action → Observation 循环。

    遵循 Thought → Action → Observation 循环：
    1. Thought: LLM 推理当前应该做什么
    2. Action: 调用工具执行动作
    3. Observation: 观察工具返回结果
    4. 重复直到得出最终答案
    """

    def __init__(self, name: str = "ReactAgent") -> None:
        """
        初始化 ReactAgent。

        在实际项目中，这些组件应该通过"依赖注入"传入
        （即从外部传进来，而不是在 __init__ 里 new 出来），
        这样方便测试和切换实现。这里为了快速启动，直接创建默认实例。

        Args:
            name: Agent 名称，默认 "ReactAgent"。
        """
        # 调用父类 BaseAgent 的初始化，传入各种组件
        # LLMFactory.create() 用工厂模式创建一个 OpenAI 客户端
        # default_tools()：计算器 + 搜索 + fetch
        # MemoryManager() 创建记忆管理器
        super().__init__(
            name=name,
            llm_client=LLMFactory.create(),
            tools=default_tools(),
            memory=MemoryManager(),
            max_iterations=10,
        )

        # 创建认知循环实例，把 LLM、工具、记忆都传给它
        # AgentLoop 是真正干活的地方，ReactAgent 只是壳
        self.loop = AgentLoop(
            llm_client=self.llm_client,
            tools=self.tools,
            memory=self.memory,
            max_iterations=self.max_iterations,
        )

    async def run(self, user_input: str) -> str:
        """
        执行 ReAct 循环处理用户输入。

        这是实现了父类定义的抽象方法。
        实际工作委托给 self.loop.execute()。

        Args:
            user_input: 用户输入文本。

        Returns:
            Agent 最终回复。
        """
        # 记录用户输入（截取前 200 字符防止日志过长）
        logger.info("[%s] User input: %s", self.name, user_input[:200])

        # 调用认知循环执行 ReAct 流程
        # await 等待异步操作完成
        result = await self.loop.execute(user_input)

        # 记录最终答案
        logger.info("[%s] Final answer: %s", self.name, result[:200])
        return result
