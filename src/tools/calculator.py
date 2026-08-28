"""
计算器工具 — 安全的数学表达式求值。

=== 为什么不用 eval()？===
eval() 能执行任意 Python 代码，非常危险！
如果用户输入 "import os; os.system('rm -rf /')"，
eval 会真的执行这个命令，删除文件。

=== 什么是 AST？===
AST = Abstract Syntax Tree（抽象语法树）。
Python 会先把代码解析成一棵树：
    2 + 3 * 4
    变成：
        Add
       /   \
      2    Mult
           /  \
          3    4

我们遍历这棵树，只允许加减乘除等安全运算符，
遇到函数调用、import 等就拒绝。
这样即使输入恶意代码，也不会被执行。
"""

from __future__ import annotations

# ast 模块用于把字符串解析成语法树
import ast

# operator 模块提供运算符对应的函数
# 例如 operator.add 对应 +，operator.mul 对应 *
import operator

from src.tools.base_tool import BaseTool


# =====================================================================
# 安全运算符白名单
# =====================================================================
# 这个字典把 AST 节点类型映射到对应的运算函数
# 只有在这个字典里的运算符才会被允许执行
# 例如 ast.Add（加法节点）→ operator.add（加法函数）
_SAFE_OPS = {
    ast.Add: operator.add,        # 加法: a + b
    ast.Sub: operator.sub,        # 减法: a - b
    ast.Mult: operator.mul,       # 乘法: a * b
    ast.Div: operator.truediv,    # 除法: a / b
    ast.FloorDiv: operator.floordiv,  # 整除: a // b
    ast.Mod: operator.mod,        # 取余: a % b
    ast.Pow: operator.pow,        # 幂运算: a ** b
    ast.USub: operator.neg,       # 一元负号: -a
    ast.UAdd: operator.pos,       # 一元正号: +a
}


class CalculatorTool(BaseTool):
    """
    安全计算器 — 仅支持基本算术运算。

    使用 AST 解析而非 eval()，防止代码注入。

    === 安全保障 ===
    1. 用 ast.parse 把字符串解析成语法树（不执行代码）
    2. 遍历语法树，只允许 _SAFE_OPS 中的运算符
    3. 遇到函数调用、属性访问等一律拒绝
    所以输入 "import os" 会被拒绝，输入 "2 + 3" 正常计算。
    """

    @property
    def name(self) -> str:
        """工具名称。"""
        return "calculator"

    @property
    def description(self) -> str:
        """工具描述，LLM 看了这个才知道什么时候该用计算器。"""
        return (
            "做数学计算。"
            "输入：算术表达式，例如 '2 + 3 * 4'。"
            "支持：+, -, *, /, //, %, ** 和括号。"
        )

    async def run(self, args: str) -> str:
        """
        安全求值数学表达式。

        Args:
            args: 数学表达式字符串，如 "2 + 3 * 4"。

        Returns:
            计算结果字符串，如 "2 + 3 * 4 = 14"。
            如果出错，返回错误信息。
        """
        try:
            # ast.parse 把字符串解析成 AST
            # mode="eval" 表示只接受表达式（不接受语句如 import）
            # 例如 "2 + 3" → AST 树，根节点是 BinOp(Add, Constant(2), Constant(3))
            tree = ast.parse(args.strip(), mode="eval")

            # 从根节点开始递归求值
            result = self._eval_node(tree.body)

            return f"{args.strip()} = {result}"
        except Exception as e:
            # 任何错误都不抛异常，返回错误信息给 LLM
            return f"Calculation error: {e}"

    def _eval_node(self, node: ast.AST) -> float | int:
        """
        递归求值 AST 节点，仅允许白名单运算符。

        === 递归过程示例 ===
        求值 "2 + 3 * 4" 的 AST：

        1. 根节点 BinOp(Add, Constant(2), Mult(Constant(3), Constant(4)))
           → 是 BinOp，查 _SAFE_OPS 找到 Add → operator.add
           → 递归求值左子树和右子树

        2. 左子树 Constant(2) → 返回 2

        3. 右子树 BinOp(Mult, Constant(3), Constant(4))
           → 是 BinOp，查 _SAFE_OPS 找到 Mult → operator.mul
           → 递归求值左子树和右子树

        4. Constant(3) → 返回 3

        5. Constant(4) → 返回 4

        6. 回到步骤 3: operator.mul(3, 4) = 12

        7. 回到步骤 1: operator.add(2, 12) = 14

        Args:
            node: AST 节点。

        Returns:
            计算结果。

        Raises:
            ValueError: 遇到不支持的运算符或表达式。
        """
        # 情况1：数字常量（如 2, 3.14）
        if isinstance(node, ast.Constant):
            return node.value

        # 情况2：二元运算（如 a + b, a * b）
        if isinstance(node, ast.BinOp):
            # 查白名单：这个运算符是否允许？
            op_func = _SAFE_OPS.get(type(node.op))
            if op_func is None:
                # 不在白名单里，拒绝（比如位运算 & ）
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            # 递归求值左右子树，然后执行运算
            return op_func(self._eval_node(node.left), self._eval_node(node.right))

        # 情况3：一元运算（如 -a, +a）
        if isinstance(node, ast.UnaryOp):
            op_func = _SAFE_OPS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op_func(self._eval_node(node.operand))

        # 其他情况（函数调用、变量名等）一律拒绝
        raise ValueError(f"Unsupported expression: {type(node).__name__}")
