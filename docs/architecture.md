# Architecture

## 概览

My Agent 采用 **ReAct（Reasoning + Acting）** 模式，核心是一个认知循环：

```
User Input → [Perceive] → [Decide] → [Act] → [Observe] → ... → Final Answer
```

## 模块依赖

```
main.py
  └── agents/react_agent.py
        ├── core/agent_loop.py       ← 认知循环核心
        │     ├── llm/               ← LLM 推理
        │     ├── tools/             ← 工具执行
        │     └── memory/           ← 历史记忆
        ├── safety/                 ← 输入/输出过滤
        └── cache/                  ← 响应缓存
```

## 认知循环流程

1. **Perceive**: 构建 system prompt + 加载历史记忆 + 用户输入
2. **Decide**: LLM 输出 `Thought + Action[tool](args)` 或 `Final Answer`
3. **Act**: 解析 Action，调用对应工具
4. **Observe**: 将工具返回结果作为 Observation 回传给 LLM
5. **Loop**: 重复 2-4 直到输出 Final Answer 或达到 max_iterations

## 设计原则

- **依赖注入**: Agent 接收 LLM/Tools/Memory 实例，不硬编码
- **工厂模式**: LLMFactory 统一创建客户端，切换模型只改配置
- **安全第一**: InputFilter 防 injection，OutputFilter 做脱敏
- **缓存优先**: ResponseCache 避免重复 API 调用
