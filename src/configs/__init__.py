"""
Configs 模块 — 配置加载与校验。

=== 为什么需要配置中心？===
项目有很多参数：API Key、模型名、记忆窗口大小等。
如果把这些写死在代码里，每次改都要改代码重新部署。
用配置文件统一管理，改配置不用改代码。

配置来源（优先级从高到低）：
1. 环境变量（最高优先级）
2. .env 文件
3. 代码中的默认值
"""

from src.configs.settings import get_settings

__all__ = ["get_settings"]
