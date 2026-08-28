"""
Agent 基类 — 定义所有 Agent 的统一接口。

=== 什么是基类（Base Class）？===
基类是一个"模板"，定义了所有子类必须有的属性和方法。
就像画了一张蓝图，具体的 Agent（如 ReactAgent）按照蓝图去实现。

=== 什么是 ABC？===
ABC = Abstract Base Class（抽象基类）。
用 @abstractmethod 标记的方法，子类必须实现，否则不能实例化。
这就像一份合同：基类说"你必须有 run() 方法"，子类必须遵守。

=== 什么是 dataclass？===
@dataclass 是 Python 的装饰器，自动帮你生成 __init__、__repr__ 等方法。
这样你不用手写一长串 __init__ 方法，只声明字段就行。
"""

# from __future__ import annotations 让类型注解支持 "前向引用"
# 比如类 A 的方法返回类型写 "A" 时，没有这行会报错
from __future__ import annotations

# ABC 和 abstractmethod 来自 abc 模块，用于定义抽象基类
from abc import ABC, abstractmethod

# dataclass 和 field 用于简化数据类的定义
from dataclasses import dataclass, field

# 导入 LLM 客户端基类（Agent 需要用它来调用大模型）
from src.llm.base_client import BaseLLMClient

# 导入记忆管理器（Agent 需要记住对话历史）
from src.memory.manager import MemoryManager

# 导入工具基类（Agent 可以使用各种工具）
from src.tools.base_tool import BaseTool

# 导入日志工具
from src.utils.logger import get_logger

# 创建当前模块的 logger
logger = get_logger(__name__)


@dataclass
class BaseAgent(ABC):
    """
    所有 Agent 的基类。

    这个类定义了一个 AI Agent 需要的基本组件：
    - 一个大脑（LLM 客户端）来推理
    - 一双手（工具列表）来执行动作
    - 一份记忆（记忆管理器）来记住对话
    - 一个限制（最大迭代次数）防止死循环

    Attributes:
        name: Agent 的名字，用于日志标识。
        llm_client: LLM 客户端实例，负责调用大模型 API（如 GPT-4）。
        tools: Agent 可用的工具列表，比如计算器、搜索工具等。
        memory: 记忆管理器，负责存储和检索对话历史。
        max_iterations: 最大推理循环次数，防止 Agent 陷入死循环。
    """

    # === 字段定义 ===
    # 每个字段都有默认值，子类可以通过 super().__init__() 覆盖

    name: str = "BaseAgent"  # Agent 名称

    # BaseLLMClient | None 表示这个值可以是 BaseLLMClient 类型或 None
    # 默认 None，子类在 __init__ 中赋实际值
    llm_client: BaseLLMClient | None = None

    # field(default_factory=list) 表示 tools 的默认值是一个新创建的空列表
    # 不能直接写 tools: list = []，因为所有实例会共享同一个列表（Python 的可变默认值陷阱）
    tools: list[BaseTool] = field(default_factory=list)

    # 记忆管理器，默认 None
    memory: MemoryManager | None = None

    # 最大迭代次数，默认 10 次
    max_iterations: int = 10

    @abstractmethod
    async def run(self, user_input: str) -> str:
        """
        处理用户输入并返回响应。

        这是抽象方法 — 子类必须实现它。
        不同类型的 Agent（ReAct、Plan-and-Execute 等）实现方式不同。

        Args:
            user_input: 用户输入的文本，比如 "帮我算一下 2+3"。

        Returns:
            Agent 的最终回复文本，比如 "2+3=5"。
        """
        # ... 表示方法体为空（抽象方法不需要实现，只定义接口）
        ...

    def get_tool(self, name: str) -> BaseTool | None:
        """
        按名称查找工具。

        比如工具列表里有 calculator 和 search，
        调用 get_tool("calculator") 就能拿到计算器工具。

        Args:
            name: 工具名称。

        Returns:
            找到的工具实例，或 None（没找到时）。
        """
        # next() 函数：遍历迭代器，返回第一个满足条件的元素
        # 这里遍历 self.tools，找到 t.name == name 的第一个工具
        # 如果没找到，返回默认值 None
        return next((t for t in self.tools if t.name == name), None)

    def add_tool(self, tool: BaseTool) -> None:
        """
        动态添加工具。

        运行时可以给 Agent 增加新能力。
        比如一开始只有计算器，后来加上搜索工具。

        Args:
            tool: 要添加的工具实例。
        """
        self.tools.append(tool)
        logger.debug("Tool added: %s", tool.name)
