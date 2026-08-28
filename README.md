# My Agent — 给初学者的完整说明书

> 这份文档的目标只有一个：让你**从头到尾看懂这个项目**。  
> 不假设你已经懂 Agent、ReAct、Flask。遇到专有名词会先用大白话解释，再对照代码。

---

## 目录

1. [一句话：这项目是干什么的](#1-一句话这项目是干什么的)
2. [先搞懂几个词（否则后面会晕）](#2-先搞懂几个词否则后面会晕)
3. [用生活例子理解 Agent](#3-用生活例子理解-agent)
4. [建议阅读顺序](#4-建议阅读顺序)
5. [项目地图：每个文件夹干什么](#5-项目地图每个文件夹干什么)
6. [一次对话到底走了哪些代码](#6-一次对话到底走了哪些代码)
7. [两种启动方式](#7-两种启动方式)
8. [环境变量怎么配](#8-环境变量怎么配)
9. [HTTP API 怎么用](#9-http-api-怎么用)
10. [记忆系统：Agent 怎么记住你说过的话](#10-记忆系统agent-怎么记住你说过的话)
11. [工具系统：Agent 怎么“动手”](#11-工具系统agent-怎么动手)
12. [LLM 客户端：Agent 怎么“思考”](#12-llm-客户端agent-怎么思考)
13. [配置、日志、异常](#13-配置日志异常)
14. [已经写好、但还没接到主流程上的模块](#14-已经写好但还没接到主流程上的模块)
15. [怎么给 Agent 加新能力](#15-怎么给-agent-加新能力)
16. [怎么跑测试](#16-怎么跑测试)
17. [常见问题](#17-常见问题)
18. [对照表：名词 ↔ 代码文件](#18-对照表名词--代码文件)

---

## 1. 一句话：这项目是干什么的

这是一个**教学用的 AI Agent 框架**。

普通聊天机器人：你问一句，模型直接回一句。

这个项目里的 Agent 会多几步：

1. **想一想**（Thought）：这件事要不要用工具？
2. **动手做**（Action）：比如调用计算器算 `15 * 23`
3. **看结果**（Observation）：计算器返回 `345`
4. **给出最终答案**（Final Answer）：告诉你 `15 * 23 = 345`

这种「先推理、再行动」的模式叫 **ReAct**（Reasoning + Acting）。

你可以：

- 在命令行里跟它聊：`python main.py "15乘23等于多少"`
- 把它当成 HTTP 服务，给前端或其他系统调用：`python server.py`

> HTTP 这一层用的是 **Flask**（和文件夹名一致）：把 Agent 包装成网址，别人用 POST 就能调用。

---

## 2. 先搞懂几个词（否则后面会晕）

| 词 | 大白话 |
|---|---|
| **LLM** | Large Language Model，大语言模型。就是 ChatGPT、DeepSeek 这类能生成文字的模型。本项目默认对接 **DeepSeek**（接口格式和 OpenAI 兼容）。 |
| **Agent（智能体）** | 不只会说话，还会**自己决定调用工具**来完成任务的程序。 |
| **ReAct** | Agent 的一种工作方式：Thought → Action → Observation，循环直到给出 Final Answer。 |
| **Tool（工具）** | Agent 的「手」。现在项目里自带一个：计算器 `calculator`。 |
| **Memory（记忆）** | 对话历史。没有记忆，Agent 下一句就忘了你刚才说了什么。 |
| **session_id** | 一次对话的身份证。同一个 `session_id` = 同一段聊天记录。 |
| **Prompt（提示词）** | 发给 LLM 的说明书，告诉它「你是谁、有哪些工具、必须按什么格式回答」。 |
| **API** | 程序之间互相调用的接口。本项目用 HTTP：别人发一个 POST 请求，就能让 Agent 干活。 |
| **Flask** | Python 写 HTTP 服务的框架。`server.py` 用它。轻量、资料多，适合入门。 |
| **Blueprint** | Flask 里「一组路由的打包」。本项目的 `/chat`、`/health` 都写在 Blueprint 里，再挂到 app 上。 |
| **PostgreSQL（PG）** | 关系型数据库。用来把对话历史存到硬盘上，服务重启后历史还在。连不上也能跑，会自动降级成「只存在内存里」。 |
| **异步（async / await）** | 调用 LLM 要等网络。`await` 表示「先去等结果，别卡住整个程序」。 |
| **抽象基类（ABC）** | 一份合同：子类必须实现某些方法。例如所有工具都必须有 `name`、`description`、`run()`。 |

---

## 3. 用生活例子理解 Agent

把 Agent 想成一个**会用计算器的助手**：

```
你：15 乘 23 等于多少？

助手心里想（Thought）：这是算术，我自己心算可能错，去用计算器。
助手动手（Action）：按计算器 15 * 23
计算器显示（Observation）：345
助手回答（Final Answer）：15 * 23 = 345
```

对应到代码，就是 `src/core/agent_loop.py` 里的循环：

```
用户输入
   ↓
[Decide]  把对话发给 LLM，LLM 输出 Thought + Action 或 Final Answer
   ↓
是 Final Answer？ → 是 → 返回给用户，结束
   ↓ 否
[Act]     解析 Action[计算器](15 * 23)，真正调用 CalculatorTool
   ↓
[Observe] 把 "15 * 23 = 345" 塞回对话，再问 LLM 一次
   ↓
重复，最多 10 轮（防止死循环）
```

LLM **不会真的去按计算器**。它只是按约定格式写出：

```text
Thought: 需要计算
Action[calculator](15 * 23)
```

真正执行计算的是你的 Python 代码 `CalculatorTool.run()`。  
这就是 Agent 和「纯聊天模型」的核心区别：**模型负责决定，代码负责执行。**

---

## 4. 建议阅读顺序

别一上来把 `src/` 全部打开。按这个顺序读，每读一个文件就能多懂一层：

| 顺序 | 文件 | 你将搞懂 |
|---|---|---|
| 1 | 本 README | 全貌 |
| 2 | `main.py` | 命令行怎么启动一轮对话 |
| 3 | `server.py` | HTTP 服务怎么起来 |
| 4 | `src/agents/react_agent.py` | Agent 外壳：组装 LLM、工具、记忆 |
| 5 | `src/core/agent_loop.py` | **最重要**：ReAct 循环到底怎么转 |
| 6 | `src/tools/calculator.py` | 一个工具长什么样 |
| 7 | `src/llm/openai_client.py` | 怎么把消息发给 DeepSeek |
| 8 | `src/memory/manager.py` | 记忆怎么存、怎么读 |
| 9 | `src/api/routes.py` | `/chat` 接口怎么接到 Agent |

源码里大部分文件顶部都有「这个文件做什么」的中文注释，就是给初学者写的，可以对着看。

---

## 5. 项目地图：每个文件夹干什么

```text
agent_study_flask/
├── main.py                 命令行入口：python main.py "你的问题"
├── server.py               HTTP 入口：python server.py  （端口 8000）
├── pyproject.toml          项目名、依赖、Python 版本要求
├── .env.example            环境变量模板（复制成 .env 再填自己的密钥）
├── .env                    真正生效的配置（不要提交到 Git）
│
├── src/                    全部业务代码
│   ├── agents/             Agent「人设」：ReactAgent 继承 BaseAgent
│   ├── core/               大脑引擎：AgentLoop（perceive → decide → act）
│   ├── llm/                怎么调用大模型
│   ├── tools/              工具（目前只有计算器）
│   ├── memory/             短期记忆 + 长期记忆（长期还是空壳）
│   ├── database/           PostgreSQL：把对话存进数据库
│   ├── api/                Flask 的路由和请求/响应格式
│   ├── configs/            从 .env 读配置
│   ├── safety/             输入过滤、输出脱敏（代码有了，主流程还没接上）
│   ├── cache/              LLM 响应缓存（代码有了，主流程还没接上）
│   ├── prompts/            提示词草稿（目前循环里是代码里写死的 prompt）
│   └── utils/              日志、自定义异常
│
├── tests/                  自动化测试
│   ├── unit/               测单个模块（用假 LLM，不花 API 钱）
│   └── integration/        测模块组合、测 HTTP 接口
│
└── docs/                   偏开发者的短文档（架构、Python 接口）
```

### 5.1 两个入口，不要搞混

| 入口 | 命令 | 适合 |
|---|---|---|
| `main.py` | `python main.py "15*23等于多少"` | 自己在终端里试 Agent |
| `server.py` | `python server.py` | 给网页、Postman、其他程序调用 |

CLI 每次都会 `ReactAgent()` 新建一个 Agent，**默认记不住上一次命令行对话**（每次新的 `session_id`）。  
HTTP 接口可以通过同一个 `session_id` 把多轮对话串起来。

### 5.2 核心类之间的关系

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
   AgentLoop.execute(...)          ← 真正转圈的地方
        │
        ├── LLMFactory.create() → OpenAIClient.chat()   ← 「想」
        ├── CalculatorTool.run()                        ← 「做」
        └── MemoryManager                               ← 「记」
                 ├── ShortTermMemory（内存，最近 N 条）
                 └── ChatHistoryRepo（PostgreSQL，持久化）
```

`ReactAgent` 可以理解成**外壳**：把零件拼好。  
`AgentLoop` 才是**发动机**：按 ReAct 规则一轮一轮跑。

---

## 6. 一次对话到底走了哪些代码

以 HTTP 为例：`POST /chat`，body 是 `{"message": "15 * 23 等于多少"}`。

```text
1. Flask 内置服务器收到请求
2. Pydantic 的 ChatRequest 校验：message 不能空，最长 10000 字
3. routes.chat()
      - 没传 session_id → 自动生成一个 UUID
      - get_or_create_agent(session_id) → 没有就新建 ReactAgent
4. asyncio.run(agent.run(message))
      - Flask 路由是同步的，Agent 内部是异步的，所以包一层 asyncio.run
      - 内部调用 loop.execute(message)
5. AgentLoop.execute()
      a. 拼 system prompt（告诉 LLM：你是 ReAct Agent，有 calculator 工具）
      b. 从 MemoryManager 取出这个 session 的历史消息
      c. 组成 messages 列表发给 LLM：
            [system, ...历史..., 当前用户这句话]
      d. 进入 for 循环（最多 AGENT_MAX_ITERATIONS 次，默认 10）
            LLM 回复
            ├─ 匹配到 "Final Answer: xxx" → 存记忆，返回 xxx
            ├─ 匹配到 "Action[名字](参数)" → 找工具并 run()，把结果当 Observation 再问 LLM
            └─ 两种格式都没有 → 提醒 LLM 按格式说话，进入下一轮
      e. 10 轮还没 Final Answer → 抛 MaxIterationsError → HTTP 508
6. 返回 JSON：
      { "answer": "...", "agent": "ReactAgent", "iterations": 2, "session_id": "..." }
```

命令行路径更短：`main.py` 直接 `ReactAgent().run(...)`，不经过 Flask，也没有多 session 复用。

---

## 7. 两种启动方式

### 7.1 准备环境（两种方式都要做）

需要 **Python 3.11+**。

在项目根目录（有 `pyproject.toml` 的那一层）打开终端：

```powershell
# 1. 创建虚拟环境（隔离依赖，避免污染系统 Python）
python -m venv venv

# 2. 激活虚拟环境（Windows PowerShell）
.\venv\Scripts\Activate.ps1

# Linux / macOS 用：
# source venv/bin/activate

# 3. 安装本项目（-e 表示可编辑安装，改 src 立刻生效）
pip install -e ".[dev]"

# 4. 复制配置模板，填入你自己的密钥
copy .env.example .env
# 然后用编辑器打开 .env，把 LLM_API_KEY 改成你的 DeepSeek Key
```

如果 PowerShell 提示「无法加载，因为在此系统上禁止运行脚本」，先执行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

再重新激活虚拟环境。

### 7.2 命令行聊天

```powershell
python main.py "15乘23等于多少"
```

没有参数时，会提示你手动输入：

```text
🧑 You:
```

成功时终端大致会打印：

```text
🤖 Agent: 15 * 23 = 345
```

### 7.3 HTTP 服务

```powershell
python server.py
```

启动后：

| 地址 | 作用 |
|---|---|
| http://localhost:8000/ | 服务简介 |
| http://localhost:8000/health | 健康检查（含数据库是否连上） |
| http://localhost:8000/docs | 接口说明（JSON，浏览器打开就能看） |
| `POST http://localhost:8000/chat` | 真正聊天 |

`debug=True`：你改了 Python 代码，服务会自动重启，出错时显示调试页。这是开发模式，不要用在公网。

---

## 8. 环境变量怎么配

配置集中在 `.env`，由 `src/configs/settings.py` 读取。  
优先级：**系统环境变量 > `.env` 文件 > 代码里的默认值**。

字段名用小写写在 Python 里，对应环境变量是大写。例如 `llm_api_key` ↔ `LLM_API_KEY`。

| 变量 | 含义 | 典型值 |
|---|---|---|
| `LLM_API_KEY` | 大模型密钥，**必须改成你自己的** | `sk-你的密钥` |
| `LLM_BASE_URL` | API 地址 | `https://api.deepseek.com/v1` |
| `LLM_MODEL` | 模型名 | `deepseek-v4-flash` |
| `AGENT_MAX_ITERATIONS` | ReAct 最多转几圈 | `10` |
| `AGENT_MEMORY_WINDOW` | 短期记忆最多留几条消息 | `20` |
| `AGENT_DEBUG` | 是否打更详细日志 | `true` |
| `PG_URI` | PostgreSQL 连接串 | `postgresql://用户:密码@主机:5432/库名` |
| `CHROMA_PERSIST_PATH` | 向量库路径（长期记忆预留） | `./data/chroma` |

DeepSeek 的接口和 OpenAI 的 Chat Completions 格式兼容，所以代码类名叫 `OpenAIClient`，实际可以连 DeepSeek。换别的兼容服务时，通常只改 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。

**PostgreSQL 不是必须的。** 连不上时，记忆只存在内存里，进程一关就没了。HTTP 的 `/health` 里 `database` 会显示 `unavailable`，聊天功能仍可使用。

---

## 9. HTTP API 怎么用

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

**请求：**

```json
{
  "message": "15 * 23 等于多少",
  "session_id": "可选，不传会自动生成"
}
```

**成功响应：**

```json
{
  "answer": "15 * 23 = 345",
  "agent": "ReactAgent",
  "iterations": 2,
  "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

`iterations` 表示这次为了得出答案，LLM 被调用了几轮。  
算一道题通常是 2：第一轮调计算器，第二轮给出 Final Answer。

**多轮对话：** 把上一次返回的 `session_id` 原样传回去。同一个会话会复用同一个 Agent，并带上历史消息。

PowerShell 示例：

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

**可能的错误码：**

| 状态码 | 含义 |
|---|---|
| 422 | `message` 为空或超长 |
| 500 | 内部错误（常见原因：API Key 无效、网络不通） |
| 508 | 转了 10 圈还没有 Final Answer |

请求/响应字段定义在 `src/api/models.py`，用 Pydantic 自动校验。

---

## 10. 记忆系统：Agent 怎么记住你说过的话

分三层，目前真正在用的是前两层：

```text
MemoryManager
 ├── ShortTermMemory     内存里的滑动窗口（deque），默认最近 20 条
 ├── PostgreSQL          持久化，重启后按 session_id 把历史装回内存
 └── LongTermMemory      预留：以后用向量库做「语义搜索旧知识」，现在是空壳
```

**为什么既要内存又要数据库？**

- 每次问 LLM 都从数据库读，会慢。
- 内存里放最近窗口，读起来快。
- 数据库负责「关服务也不丢」。PG 挂了就只走内存，不把整个 Agent 弄挂。

**窗口是什么意思？**

LLM 一次能吃的文字有上限。窗口 = 只保留最近 N 条。  
默认 20。第 21 条进来时，最早那条会被挤掉（`collections.deque(maxlen=20)`）。

**和 session_id 的关系：**

- HTTP：`get_or_create_agent(session_id)` 按会话缓存 Agent。
- 同一 `session_id` → 同一份记忆。
- 不同 `session_id` → 互不干扰。
- CLI 的 `ReactAgent()` 每次新建，相当于每次新开一个会话。

相关文件：

- `src/memory/manager.py` — 调度中心
- `src/memory/short_term.py` — 内存窗口
- `src/memory/long_term.py` — stub（占位，还没接 ChromaDB）
- `src/database/connection.py` — 连接池、建表
- `src/database/chat_history.py` — 增删查对话记录

表 `chat_history` 大致是：`session_id`、`role`（user/assistant）、`content`、`iterations`、`created_at`。

---

## 11. 工具系统：Agent 怎么「动手」

所有工具都继承 `BaseTool`，必须提供：

1. `name`：英文名，对应 LLM 写的 `Action[这个名字](...)`
2. `description`：出现在 system prompt 里，LLM 靠它决定「该不该用我」
3. `run(args)`：真正执行，返回字符串，作为 Observation

目前唯一实现：`CalculatorTool`。

它**不用** Python 的 `eval()`（`eval` 能执行任意代码，危险）。  
做法是：把 `"2 + 3 * 4"` 解析成语法树（AST），只允许 `+ - * / // % **` 和正负号。遇到函数调用、`import` 就拒绝。

`AgentLoop` 找工具的方式很直接：遍历 `self.tools`，名字对上就 `await tool.run(args)`。  
工具不存在或算失败时，**不把整个请求打爆**，而是把错误字符串当作 Observation 还给 LLM，让它换策略。

---

## 12. LLM 客户端：Agent 怎么「思考」

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

这是**工厂模式**：换模型时，理想情况是新增一个 `XxxClient`，在工厂里加一行，不必改 `AgentLoop`。

当前工厂里只注册了 `"openai"` 这一种。DeepSeek 走的就是这条路（兼容同一套 HTTP 协议）。

`messages` 的格式是行业惯例：

```python
[
  {"role": "system", "content": "你是谁、有什么工具、怎么输出"},
  {"role": "user", "content": "用户的话"},
  {"role": "assistant", "content": "模型上一轮说的"},
  {"role": "user", "content": "Observation: 工具结果"},
]
```

`temperature` 默认 0.7：越大越随机，越小越死板。

---

## 13. 配置、日志、异常

### 配置

`get_settings()` 带 `@lru_cache`：整个进程只读一次 `.env`，到处拿到的是同一份配置。

### 日志

`src/utils/logger.py` 用 `rich` 把日志打得带颜色。每个模块通常写：

```python
from src.utils.logger import get_logger
logger = get_logger(__name__)
```

级别从低到高：DEBUG → INFO → WARNING → ERROR。  
开发时看 DEBUG 有助于看清「第几轮循环、调了哪个工具」。

### 异常

`src/utils/exceptions.py`：

```text
AgentError
 ├── AgentLoopError → MaxIterationsError   转圈太多
 ├── LLMError                              调模型失败
 ├── ToolError                             工具失败
 └── MemoryError                           记忆出错
```

HTTP 层会把 `MaxIterationsError` 变成 508，其它未捕获异常变成 500。

---

## 14. 已经写好、但还没接到主流程上的模块

读代码时容易误会「有文件 = 已经在用」。下面这些**当前对话路径不会自动走到**：

| 模块 | 现状 |
|---|---|
| `src/safety/input_filter.py` | 能检测常见 Prompt Injection（如 “ignore previous instructions”），**`AgentLoop` / `routes` 没有调用它** |
| `src/safety/output_filter.py` | 能把邮箱、手机号、身份证、`sk-` 密钥打成 `[EMAIL]` 等，**主流程没接** |
| `src/cache/response_cache.py` | 相同 messages 可缓存 LLM 回复，**OpenAIClient 没接** |
| `src/prompts/*.md` | 写了更完整的 ReAct 提示词和 few-shot 例子，**实际 prompt 是 `agent_loop.py` 里字符串拼出来的** |
| `src/memory/long_term.py` | 向量长期记忆接口，返回空列表 / `"stub-id"` |

它们不是垃圾，而是**预留扩展点**。想动手练习，最合适的作业就是：把 InputFilter、OutputFilter、ResponseCache 接到 `AgentLoop` 或 `routes` 上。

`docs/architecture.md` 里画的依赖关系偏「目标架构」，和「此刻真实调用链」不完全一致。以本 README 第 5、6 节为准。

---

## 15. 怎么给 Agent 加新能力

### 加一个新工具（例如搜索）

1. 在 `src/tools/` 新建文件，继承 `BaseTool`。
2. 实现 `name`、`description`、`run`。
3. 在创建 Agent 的地方把工具加进列表：
   - CLI：`src/agents/react_agent.py` 的 `tools=[CalculatorTool(), 你的工具()]`
   - HTTP：`src/api/routes.py` 的 `get_or_create_agent()` 里同样加上

`description` 要写清楚「干什么、参数长什么样」，否则 LLM 不知道什么时候该调用你。

### 加一种新的大模型客户端

1. 新建 `src/llm/xxx_client.py`，实现 `BaseLLMClient.chat()`。
2. 在 `LLMFactory.create()` 的 `providers` 字典里注册名字。

### 换提示词

现在改 `AgentLoop._build_system_prompt()`。  
以后也可以改成读取 `src/prompts/system.md`。

---

## 16. 怎么跑测试

```powershell
# 确保已激活 venv，并安装了 dev 依赖
pytest
```

测试**不会**真的去调 DeepSeek（那样又慢又花钱）。它们用假的 LLM：

- 第一轮固定返回 `Action[calculator](15 * 23)`
- 第二轮固定返回 `Final Answer: 15 * 23 = 345`
- 计算器是真的，所以能验证「解析 Action → 执行工具 → 给出答案」整条链

主要文件：

- `tests/unit/test_agent_loop.py` — 立刻给答案 / 超时抛错
- `tests/unit/test_tools.py` — 计算器
- `tests/unit/test_memory.py` — 短期记忆窗口
- `tests/integration/test_agent_e2e.py` — Loop + 真计算器 + 假 LLM
- `tests/integration/test_api.py` — HTTP `/`、`/health`、`/chat`

---

## 17. 常见问题

**Q：为什么 Agent 是 async，Flask 路由却是同步函数？**  
A：调用 LLM 适合用 async 等网络。经典 Flask 视图是普通函数。所以在 `/chat` 里用 `asyncio.run(agent.run(...))` 把这一次异步循环跑完。对初学者比上 ASGI 服务器更直观。

**Q：`python main.py` 没反应或报 API 错误？**  
A：检查 `.env` 里 `LLM_API_KEY` 是否仍是 `sk-xxx`，以及网络能否访问 `LLM_BASE_URL`。

**Q：`/health` 显示 database unavailable？**  
A：PostgreSQL 没连上。聊天还能用，只是重启后对话历史会丢。按 `PG_URI` 检查账号、主机、防火墙。

**Q：为什么 Agent 有时不调用计算器，直接口算？**  
A：LLM 不一定每次都听话。system prompt 只是「强烈建议」。简单加减它可能自己算；复杂表达式更倾向用工具。这是正常现象。

**Q：为什么最多 10 轮？**  
A：如果模型一直输出 Action 却不给 Final Answer，循环永不结束。`max_iterations` 是保险丝。

**Q：CLI 第二句为什么不记得第一句？**  
A：每次运行 `main.py` 都是新进程、新 `ReactAgent`、新 `session_id`。要用记忆，请走 HTTP 并固定 `session_id`。

**Q：代码里又是 OpenAI 又是 DeepSeek？**  
A：HTTP 协议按 OpenAI Chat Completions 来写；默认配置指向 DeepSeek。换兼容该协议的其它厂商，改 `.env` 即可。

---

## 18. 对照表：名词 ↔ 代码文件

| 你听到的说法 | 去看这个文件 |
|---|---|
| 命令行入口 | `main.py` |
| HTTP 入口 | `server.py` |
| 聊天接口 | `src/api/routes.py` |
| 请求 JSON 长什么样 | `src/api/models.py` |
| Agent 外壳 | `src/agents/react_agent.py` |
| Agent 必须实现 run() | `src/agents/base_agent.py` |
| ReAct 循环 | `src/core/agent_loop.py` |
| 调大模型 | `src/llm/openai_client.py` |
| 创建 LLM 客户端 | `src/llm/factory.py` |
| 计算器 | `src/tools/calculator.py` |
| 工具合同 | `src/tools/base_tool.py` |
| 记忆调度 | `src/memory/manager.py` |
| 读 .env | `src/configs/settings.py` |
| 建表 / 连接池 | `src/database/connection.py` |
| 存聊天记录 | `src/database/chat_history.py` |

更偏「给已经懂架构的人看」的短文：

- `docs/architecture.md` — 架构草图（含尚未接线的模块）
- `docs/api.md` — Python 类接口和扩展示例

---

## 你读完之后应该能回答的问题

如果下面几题你都能用自己的话讲出来，这个项目就算理清了：

1. Agent 和普通聊天机器人差在哪一步？
2. Thought / Action / Observation / Final Answer 分别是谁产生的？
3. `ReactAgent` 和 `AgentLoop` 谁才是转圈的发动机？
4. 为什么工具结果要再塞回 LLM，而不是直接把计算器结果返回给用户？
5. `session_id` 不传会怎样？传同一个又会怎样？
6. PostgreSQL 挂了，服务还能不能聊？
7. 想加一个「查天气」工具，最少要改哪几个文件？

答不上来就回到第 4 节，对着源码再走一遍「一次对话的路径」。
