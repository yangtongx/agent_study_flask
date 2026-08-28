"""
Agent 模块 — 定义 Agent 实例与类型。

=== 什么是 Agent？===
Agent（智能体）是一个能自主推理和行动的 AI 系统。
它不只是简单地回答问题，而是能：
1. 理解用户需求（感知）
2. 思考该怎么做（推理/决策）
3. 调用工具完成任务（执行）
4. 根据结果调整策略（反馈）

=== 这个文件做什么？===
这是一个"包初始化"文件（__init__.py）。
它的作用是：当你 `from src.agents import BaseAgent` 时，
Python 会先执行这个文件，把 BaseAgent 和 ReactAgent 暴露出来。
这样外部就不用写 `from src.agents.base_agent import BaseAgent` 这么长的路径了。
"""

# 从 base_agent 模块导入 BaseAgent 基类
from src.agents.base_agent import BaseAgent

# 从 react_agent 模块导入 ReactAgent 具体实现
from src.agents.react_agent import ReactAgent

# __all__ 定义了 `from src.agents import *` 时会导出的名称
# 这是一个好习惯，明确声明模块的公开接口
__all__ = ["BaseAgent", "ReactAgent"]
