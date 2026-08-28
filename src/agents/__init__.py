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
Python 会先执行这个文件，把常用类和工厂函数暴露出来。
这样外部就不用写 `from src.agents.base_agent import BaseAgent` 这么长的路径了。

create_main_agent 是推荐入口：按 AGENT_BACKEND 返回手写或 AgentScope 主 Agent。
"""

# 从 base_agent 模块导入 BaseAgent 基类
from src.agents.base_agent import BaseAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.factory import create_main_agent
from src.agents.react_agent import ReactAgent

# __all__ 声明「from src.agents import *」时会导出哪些名字
__all__ = ["BaseAgent", "ReactAgent", "CoordinatorAgent", "create_main_agent"]
