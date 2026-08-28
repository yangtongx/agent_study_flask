"""
输出安全过滤 — 敏感信息脱敏。

=== 什么是脱敏？===
如果 AI 在回复中输出了用户的邮箱、手机号、身份证号，
可能造成隐私泄露。脱敏就是把这些信息替换成 [EMAIL]、[PHONE] 等标记。

例如：
  原文: "你的邮箱是 zhangsan@qq.com，手机是 13800138000"
  脱敏: "你的邮箱是 [EMAIL]，手机是 [PHONE]"

=== 实现方式 ===
用正则表达式匹配各种敏感信息的模式，找到后替换成掩码标记。
"""

from __future__ import annotations

import re

from src.utils.logger import get_logger

logger = get_logger(__name__)


# =====================================================================
# 敏感信息正则模式
# =====================================================================
# 每个模式是一个 (正则, 替换文本) 的元组
_SENSITIVE_PATTERNS = {
    # 邮箱：匹配 xxx@xxx.xxx 格式
    "email": (r"[\w.-]+@[\w.-]+\.\w+", "[EMAIL]"),
    # 手机号：匹配 1 开头的 11 位数字（中国大陆手机号）
    "phone": (r"\b1[3-9]\d{9}\b", "[PHONE]"),
    # 身份证号：18 位数字（最后一位可能是 X）
    "id_card": (r"\b\d{17}[\dXx]\b", "[ID_CARD]"),
    # API Key：匹配 sk- 开头的长字符串（OpenAI Key 格式）
    "api_key": (r"sk-[a-zA-Z0-9]{20,}", "[API_KEY]"),
}


class OutputFilter:
    """
    输出安全过滤器。

    对 Agent 输出做敏感信息脱敏。
    """

    def __init__(self) -> None:
        """编译所有敏感信息正则。"""
        self._patterns = {
            # 对每个模式：编译正则，并保留对应的替换标记
            name: (re.compile(pat, re.IGNORECASE), mask)
            for name, (pat, mask) in _SENSITIVE_PATTERNS.items()
        }

    def sanitize(self, text: str) -> str:
        """
        脱敏处理。

        遍历所有敏感信息模式，在文本中找到后替换成掩码标记。

        Args:
            text: 原始文本。

        Returns:
            脱敏后的文本。
        """
        for name, (pattern, mask) in self._patterns.items():
            # 先检查有没有匹配
            if pattern.search(text):
                # 统计匹配数量，用于日志
                count = len(pattern.findall(text))
                logger.info("Output: %d %s(s) masked", count, name)
                # 执行替换：把所有匹配项替换成掩码标记
                text = pattern.sub(mask, text)
        return text
