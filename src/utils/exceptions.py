"""
自定义异常层次结构。

=== 为什么需要自定义异常？===
Python 内置的 Exception 太笼统了。
如果所有错误都抛 Exception，调用方没法区分是 LLM 挂了还是工具挂了。

自定义异常形成层次结构，调用方可以精确捕获：

    try:
        await agent.run("...")
    except MaxIterationsError:
        # 只处理"超次数"这种情况
        ...
    except LLMError:
        # 只处理"LLM 调用失败"这种情况
        ...
    except AgentError:
        # 捕获所有 Agent 相关异常（父类）
        ...

=== 异常层次 ===
    Exception（Python 内置）
    └── AgentError（所有 Agent 异常的基类）
        ├── AgentLoopError（认知循环出错）
        │   └── MaxIterationsError（超过最大迭代次数）
        ├── LLMError（LLM 调用失败）
        ├── ToolError（工具执行失败）
        └── MemoryError（记忆系统错误）
"""


class AgentError(Exception):
    """Agent 框架基础异常。所有自定义异常的父类。"""


class AgentLoopError(AgentError):
    """Agent 认知循环中发生的错误。"""


class MaxIterationsError(AgentLoopError):
    """
    超过最大迭代次数。

    Agent 循环了 max_iterations 次还没给出 Final Answer。
    可能是 LLM 陷入了死循环，或者任务太难需要更多步骤。
    """


class LLMError(AgentError):
    """LLM 调用失败（网络错误、认证失败、限流等）。"""


class ToolError(AgentError):
    """工具执行失败。"""


class MemoryError(AgentError):
    """记忆系统错误。"""
