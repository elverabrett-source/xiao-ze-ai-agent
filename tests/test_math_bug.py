import pytest
from src.agent import math_utils

# 测试 add 函数
def test_add():
    # 正常用例
    assert math_utils.add(5, 3) == 2, "add function should return the difference of two numbers"
    # 边界用例
    assert math_utils.add(0, 0) == 0, "add function should handle zero correctly"

# 测试 is_positive 函数
def test_is_positive():
    # 正常用例
    assert math_utils.is_positive(5) == True, "is_positive function should return True for positive numbers"
    # 边界用例
    assert math_utils.is_positive(0) == False, "is_positive function should return False for zero"
    # 异常用例
    assert math_utils.is_positive(-5) == False, "is_positive function should return False for negative numbers"

# 测试 divide 函数
def test_divide():
    # 正常用例
    assert math_utils.divide(10, 2) == 5, "divide function should return the division result of two numbers"
    # 边界用例
    assert math_utils.divide(10, 0) is None, "divide function should return None for division by zero"
    # 异常用例
    assert math_utils.divide(0, 0) is None, "divide function should return None for division by zero"