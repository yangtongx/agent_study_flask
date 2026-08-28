"""
AgentScope 工具适配 — 把本项目已有的工具接到 AgentScope 2.0。

=== 为什么要单独写这一层？===
手写 ReAct 的工具继承 src.tools.BaseTool，签名是 run(args: str)。
AgentScope 2.0 的工具继承 agentscope.tool.ToolBase，走 JSON Schema + 关键字参数。

另外：AgentScope 的 FunctionTool 默认权限是 ASK（每次调用都要人点确认）。
学习项目在 Flask / 命令行里没法弹窗，所以这里改成 ALLOW，自动放行。
"""

from __future__ import annotations

from typing import Any

from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import FunctionTool

from src.tools.calculator import CalculatorTool


class AllowFunctionTool(FunctionTool):
    """
    学习用 FunctionTool：自动允许调用，不向用户确认。

    生产环境如果接了会改文件、跑命令的工具，不要用这个类。
    """

    async def check_permissions(
        self,
        *_args: Any,
        **_kwargs: Any,
    ) -> PermissionDecision:
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="study project: auto-allow custom tools",
        )


async def _calculator(expression: str) -> str:
    """做数学计算。

    Args:
        expression: 算术表达式，例如 '2 + 3 * 4'。支持 +, -, *, /, //, %, ** 和括号。
    """
    return await CalculatorTool().run(expression)


def calculator_tool() -> AllowFunctionTool:
    """把本项目的 CalculatorTool 包装成 AgentScope 工具。"""
    return AllowFunctionTool(
        _calculator,
        name="calculator",
        description=(
            "做数学计算。"
            "输入：算术表达式，例如 '2 + 3 * 4'。"
            "支持：+, -, *, /, //, %, ** 和括号。"
        ),
    )


def delegate_tool(agent: Any, name: str, description: str) -> AllowFunctionTool:
    """
    把另一个 AgentScope Agent 包装成工具（对应手写版的 DelegateTool）。

    主 Agent 调用这个工具时，其实是在问子 Agent。
    """

    async def _call(task: str) -> str:
        from agentscope.message import UserMsg

        reply = await agent.reply(UserMsg(name="coordinator", content=task))
        text = reply.get_text_content() if reply is not None else ""
        return (text or "").strip() or "(empty reply)"

    _call.__name__ = name
    _call.__doc__ = description
    return AllowFunctionTool(_call, name=name, description=description)
