import sys
import os
# 添加 agent 目录到 sys.path 以便导入 math_utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'agent')))

import math_utils

def test_add():
    assert math_utils.add(2, 3) == 5

def test_is_positive():
    assert math_utils.is_positive(5) is True
    # 注意：这里漏掉了对负数或 0 的测试，变异测试应该能抓到！
