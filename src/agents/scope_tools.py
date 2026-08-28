"""
AgentScope 工具适配 — 把本项目已有的工具接到 AgentScope 2.0。

=== 为什么要单独写这一层？===
手写 ReAct 的工具继承 src.tools.BaseTool，签名是：
    async def run(self, args: str) -> str

AgentScope 2.0 的工具继承 agentscope.tool.ToolBase，走：
    关键字参数 + JSON Schema（模型按字段名传参，不是一整段字符串）

两边「合同」不一样，所以不能直接把 CalculatorTool 塞给 AgentScope。
这一层做两件事：
1. 把计算器、子 Agent 包装成 AgentScope 认识的 FunctionTool
2. 把默认权限从 ASK 改成 ALLOW（见下面「权限」说明）

=== 什么是 FunctionTool？===
AgentScope 提供的适配器：你写一个普通 Python 函数，它自动：
- 从函数名 / 你传入的 name 得到工具名
- 从类型注解生成 JSON Schema（expression: str → 模型知道要传字符串）
- 调用时把模型给的 JSON 拆成关键字参数再调你的函数

=== 什么是权限 ASK / ALLOW？===
AgentScope 2.0 有权限引擎。FunctionTool 默认是 ASK：
    模型想调工具 → 框架先问人「同不同意」→ 同意了才真正执行

学习项目跑在 Flask / 命令行里，没有弹窗，ASK 会把请求卡住。
所以 AllowFunctionTool 改成 ALLOW：计算器这种安全工具直接放行。

警告：生产环境如果接了会改文件、跑系统命令的工具，不要用这个类。
"""

from __future__ import annotations

# Any：子 Agent 只要有 reply() 就行，不必写死成 Agent 类型（测试里可以注入假对象）
from typing import Any

# PermissionBehavior：允许 / 拒绝 / 询问 三种行为
# PermissionDecision：权限检查的返回值（行为 + 说明文字）
from agentscope.permission import PermissionBehavior, PermissionDecision

# FunctionTool：把普通 Python 函数包装成 AgentScope 工具
from agentscope.tool import FunctionTool

# 复用本项目已经写好、用 AST 防注入的安全计算器
from src.tools.calculator import CalculatorTool
from src.tools.retrieve import RetrieveTool


class AllowFunctionTool(FunctionTool):
    """
    学习用 FunctionTool：自动允许调用，不向用户确认。

    === 怎么覆盖权限？===
    FunctionTool.check_permissions 默认返回 ASK。
    子类重写这个方法，返回 ALLOW，Agent 就不会停下来等人确认。

    生产环境如果接了会改文件、跑命令的工具，不要用这个类。
    """

    async def check_permissions(
        self,
        *_args: Any,
        **_kwargs: Any,
    ) -> PermissionDecision:
        """
        每次工具被调用前，AgentScope 都会问一次「能不能跑」。

        *_args / **_kwargs：父类签名可能带 tool_input、context，
        我们不检查内容，直接放行，所以全部忽略。
        """
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="study project: auto-allow custom tools",
        )


async def _calculator(expression: str) -> str:
    """
    AgentScope 眼里的「计算器函数」。

    参数必须写成 expression: str，不能再叫 args。
    因为 AgentScope 会按参数名生成 JSON Schema，模型会输出：
        {"expression": "15 * 23"}
    而不是手写版那种一整段 Action[calculator](15 * 23)。

    Args:
        expression: 算术表达式，例如 '2 + 3 * 4'。支持 +, -, *, /, //, %, ** 和括号。
    """
    # 真正计算仍走本项目的 CalculatorTool（AST 白名单，不用 eval）
    return await CalculatorTool().run(expression)


def calculator_tool() -> AllowFunctionTool:
    """
    把本项目的 CalculatorTool 包装成 AgentScope 工具。

    name / description 会写进工具列表，模型靠它们决定「什么时候该用计算器」。
    """
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

    === 和手写版怎么对应？===
    手写：主 Agent 输出 Action[math_agent](15 * 23)
          → DelegateTool.run("15 * 23")
          → await math_agent.run("15 * 23")

    这里：模型原生 function calling 选中 math_agent
          → _call(task="15 * 23")
          → await math_agent.reply(UserMsg(...))

    主 Agent 眼里：math_agent 和 calculator 一样，都是工具。

    Args:
        agent: 被调用的子 Agent，只要有 async reply(...) 即可。
        name: 暴露给主 Agent 的工具名，例如 math_agent。
        description: 告诉主 Agent「什么时候该叫这个专家」。
    """

    async def _call(task: str) -> str:
        """
        真正被主 Agent 调用的函数。

        task: 主 Agent 交给专家的那句话，例如 "15 * 23"。
        UserMsg: AgentScope 的用户消息。name 是发送者名字，content 是正文。
        reply(): 子 Agent 自己再跑一轮推理（数学专家会去调 calculator）。
        get_text_content(): 从回复消息里抽出纯文本。
        """
        # 延迟导入：避免模块顶层循环依赖，也让「消息类型」只在真正调用时才用到
        from agentscope.message import UserMsg

        reply = await agent.reply(UserMsg(name="coordinator", content=task))
        text = reply.get_text_content() if reply is not None else ""
        # 子 Agent 万一回了空字符串，给主 Agent 一个明确标记，避免它以为「没返回」
        return (text or "").strip() or "(empty reply)"

    # FunctionTool 默认用函数名当工具名。这里闭包函数都叫 _call，
    # 必须手动改成 math_agent / writer_agent 等，否则多个工具重名。
    _call.__name__ = name
    _call.__doc__ = description
    return AllowFunctionTool(_call, name=name, description=description)


async def _retrieve(query: str) -> str:
    """从知识库检索相关资料。

    Args:
        query: 要查的问题或关键词，例如 '年假有几天'。
    """
    return await RetrieveTool().run(query)


def retrieve_tool() -> AllowFunctionTool:
    """把本项目的 RetrieveTool 包装成 AgentScope 工具。"""
    return AllowFunctionTool(
        _retrieve,
        name="retrieve",
        description=(
            "从知识库检索相关资料。"
            "输入：要查的问题或关键词，例如 '年假有几天'。"
        ),
    )
