import os
import subprocess
import pathlib
import re

def run_tests(test_file_path: str):
    """
    直接运行指定的测试文件 (pytest)，返回 (是否成功, 输出文本)
    """
    base_dir = pathlib.Path(test_file_path).resolve().parent.parent
    try:
        result = subprocess.run(
            ["pytest", "-v", "--timeout=30", str(test_file_path)],
            cwd=base_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=120
        )
        return (result.returncode == 0), result.stdout + (result.stderr or "")
    except subprocess.TimeoutExpired:
        return False, "❌ 测试执行超时（120秒），已强制终止。请检查测试代码是否存在死循环或阻塞操作。"
    except Exception as e:
        return False, str(e)


def run_tests_from_code(code: str, test_filename: str = "test_generated.py"):
    """
    1. 将 LLM 生成的代码保存到 tests 目录下
    2. 运行 pytest (带 --cov 覆盖率分析)
    3. 返回终端的运行结果和覆盖率信息
    """
    # 确定当前的根目录 (d:\\AI-test) 和 tests 目录
    base_dir = pathlib.Path(__file__).resolve().parent.parent
    tests_dir = base_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    
    # 1. 保存代码
    test_file_path = tests_dir / test_filename
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write(code)
        
    print(f"💾 Executor: 测试代码已保存至 {test_file_path}")
    print("🚀 Executor: 正在启动 pytest (开启覆盖率分析)...")

    # 2. 运行 pytest
    try:
        result = subprocess.run(
            ["pytest", "-v", "--timeout=30", "--cov=src", "--cov-report=term-missing", str(test_file_path)],
            cwd=base_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=120
        )
        
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
            
        print("--- Pytest 运行结果 (含覆盖率) ---")
        print(output)
        
        # 3. 解析覆盖率数字
        coverage_percent = 0
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        if match:
            coverage_percent = int(match.group(1))

        # 4. 判断是否成功并返回给上一层
        if result.returncode == 0:
            print(f"✅ 测试全部通过！当前覆盖率: {coverage_percent}%")
            return True, output, coverage_percent
        else:
            print("❌ 测试存在失败用例！")
            return False, output, coverage_percent
            
    except subprocess.TimeoutExpired:
        error_msg = "❌ 测试执行超时（120秒），已强制终止。可能是测试代码存在阻塞操作（如网络请求、无限循环等）。"
        print(error_msg)
        return False, error_msg, 0
    except Exception as e:
        error_msg = f"❌ 执行 pytest 失败 (是不是没安装 pytest？): {e}"
        print(error_msg)
        return False, error_msg, 0

if __name__ == "__main__":
    # 简单测试一下执行器本身
    dummy_code = """
def test_dummy():
    assert 1 + 1 == 2
"""
    run_tests_from_code(dummy_code, "test_dummy.py")
