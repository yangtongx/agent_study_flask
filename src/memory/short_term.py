"""
短期记忆 — 维护对话历史窗口。

=== 什么是"窗口"？===
LLM 的输入有长度限制（token 上限），不能把所有历史对话都塞进去。
"窗口"就是只保留最近 N 条消息，老的消息自动丢弃。

比如窗口大小为 3，对话顺序是 A, B, C, D, E：
- 加入 D 时：B, C, D（A 被挤出）
- 加入 E 时：C, D, E（B 被挤出）

=== 为什么用 deque？===
deque（双端队列）是 Python 的高效数据结构：
- 在两端添加/删除元素都是 O(1) 时间
- 设置 maxlen 后，超出长度自动从另一端删除，不需要手动管理
"""

from __future__ import annotations

# deque 是双端队列，比 list 在头部删除时高效得多
from collections import deque

# dataclass 和 field 用于简化数据类的定义
from dataclasses import dataclass, field


@dataclass
class ShortTermMemory:
    """
    基于 deque 的滑动窗口短期记忆。

    保留最近 window_size 条对话消息，超出的自动丢弃。

    === 工作原理 ===
    deque(maxlen=3) 就像一个最多能放 3 个球的管子：
    放第 4 个球时，第 1 个球自动从另一端滚出去。

    Attributes:
        window_size: 最大保留的消息条数（窗口大小）。
    """

    window_size: int = 20

    # field(default_factory=...) 在每次创建实例时调用 lambda 生成新 deque
    # 不能直接写 default=deque(maxlen=20)，因为所有实例会共享同一个 deque
    # lambda: deque(maxlen=20) 每次调用都创建一个新的 deque
    _messages: deque = field(default_factory=lambda: deque(maxlen=20))

    def __post_init__(self) -> None:
        """
        dataclass 初始化后的钩子方法。

        当 window_size 被设置为非默认值 20 时，
        需要重新创建一个正确 maxlen 的 deque。
        """
        if self.window_size != 20:
            self._messages = deque(maxlen=self.window_size)

    def add(self, role: str, content: str) -> None:
        """
        添加一条消息到记忆。

        Args:
            role: 消息角色，如 "user"（用户）或 "assistant"（AI）。
            content: 消息内容文本。
        """
        # 把消息存成字典格式（和 OpenAI API 的 messages 格式一致）
        self._messages.append({"role": role, "content": content})

    def get_all(self) -> list[dict]:
        """
        返回所有消息（按时间顺序）。

        Returns:
            消息列表，例如：
            [{"role": "user", "content": "你好"},
             {"role": "assistant", "content": "你好！"}]
        """
        # list(deque) 把 deque 转换成普通列表返回
        return list(self._messages)

    def clear(self) -> None:
        """清空短期记忆。"""
        self._messages.clear()

    def __len__(self) -> int:
        """
        返回当前消息数量。

        实现 __len__ 后，可以用 len(memory) 获取消息数，
        也能用 if memory: 判断是否有消息。
        """
        return len(self._messages)
