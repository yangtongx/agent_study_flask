"""
HTTP 服务入口 — 启动 Agent API 服务。

=== 这个文件做什么？===
创建 Flask 应用，注册路由，启动 HTTP 服务。
启动后其他系统就可以通过 HTTP 调用 Agent。

=== 启动方式 ===
    python server.py

=== 启动后可访问 ===
    http://localhost:8000/          → API 信息
    http://localhost:8000/health    → 健康检查
    http://localhost:8000/docs      → 接口说明（JSON）
    POST http://localhost:8000/chat → 调用 Agent
"""

from flask import Flask

from src.api.routes import bp
from src.utils.logger import get_logger

logger = get_logger(__name__)


def create_app() -> Flask:
    """
    创建 Flask 应用并挂上 API 路由。

    抽成函数是为了方便测试：测试里也能拿到同一个 app。
    """
    application = Flask(__name__)
    application.register_blueprint(bp)
    return application


# 模块级 app：python server.py 和 测试 from server import app 都用它
app = create_app()


if __name__ == "__main__":
    # Flask 内置开发服务器
    # host="0.0.0.0" → 监听所有网卡（允许局域网访问）
    # port=8000      → 浏览器访问 http://localhost:8000
    # debug=True     → 代码改动后自动重启；出错时显示调试页（只适合学习/开发）
    logger.info("Agent API server starting on http://0.0.0.0:8000 ...")
    app.run(host="0.0.0.0", port=8000, debug=True)
