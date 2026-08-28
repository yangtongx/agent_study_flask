# 本学习项目速查

## 怎么启动

- 命令行：`python main.py "你的问题"`
- HTTP：`python server.py`，默认端口 **8000**

## 两个后端

`.env` 里的 `AGENT_BACKEND`：

- `handmade`：手写 ReAct，自己解析 Thought / Action / Final Answer
- `agentscope`：AgentScope 2.0 官方 Agent，原生 function calling

## 四个专家

主管会把任务分给：math_agent（计算器）、writer_agent（改写）、knowledge_agent（知识库）、general_agent（闲聊）。

问文档、制度、本项目说明时，应该找 knowledge_agent。
