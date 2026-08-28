"""记忆系统单元测试。"""

from src.memory.short_term import ShortTermMemory


def test_short_term_add_and_get():
    """测试添加和获取消息。"""
    mem = ShortTermMemory(window_size=5)
    mem.add("user", "hello")
    mem.add("assistant", "hi there")

    msgs = mem.get_all()
    # 应该有 2 条消息
    assert len(msgs) == 2
    # 第一条是用户消息
    assert msgs[0]["role"] == "user"
    # 第二条是 AI 消息
    assert msgs[1]["role"] == "assistant"


def test_short_term_window():
    """
    测试窗口溢出。

    窗口大小为 3，存 5 条消息后应该只保留最后 3 条。
    """
    mem = ShortTermMemory(window_size=3)
    for i in range(5):
        mem.add("user", f"msg{i}")

    msgs = mem.get_all()
    # 只保留 3 条
    assert len(msgs) == 3
    # 最旧的是 msg2（msg0 和 msg1 被挤出了）
    assert msgs[0]["content"] == "msg2"


def test_short_term_clear():
    """测试清空记忆。"""
    mem = ShortTermMemory()
    mem.add("user", "test")
    mem.clear()
    # 清空后长度应该是 0
    assert len(mem) == 0
