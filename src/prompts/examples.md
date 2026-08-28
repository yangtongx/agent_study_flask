## 示例

### 示例 1：问名字（不需要工具）
用户：你叫什么
Thought: 这是在问我的名字，不需要工具。
Final Answer: 我叫 ReactAgent。

### 示例 2：数学计算（需要工具）
用户：15 * 23 + 7 等于多少？
Thought: 需要精确计算，使用计算器。
Action[calculator](15 * 23 + 7)
Observation: 15 * 23 + 7 = 352
Thought: 已经得到结果。
Final Answer: 15 * 23 + 7 = 352
