"""
快速启动示例 — 用 Mock LLM 演示 Agent 运行流程。

无需真实 API Key 即可运行：
    python examples/quick_start.py

=== 这个示例做什么？===
1. 创建一个假的 LLM 客户端（DemoLLMClient），预设好两轮回复
2. 创建 AgentLoop，挂载计算器工具
3. 模拟用户问 "100 * 7 + 3 等于多少"
4. Agent 走完完整的 ReAct 循环（Thought → Action → Observation → Final Answer）
5. 打印结果

=== 运行效果 ===
🚀 Starting My Agent (Demo Mode)

🧑 User: What is 100 * 7 + 3?

🤖 Agent: 100 * 7 + 3 = 703
"""

import asyncio

from src.core.agent_loop import AgentLoop
from src.tools.calculator import CalculatorTool


class DemoLLMClient:
    """
    演示用 LLM — 预设 ReAct 循环响应。

    这个类"假装"自己是一个 LLM 客户端（实现了 chat 方法），
    但实际上返回的是写死在代码里的固定回复。

    第一轮：决定用计算器
    第二轮：看到结果后给出最终答案
    """

    def __init__(self) -> None:
        self._step = 0  # 记录当前是第几步

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """模拟 LLM 的两轮对话。"""
        self._step += 1
        if self._step == 1:
            # 第一轮：LLM "思考"后决定调用计算器工具
            return (
                "Thought: The user wants to calculate. I'll use the calculator tool.\n"
                "Action[calculator](100 * 7 + 3)"
            )
        # 第二轮：LLM 看到 Observation（计算器返回 703），给出最终答案
        return (
            "Thought: The calculator returned 703. That's the answer.\n"
            "Final Answer: 100 * 7 + 3 = 703"
        )


async def main() -> None:
    """快速启动入口。"""
    print("🚀 Starting My Agent (Demo Mode)\n")

    # 创建认知循环，挂载：
    # - 假 LLM 客户端（不需要真实 API Key）
    # - 真实的计算器工具（会真正执行计算）
    loop = AgentLoop(
        llm_client=DemoLLMClient(),
        tools=[CalculatorTool()],
        max_iterations=5,
    )

    user_input = "What is 100 * 7 + 3?"
    print(f"🧑 User: {user_input}")

    # 执行 ReAct 循环
    result = await loop.execute(user_input)
    print(f"\n🤖 Agent: {result}")


# 入口：asyncio.run 创建事件循环并运行 main 协程
if __name__ == "__main__":
    asyncio.run(main())
