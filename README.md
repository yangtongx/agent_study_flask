# Study Agent — 给初学者的说明

这份 README 按「先懂词，再看代码」来写。就先假设你是纯小白，不懂 Agent、ReAct 或 Flask这些东西。我就先按照专有名词用白话说一遍，再对到文件。

clone 之后默认在 **main**：一个 Agent，工具是计算器、网页搜索、按 URL 读正文。学完这里再按 [第 4 节](#4-建议阅读顺序) 切后面的分支。git 的提交顺序和学习顺序不一样。

## 目录

1. [这项目是干什么的](#1-这项目是干什么的)
2. [先记住这几个词](#2-先记住这几个词)
3. [用一个例子看 Agent](#3-用一个例子看-agent)
4. [建议阅读顺序](#4-建议阅读顺序)
5. [项目地图](#5-项目地图)
6. [一次对话走了哪些代码](#6-一次对话走了哪些代码)
7. [怎么启动](#7-怎么启动)
8. [环境变量](#8-环境变量)
9. [HTTP API](#9-http-api)
10. [记忆：Agent 怎么记住说过的话](#10-记忆agent-怎么记住说过的话)
11. [工具：Agent 怎么动手](#11-工具agent-怎么动手)
12. [LLM 客户端：请求怎么发出去](#12-llm-客户端请求怎么发出去)
13. [配置、日志、异常](#13-配置日志异常)
14. [写了但还没接到主流程的模块](#14-写了但还没接到主流程的模块)
15. [怎么加新能力](#15-怎么加新能力)
16. [怎么跑测试](#16-怎么跑测试)
17. [常见问题](#17-常见问题)
18. [名词和文件对照](#18-名词和文件对照)

## 1. 这项目是干什么的

这是一个用来学 Agent 的项目。你现在看到的是第一阶：一个 Agent、手写 ReAct。后面还有多 Agent、RAG，以及选修的 AgentScope。切分支的方法在第 4 节。

普通聊天机器人是你问一句，模型直接回一句。

这里多几步：

1. **想**（Thought）：这件事要不要用工具？
2. **做**（Action）：比如调用计算器算 `15 * 23`
3. **看结果**（Observation）：计算器返回 `345`
4. **给最终答案**（Final Answer）：告诉你 `15 * 23 = 345`

「先推理、再行动」这种循环叫 **ReAct**（Reasoning + Acting）。

可以在命令行聊：

```powershell
python main.py "15乘23等于多少"
```

也可以当成 HTTP 服务，给网页或别的程序调用：

```powershell
python server.py
```

HTTP 这一层用的是 **Flask**：把 Agent 包成网址，别人用 POST 就能调用。

## 2. 先记住这几个词

| 词 | 白话 |
|---|---|
| **LLM** | Large Language Model，大语言模型。ChatGPT、DeepSeek 这类能生成文字的模型。本项目默认对接 **DeepSeek**，接口格式和 OpenAI 兼容。 |
| **Agent（智能体）** | 不只会说话，还会自己决定要不要调用工具。 |
| **ReAct** | 一种工作方式：Thought → Action → Observation，循环到给出 Final Answer。 |
| **Tool（工具）** | Agent 的手。这里有计算器 `calculator`、搜索 `web_search`、读网页 `fetch`。 |
| **Memory（记忆）** | 对话历史。没有记忆，下一句就忘了你刚才说什么。 |
| **session_id** | 一次对话的编号。同一个 `session_id` 就是同一段聊天记录。 |
| **Prompt（提示词）** | 发给模型的说明：你是谁、有哪些工具、必须按什么格式回答。 |
| **API** | 程序之间互相调用的接口。这里用 HTTP：发一个 POST，Agent 就开始干活。 |
| **Flask** | Python 写 HTTP 服务的框架。`server.py` 用它。资料多，适合入门。 |
| **Blueprint** | Flask 里「一组路由打成一包」。`/chat`、`/health` 写在 Blueprint 里，再挂到 app 上。 |
| **PostgreSQL（PG）** | 关系型数据库。对话历史存到硬盘上，服务重启后还在。连不上也能跑，会自动改成只放内存。 |
| **异步（async / await）** | 调模型要等网络。`await` 的意思是先去等结果，别把整个程序卡死。 |
| **抽象基类（ABC）** | 一份合同：子类必须实现某些方法。例如所有工具都要有 `name`、`description`、`run()`。 |

## 3. 用一个例子看 Agent

把 Agent 想成一个会用计算器的助手：

```text
你：15 乘 23 等于多少？

助手心里想（Thought）：这是算术，心算可能错，去用计算器。
助手动手（Action）：按计算器 15 * 23
计算器显示（Observation）：345
助手回答（Final Answer）：15 * 23 = 345
```

对应到 `src/core/agent_loop.py` 里的循环：

```text
用户输入
   ↓
[Decide]  把对话发给 LLM，LLM 输出 Thought + Action，或 Final Answer
   ↓
是 Final Answer？ → 是 → 返回给用户，结束
   ↓ 否
[Act]     解析 Action[calculator](15 * 23)，调用 CalculatorTool
   ↓
[Observe] 把 "15 * 23 = 345" 塞回对话，再问 LLM 一次
   ↓
重复，最多 10 轮（防止死循环）
```

模型不会真的去按计算器。它只按约定格式写出：

```text
Thought: 需要计算
Action[calculator](15 * 23)
```

真正算数的是 Python 里的 `CalculatorTool.run()`。模型负责决定，代码负责执行。

## 4. 建议阅读顺序

### 4.1 整个仓库怎么学

分支的创建顺序是：`main` → 多 Agent → AgentScope → RAG。学习不要按这个顺序。AgentScope 是把循环换成官方框架，比「再加一个检索工具」跳得大。

| 阶 | 要搞懂的 | 怎么切 | 到了之后看什么 |
|---|---|---|---|
| 1 | 一个 Agent、ReAct 怎么转 | 你已经在这（`main`） | 本 README，以及下面的读文件表 |
| 2 | 主管分活；子 Agent 也是工具 | `git checkout feature/multi-agent` | 那个分支的 README |
| 3 | 再多一只手：翻知识库（RAG） | `git checkout feature/rag` | 那个分支 README 的 RAG 一节 |
| 4 | （选修）同一套分工，换官方框架 | 仍留在 `feature/rag`，`.env` 里 `AGENT_BACKEND=agentscope` | 那个分支 README 的 AgentScope 一节 |

`git checkout` 提示没有这个分支时，先 `git fetch` 再切。

不必把每个历史分支都跑一遍：`feature/rag` 里已经包含多 Agent、RAG 和 AgentScope 的代码。先在 `main` 把手写 ReAct 看懂，再切 `feature/rag` 或 `feature/agentscope-2`。切到 `feature/rag` 后先保持 `AGENT_BACKEND=handmade`，学完 RAG 再选修 AgentScope。

### 4.2 本分支先读哪些文件

按这个顺序读，每读一个文件多懂一层：

| 顺序 | 文件 | 读完能弄清 |
|---|---|---|
| 1 | 本 README | 全貌 |
| 2 | `main.py` | 命令行怎么启动一轮对话 |
| 3 | `server.py` | HTTP 服务怎么起来 |
| 4 | `src/core/agent_loop.py` | ReAct 循环怎么转 |
| 5 | `src/tools/calculator.py` | 一个工具长什么样 |
| 6 | `src/agents/react_agent.py` | Agent 外壳：组装 LLM、工具、记忆 |
| 7 | `src/llm/openai_client.py` | 消息怎么发给 DeepSeek |
| 8 | `src/memory/manager.py` | 记忆怎么存、怎么读 |
| 9 | `src/api/routes.py` | `/chat` 怎么接到 Agent |

源码里多数文件顶部有「这个文件做什么」的中文注释，可以对着看。

## 5. 项目地图

```text
agent_study_flask/
├── main.py                 命令行入口：python main.py "你的问题"
├── server.py               HTTP 入口：python server.py（端口 8000）
├── pyproject.toml          项目名、依赖、Python 版本
├── .env.example            环境变量模板（复制成 .env 再填密钥）
├── .env                    真正生效的配置（不要提交到 Git）
│
├── src/                    业务代码
│   ├── agents/             Agent：ReactAgent 继承 BaseAgent
│   ├── core/               循环：AgentState + StateGraph（perceive → decide → act）
│   ├── llm/                怎么调用大模型
│   ├── tools/              计算器、网络搜索、fetch
│   ├── memory/             短期记忆 + 长期记忆（长期还是空壳）
│   ├── database/           PostgreSQL：把对话存进数据库
│   ├── api/                Flask 路由和请求/响应格式
│   ├── configs/            从 .env 读配置
│   ├── safety/             输入过滤、输出脱敏（代码有了，主流程还没接上）
│   ├── cache/              LLM 响应缓存（代码有了，主流程还没接上）
│   ├── prompts/            提示词：system.md / examples.md / task.md / retry.md
│   └── utils/              日志、自定义异常
│
├── tests/                  自动化测试
│   ├── unit/               测单个模块（用假 LLM，不花 API 钱）
│   └── integration/        测模块组合、测 HTTP 接口
│
└── docs/                   偏开发者的短文档（架构、Python 接口）
```

### 5.1 两个入口

| 入口 | 命令 | 适合 |
|---|---|---|
| `main.py` | `python main.py "15*23等于多少"` | 自己在终端里试 |
| `server.py` | `python server.py` | 给网页、Postman、别的程序调用 |

命令行每次 `ReactAgent()` 都是新的 `session_id`，记不住上一次命令行对话。HTTP 可以用同一个 `session_id` 把多轮串起来。

### 5.2 类之间的关系

```text
你（用户 / HTTP 调用方）
        │
        ▼
  main.py  或  server.py → routes.py
        │
        ▼
   ReactAgent.run(用户那句话)
        │
        ▼
   AgentLoop.execute(...)          ← 真正转圈的地方（LangGraph StateGraph）
        │
        ├── AgentState（messages / iteration / final_answer）
        ├── LLMFactory.create() → OpenAIClient.chat()
        ├── CalculatorTool.run()
        └── MemoryManager
                 ├── ShortTermMemory（内存，最近 N 条）
                 └── ChatHistoryRepo（PostgreSQL，持久化）
```

`ReactAgent` 是外壳：把零件拼好。`AgentLoop` 是转圈的地方：按 ReAct 一轮一轮跑。

## 6. 一次对话走了哪些代码

以 HTTP 为例：`POST /chat`，body 是 `{"message": "15 * 23 等于多少"}`。

```text
1. Flask 收到请求
2. Pydantic 的 ChatRequest 校验：message 不能空，最长 10000 字
3. routes.chat()
      - 没传 session_id → 自动生成一个 UUID
      - get_or_create_agent(session_id) → 没有就新建 ReactAgent
4. asyncio.run(agent.run(message))
      - Flask 路由是同步的，Agent 内部是异步的，所以包一层 asyncio.run
      - 内部调用 loop.execute(message)
5. AgentLoop.execute()
      a. 准备一份空的 AgentState（LangGraph 的共享状态）
      b. perceive：ChatPromptTemplate 拼 messages，经 reducer 写入 State
      c. decide：读 State["messages"] 调 LLM，只 return 新增的 assistant 消息
      d. 条件边看 State：
            ├─ final_answer 有值 → 结束，存记忆
            ├─ 匹配到 Action → act 跑工具，Observation 再追加进 messages
            ├─ 格式不完整 → retry 追加纠错提示
            └─ 轮次用尽仍无答案 → MaxIterationsError → HTTP 508
      节点不要原地 messages.append。return {"messages": [新消息]}，
      由 append_messages 这个 reducer 合并。
6. 返回 JSON：
      { "answer": "...", "agent": "ReactAgent", "iterations": 2, "session_id": "..." }
```

命令行更短：`main.py` 直接 `ReactAgent().run(...)`，不经过 Flask，也没有多 session 复用。

## 7. 怎么启动

### 7.1 准备环境

需要 **Python 3.11+**。在项目根目录（有 `pyproject.toml` 的那一层）打开终端：

```powershell
# 1. 创建虚拟环境，避免把包装进系统 Python
python -m venv venv

# 2. 激活（Windows PowerShell）
.\venv\Scripts\Activate.ps1

# Linux / macOS：
# source venv/bin/activate

# 3. 安装本项目。-e 是可编辑安装，改 src 立刻生效
pip install -e ".[dev]"

# 4. 复制配置模板，填自己的密钥
copy .env.example .env
# 用编辑器打开 .env，把 LLM_API_KEY 改成你的 DeepSeek Key
```

PowerShell 若提示「无法加载，因为在此系统上禁止运行脚本」，先执行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

再重新激活虚拟环境。

### 7.2 命令行

```powershell
python main.py "15乘23等于多少"
```

没有参数时会等你输入：

```text
🧑 You:
```

成功时大致是：

```text
🤖 Agent: 15 * 23 = 345
```

### 7.3 HTTP 服务

```powershell
python server.py
```

| 地址 | 作用 |
|---|---|
| http://localhost:8000/ | 服务简介 |
| http://localhost:8000/health | 健康检查（含数据库是否连上） |
| http://localhost:8000/docs | 接口说明（JSON） |
| `POST http://localhost:8000/chat` | 聊天 |

`debug=True`：出错时显示调试页，只适合自己学习，不要暴露到公网。`use_reloader=False`：改了 Python 代码不会自动重启，要自己停掉再开。Windows 上如果开着 reloader，会多一个子进程，两个进程抢 8000 端口。

## 8. 环境变量

配置在 `.env`，由 `src/configs/settings.py` 读取。优先级：**系统环境变量 > `.env` > 代码里的默认值**。

Python 里字段名是小写，环境变量是大写。例如 `llm_api_key` 对应 `LLM_API_KEY`。

| 变量 | 含义 | 典型值 |
|---|---|---|
| `LLM_API_KEY` | 大模型密钥，必须改成你自己的 | `sk-你的密钥` |
| `LLM_BASE_URL` | API 地址 | `https://api.deepseek.com/v1` |
| `LLM_MODEL` | 模型名 | `deepseek-v4-flash` |
| `AGENT_MAX_ITERATIONS` | ReAct 最多转几圈 | `10` |
| `AGENT_MEMORY_WINDOW` | 短期记忆最多留几条消息 | `20` |
| `AGENT_DEBUG` | 是否打更详细的日志 | `true` |
| `PG_URI` | PostgreSQL 连接串 | `postgresql://用户:密码@主机:5432/库名` |
| `CHROMA_PERSIST_PATH` | 向量库路径（长期记忆预留） | `./data/chroma` |
| `LANGSMITH_TRACING` | 是否把 LangGraph 节点上传到 LangSmith | `false` |
| `LANGSMITH_API_KEY` | LangSmith 密钥，在 [Settings](https://smith.langchain.com/settings) 创建 | `lsv2_pt_...` |
| `LANGSMITH_PROJECT` | 网页上的项目名 | `agent-study-flask` |

DeepSeek 的接口和 OpenAI Chat Completions 格式兼容，所以类名叫 `OpenAIClient`，实际可以连 DeepSeek。换别的兼容服务时，通常只改 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。

要在 LangSmith 里看节点：`.env` 里 `LANGSMITH_TRACING=true` 并填入 Key，重启 `server.py`，再发一轮 `/chat`。打开 [smith.langchain.com](https://smith.langchain.com)，进项目 `agent-study-flask`，点那条 Trace。应能看到 `perceive` → `decide` → `act`（计算器）→ `decide`。账号若在欧盟，还要设 `LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com`。

PostgreSQL 不是必须的。连不上时，记忆只在内存里，进程一关就没了。`/health` 里 `database` 会显示 `unavailable`，聊天仍可使用。

`get_settings()` 带了缓存，整个进程只读一次 `.env`。改完配置要重启。

## 9. HTTP API

### `GET /`

返回服务名字和有哪些接口。

### `GET /health`

```json
{
  "status": "ok",
  "agent": "ReactAgent",
  "database": "connected"
}
```

`database` 可能是 `connected` 或 `unavailable`。

### `POST /chat`

请求：

```json
{
  "message": "15 * 23 等于多少",
  "session_id": "可选，不传会自动生成"
}
```

成功响应：

```json
{
  "answer": "Thought: 需要计算。\nThought: 已经得到结果。\n\n15 * 23 = 345",
  "agent": "ReactAgent",
  "iterations": 2,
  "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

`answer` 前面带本轮的 Thought，后面才是最终答案。写入记忆的仍是纯答案，避免下一轮把推理过程当成说过的话。

`iterations` 是这次为了得出答案，模型被调用了几轮。算一道题通常是 2：第一轮调计算器，第二轮给出 Final Answer。

多轮对话把上一次返回的 `session_id` 原样传回去。同一个会话复用同一个 Agent，并带上历史消息。

```powershell
# 第一轮
Invoke-RestMethod -Method POST -Uri http://localhost:8000/chat `
  -ContentType "application/json" `
  -Body '{"message":"15*23等于多少"}'

# 第二轮（把 session_id 换成上一次返回的值）
Invoke-RestMethod -Method POST -Uri http://localhost:8000/chat `
  -ContentType "application/json" `
  -Body '{"message":"再乘以2呢","session_id":"这里填上一次的id"}'
```

| 状态码 | 含义 |
|---|---|
| 422 | `message` 为空或超长 |
| 500 | 内部错误。常见原因：API Key 无效、网络不通 |
| 508 | 转了 10 圈还没有 Final Answer |

请求和响应的字段在 `src/api/models.py`，用 Pydantic 校验。

## 10. 记忆：Agent 怎么记住说过的话

分三层，目前真正在用的是前两层：

```text
MemoryManager
 ├── ShortTermMemory     内存里的滑动窗口（deque），默认最近 20 条
 ├── PostgreSQL          持久化，重启后按 session_id 把历史装回内存
 └── LongTermMemory      预留：以后用向量库做语义搜索，现在是空壳
```

为什么既要内存又要数据库：

- 每次问模型都从数据库读，会慢。
- 内存里放最近一段，读起来快。
- 数据库负责关服务也不丢。PG 挂了就只走内存，不把整个 Agent 弄挂。

窗口是什么：模型一次能吃的文字有上限，所以只保留最近 N 条。默认 20。第 21 条进来时，最早那条被挤掉（`collections.deque(maxlen=20)`）。

和 `session_id` 的关系：

- HTTP：`get_or_create_agent(session_id)` 按会话缓存 Agent。
- 同一 `session_id` 是同一份记忆。
- 不同 `session_id` 互不干扰。
- 命令行的 `ReactAgent()` 每次新建，等于每次新开一个会话。

相关文件：

- `src/memory/manager.py`：调度
- `src/memory/short_term.py`：内存窗口
- `src/memory/long_term.py`：占位，还没接 ChromaDB
- `src/database/connection.py`：连接池、建表
- `src/database/chat_history.py`：增删查对话记录

表 `chat_history` 大致是：`session_id`、`role`（user / assistant）、`content`、`iterations`、`created_at`。

## 11. 工具：Agent 怎么动手

所有工具都继承 `BaseTool`，必须提供：

1. `name`：英文名，对应模型写的 `Action[这个名字](...)`
2. `description`：出现在 system prompt 里，模型靠它决定该不该用
3. `run(args)`：真正执行，返回字符串，作为 Observation

目前有三个：

- `CalculatorTool`（`calculator`）：安全算术，不用 `eval()`。
- `WebSearchTool`（`web_search`）：默认走 360 搜索，没有有效结果再用必应中国。搜到链接后会 fetch 前几篇正文。
- `FetchTool`（`fetch`）：对一个 http 或 https 链接做 GET，把 HTML 收成纯文本。

百度、搜狗对脚本会出验证码页，不能当搜索结果用。

计算器不用 Python 的 `eval()`。`eval` 能执行任意代码。这里把 `"2 + 3 * 4"` 解析成语法树（AST），只允许 `+ - * / // % **` 和正负号。遇到函数调用、`import` 就拒绝。

搜索用项目里的 `httpx` 拉搜索页，再解析标题和链接。`run()` 是 async，真正发请求放在 `asyncio.to_thread` 里。测试里替换 `_search`，不会真的上网。

`AgentLoop` 找工具的方式很直接：遍历 `self.tools`，名字对上就 `await tool.run(args)`。工具不存在或执行失败时，不把整个请求打成 500，而是把错误字符串当作 Observation 还给模型，让它换个做法。

## 12. LLM 客户端：请求怎么发出去

```text
AgentLoop 只认识 BaseLLMClient（抽象接口）
        │
        ▼
LLMFactory.create("openai")  →  new OpenAIClient()
        │
        ▼
OpenAIClient 用 httpx 发 POST
  {base_url}/chat/completions
  Header: Authorization: Bearer {api_key}
  Body: { model, messages, temperature }
```

这是工厂模式：换模型时，新增一个 `XxxClient`，在工厂里加一行，不必改 `AgentLoop`。当前工厂里只注册了 `"openai"`。DeepSeek 走的就是这条路。

`messages` 的格式：

```python
[
  {"role": "system", "content": "你是谁、有什么工具、怎么输出"},
  {"role": "user", "content": "用户的话"},
  {"role": "assistant", "content": "模型上一轮说的"},
  {"role": "user", "content": "Observation: 工具结果"},
]
```

`temperature` 默认 0.7。越大越随机，越小越固定。

## 13. 配置、日志、异常

### 配置

`get_settings()` 带 `@lru_cache`：整个进程只读一次 `.env`，到处拿到的是同一份配置。

### 日志

`src/utils/logger.py` 用 `rich` 给日志上色。每个模块通常这样写：

```python
from src.utils.logger import get_logger
logger = get_logger(__name__)
```

级别从低到高：DEBUG → INFO → WARNING → ERROR。开发时看 DEBUG，能看见第几轮循环、调了哪个工具。

### 异常

`src/utils/exceptions.py`：

```text
AgentError
 ├── AgentLoopError → MaxIterationsError   转圈太多
 ├── LLMError                              调模型失败
 ├── ToolError                             工具失败
 └── MemoryError                           记忆出错
```

HTTP 层把 `MaxIterationsError` 变成 508，其它未捕获异常变成 500。

## 14. 写了但还没接到主流程的模块

读代码时容易把「有这个文件」理解成「已经在用」。下面这些，当前对话路径不会自动走到：

| 模块 | 现状 |
|---|---|
| `src/safety/input_filter.py` | 能检测常见 Prompt Injection（如 “ignore previous instructions”）。`AgentLoop` 和 `routes` 没有调用它 |
| `src/safety/output_filter.py` | 能把邮箱、手机号、身份证、`sk-` 密钥打成 `[EMAIL]` 等。主流程没接 |
| `src/cache/response_cache.py` | 相同 messages 可缓存模型回复。`OpenAIClient` 没接 |
| `src/memory/long_term.py` | 向量长期记忆的接口，返回空列表或 `"stub-id"` |

这些是预留的扩展点。想练手的话，可以把 InputFilter、OutputFilter、ResponseCache 接到 `AgentLoop` 或 `routes` 上。

`docs/architecture.md` 画的依赖关系偏「打算接上之后的样子」，和此刻的真实调用链不完全一致。以本 README 第 5、6 节为准。

## 15. 怎么加新能力

### 加一个新工具（例如查天气）

1. 在 `src/tools/` 新建文件，继承 `BaseTool`。
2. 实现 `name`、`description`、`run`。
3. 把它加进 `src/tools/__init__.py` 的 `default_tools()`。命令行（`react_agent.py`）和 HTTP（`routes.py`）都从这里取工具列表。

`description` 要写清干什么、参数长什么样，否则模型不知道什么时候该调用。

### 加一种新的模型客户端

1. 新建 `src/llm/xxx_client.py`，实现 `BaseLLMClient.chat()`。
2. 在 `LLMFactory.create()` 的 `providers` 字典里注册名字。

### 换提示词

改 `src/prompts/` 下的 markdown，不必改循环代码。

消息列表用 LangChain 的 `ChatPromptTemplate.from_messages` 拼出来，再交给 LangGraph 的 `AgentState`（`src/core/state.py`）在节点之间传递。顺序是 system（人设 + 工具 + few-shot）、历史占位、human（当前输入）。

图只用 LangGraph 管 State，不用 LangChain 自带的 Agent。Thought / Action / Observation 仍按 ReAct 写在节点里。

| 文件 | 作用 |
|---|---|
| `system.md` | 人设、工具列表占位符 `{tool_descriptions}`、输出格式 |
| `examples.md` | few-shot 示例，会拼进 system 消息 |
| `task.md` | 包装当前这一轮用户输入 |
| `retry.md` | 模型没按 ReAct 格式输出时的纠错提示 |

## 16. 怎么跑测试

```powershell
# 先激活 venv，并装过 dev 依赖
pytest
```

测试不会真的去调 DeepSeek，那样又慢又花钱。它们用假的模型：

- 第一轮固定返回 `Action[calculator](15 * 23)`
- 第二轮固定返回 `Final Answer: 15 * 23 = 345`
- 计算器是真的，所以能验证「解析 Action → 执行工具 → 给出答案」整条链

搜索相关测试替换了 `_search`，不会访问外网。

主要文件：

- `tests/unit/test_state.py`：AgentState 与 messages reducer
- `tests/unit/test_prompts.py`：ChatPromptTemplate 组装消息
- `tests/unit/test_agent_loop.py`：立刻给答案，以及超时抛错
- `tests/unit/test_tools.py`：计算器
- `tests/unit/test_memory.py`：短期记忆窗口
- `tests/integration/test_agent_e2e.py`：Loop + 真计算器 + 假 LLM
- `tests/integration/test_api.py`：HTTP `/`、`/health`、`/chat`

## 17. 常见问题

**问：为什么 Agent 是 async，Flask 路由却是普通函数？**  
调用模型适合用 async 等网络。经典 Flask 视图是同步函数。所以在 `/chat` 里用 `asyncio.run(agent.run(...))` 把这一次异步循环跑完。对入门来说，这比先上 ASGI 服务器更直观。

**问：`python main.py` 没反应，或报 API 错误？**  
检查 `.env` 里 `LLM_API_KEY` 是不是还是 `sk-xxx`，以及网络能否访问 `LLM_BASE_URL`。

**问：`/health` 显示 database unavailable？**  
PostgreSQL 没连上。聊天还能用，只是重启后对话历史会丢。按 `PG_URI` 检查账号、主机、防火墙。

**问：为什么有时不调用计算器，直接口算？**  
模型不保证每次都按提示词来。简单加减它可能自己算；复杂表达式更常去用工具。

**问：为什么最多 10 轮？**  
如果模型一直输出 Action 却不给 Final Answer，循环不会自己停。`max_iterations` 是上限，到了就抛 `MaxIterationsError`。

**问：命令行第二句为什么不记得第一句？**  
每次运行 `main.py` 都是新进程、新 `ReactAgent`、新 `session_id`。要用记忆，走 HTTP，并固定 `session_id`。

**问：代码里又是 OpenAI 又是 DeepSeek？**  
HTTP 协议按 OpenAI Chat Completions 来写，默认配置指向 DeepSeek。换兼容该协议的其它厂商，改 `.env` 即可。

**问：改了代码，服务为什么不自动重启？**  
`server.py` 里 `debug=True` 只打开调试页，`use_reloader=False` 关掉了自动重载。改完自己停掉再运行 `python server.py`。

**问：LangSmith 里看不到 perceive / decide / act？**  
`.env` 里 `LANGSMITH_TRACING` 必须是 `true`，`LANGSMITH_API_KEY` 不能空。改完重启服务再聊一轮。打开 https://smith.langchain.com ，选项目 `LANGSMITH_PROJECT`（默认 `agent-study-flask`），点那条 Trace。没装上依赖时执行 `pip install -e ".[dev]"`。

**问：仓库里还有 `feature/multi-agent`、`feature/rag`，该怎么切？**  
见第 4 节。先把 `main` 看懂，再切 `feature/multi-agent`，然后 `feature/rag`。不要按 git 提交时间去先看 AgentScope。`feature/rag` 里虽然也有 AgentScope，先学 RAG，`.env` 保持 `handmade`。

## 18. 名词和文件对照

| 说法 | 文件 |
|---|---|
| 命令行入口 | `main.py` |
| HTTP 入口 | `server.py` |
| 聊天接口 | `src/api/routes.py` |
| 请求 JSON 长什么样 | `src/api/models.py` |
| Agent 外壳 | `src/agents/react_agent.py` |
| Agent 必须实现 `run()` | `src/agents/base_agent.py` |
| ReAct 循环 | `src/core/agent_loop.py` |
| 调大模型 | `src/llm/openai_client.py` |
| 创建 LLM 客户端 | `src/llm/factory.py` |
| 计算器 | `src/tools/calculator.py` |
| 网络搜索 | `src/tools/web_search.py` |
| 读网页 | `src/tools/web_fetch.py` |
| 默认工具列表 | `src/tools/__init__.py` 的 `default_tools()` |
| 工具合同 | `src/tools/base_tool.py` |
| 记忆调度 | `src/memory/manager.py` |
| 读 `.env` | `src/configs/settings.py` |
| 建表 / 连接池 | `src/database/connection.py` |
| 存聊天记录 | `src/database/chat_history.py` |

另外两篇更短：

- `docs/architecture.md`：架构草图，含尚未接线的模块
- `docs/api.md`：Python 类接口和扩展示例

## 读完可以自己讲一遍

下面几题能用自己的话讲出来，这条主路径就算走通了：

1. Agent 和普通聊天差在哪一步？
2. Thought / Action / Observation / Final Answer 分别是谁产生的？
3. `ReactAgent` 和 `AgentLoop` 谁在转圈？
4. 工具结果为什么要再塞回模型，而不是直接把计算器结果返回给用户？
5. `session_id` 不传会怎样？传同一个又会怎样？
6. PostgreSQL 挂了，服务还能不能聊？
7. 想加一个「查天气」工具，最少要改哪几个文件？

讲不顺就回到第 4 节，对着源码再走一遍第 6 节的路径。
