"""
程序入口 — 快速启动 Agent 并执行一轮对话。

=== 这个文件做什么？===
当你运行 `python main.py` 时，程序从这里开始执行。
它会：
1. 读取你在命令行输入的文字（或交互式输入）
2. 创建一个 CoordinatorAgent（主 Agent，内部再调度子 Agent）
3. 把你的输入交给 Agent 处理
4. 打印 Agent 的回复

=== 什么是 asyncio？===
Python 的异步编程库。Agent 调用 LLM API 时需要等待网络响应，
用 async/await 可以在等待时做其他事，不浪费时间。
"""

# asyncio 是 Python 标准库，用于编写异步并发代码
import asyncio

# sys 用于读取命令行参数（sys.argv）
import sys

# 主 Agent：把任务分给数学 / 写作 / 通用子 Agent
from src.agents.coordinator_agent import CoordinatorAgent

# 从工具模块导入日志函数，用于打印调试信息
from src.utils.logger import get_logger

# 创建当前模块的 logger，__name__ 是当前文件名（main）
logger = get_logger(__name__)


async def main(user_input: str | None = None) -> None:
    """
    启动 Agent，处理用户输入并输出响应。

    这是整个程序的入口函数，用 async def 定义因为它内部要调用异步的 agent.run()。

    Args:
        user_input: 用户输入文本。如果为 None，则从命令行读取。
                    你也可以在调用 main() 时直接传入文本，比如 main("你好")。
    """
    # 如果调用时没有传入 user_input，就从命令行或交互式输入获取
    if user_input is None:
        # sys.argv 是命令行参数列表
        # 例如运行 `python main.py 你好世界`，则 sys.argv = ['main.py', '你好', '世界']
        # sys.argv[1:] 取从第 2 个开始的所有参数
        if len(sys.argv) > 1:
            # 用空格把多个参数拼成一句话
            user_input = " ".join(sys.argv[1:])
        else:
            # 没有命令行参数，就交互式读取用户输入
            # input() 会阻塞等待用户在终端输入文字并按回车
            user_input = input("🧑 You: ").strip()  # .strip() 去除首尾空格

            # 如果用户直接按回车，输入为空，就退出
            if not user_input:
                logger.warning("Empty input, exiting.")
                return

    # 记录日志：把用户输入的前 100 个字符打印出来，方便调试
    # %s 是日志格式化占位符，会被 user_input[:100] 替换
    logger.info("Starting agent with input: %s", user_input[:100])

    # 创建主 Agent。内部会带上三个子 Agent（数学、写作、通用）
    agent = CoordinatorAgent()

    # 调用 agent 的 run 方法处理用户输入
    # await 表示等待异步操作完成（agent 内部会调用 LLM API）
    result = await agent.run(user_input)

    # 打印最终结果
    print(f"\n🤖 Agent: {result}")


# 这是 Python 的标准入口模式
# __name__ == "__main__" 表示这个文件是被直接运行的（而不是被 import 的）
# asyncio.run() 创建一个事件循环并运行 main() 协程直到完成
if __name__ == "__main__":
    asyncio.run(main())
