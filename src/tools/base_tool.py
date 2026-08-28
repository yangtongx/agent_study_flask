"""
工具基类 — 定义统一 name/description/run 接口。

=== 设计理念 ===
所有工具都遵循同一个接口（name + description + run），
这样 AgentLoop 不需要知道每个工具的内部实现，
只需要统一调用 tool.run(args) 就行。

这就是"多态"：不同工具，同一个调用方式。
新增工具时，只需要继承 BaseTool 实现三个方法，不需要改 Agent 的代码。
这符合"开闭原则"（对扩展开放，对修改关闭）。
"""

from __future__ import annotations

# ABC 和 abstractmethod 用于定义抽象基类
from abc import ABC, abstractmethod

# dataclass 用于简化数据类的定义
from dataclasses import dataclass


@dataclass
class BaseTool(ABC):
    """
    所有工具的基类。

    子类需实现:
        - name: 工具名称（LLM 用它来选择工具）
        - description: 工具描述（告诉 LLM 这个工具能做什么）
        - run(): 实际执行逻辑

    === 为什么 name 和 description 是 @property？===
    @property 把方法变成属性，访问时不用加括号。
    比如 calc.name 而不是 calc.name()。
    因为它们是"只读属性"，不是动作，用 @property 更自然。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        工具名称，用于 Action[name] 调用。

        必须是英文，不含空格，因为 LLM 输出的 Action[xxx] 要用它匹配。
        例如 "calculator"、"search"、"weather"。
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """
        工具描述，帮助 LLM 判断何时使用此工具。

        这段文字会出现在 system prompt 里，LLM 会根据描述决定：
        "用户问的是数学题，我应该用 calculator 工具。"
        所以描述要写清楚：工具做什么、接收什么参数。
        """
        ...

    @abstractmethod
    async def run(self, args: str) -> str:
        """
        执行工具。

        这是工具的核心方法，AgentLoop 解析出 Action 后调用它。

        Args:
            args: LLM 传入的参数字符串。
                  比如计算器收到 "15 * 23"，搜索工具收到 "Python 教程"。

        Returns:
            执行结果字符串，会作为 Observation 返回给 LLM。
        """
        ...
