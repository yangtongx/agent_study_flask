"""工具模块单元测试。"""

import pytest

from src.tools.calculator import CalculatorTool


@pytest.mark.asyncio
async def test_calculator_basic():
    """测试基本算术：2 + 3 应该等于 5。"""
    calc = CalculatorTool()
    result = await calc.run("2 + 3")
    # 结果字符串中应该包含 "5"
    assert "5" in result


@pytest.mark.asyncio
async def test_calculator_complex():
    """测试复合表达式：2 + 3 * 4 应该等于 14（先乘后加）。"""
    calc = CalculatorTool()
    result = await calc.run("2 + 3 * 4")
    assert "14" in result


@pytest.mark.asyncio
async def test_calculator_power():
    """测试幂运算：2 ** 10 应该等于 1024。"""
    calc = CalculatorTool()
    result = await calc.run("2 ** 10")
    assert "1024" in result


@pytest.mark.asyncio
async def test_calculator_invalid():
    """测试非法输入：import os 不应该执行，应返回错误。"""
    calc = CalculatorTool()
    result = await calc.run("import os")
    # 结果中应该包含 "error"
    assert "error" in result.lower()


def test_calculator_name_and_description():
    """测试工具的元信息（name 和 description 属性）。"""
    calc = CalculatorTool()
    assert calc.name == "calculator"
    # description 要让 LLM 知道这是计算器
    assert "数学" in calc.description
