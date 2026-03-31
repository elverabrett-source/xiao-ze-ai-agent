"""
agent/ui_executor.py
UI 测试执行器 —— 负责保存并运行 Playwright 自动化测试脚本

工作流程:
1. 接收大模型生成的 Playwright 测试代码字符串
2. 自动生成 conftest.py（配置 base_url 和页面自动导航）
3. 确保 Playwright 浏览器已安装
4. 用 subprocess 调用 pytest 运行
5. 返回执行结果（成功/失败 + 输出日志）
"""

import subprocess
import pathlib
import sys
import os

# 项目根目录
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
TESTS_DIR = BASE_DIR / "tests"


def _ensure_playwright_browsers():
    """确保 Playwright 的 Chromium 浏览器已安装"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120
        )
        if result.returncode == 0:
            print("✅ Playwright Chromium 浏览器已就绪")
        else:
            print(f"⚠️ Playwright 浏览器安装提示: {result.stderr[-200:]}")
    except Exception as e:
        print(f"⚠️ 检查 Playwright 浏览器安装时出错: {e}")


def _ensure_conftest(target_url: str):
    """
    自动生成 tests/conftest.py 文件
    使用 pytest-playwright 的 --base-url 机制，不覆盖内置 fixture
    """
    conftest_path = TESTS_DIR / "conftest.py"
    conftest_content = f'''import pytest

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """全局注入 User-Agent，绕过基础反爬"""
    return {{
        **browser_context_args,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }}

@pytest.fixture(autouse=True)
def goto_target(page):
    """自动在每个测试开始前导航到目标 URL，并增加加载缓冲"""
    page.goto("{target_url}", wait_until="domcontentloaded", timeout=90000)
    # 针对大型重载量站点的柔性等待
    page.wait_for_timeout(2000)
'''
    with open(conftest_path, "w", encoding="utf-8") as f:
        f.write(conftest_content)
    print(f"📝 UI Executor: conftest.py 已生成（target: {target_url}）")


def run_ui_tests(code: str, filename: str = "test_ui.py", target_url: str = ""):
    """
    运行 Playwright UI 自动化测试

    参数:
        code: 由大模型生成的 Playwright pytest 测试代码
        filename: 保存的测试文件名（默认 test_ui.py）
        target_url: 目标 URL（用于生成 conftest.py）

    返回:
        (is_success: bool, output: str) 元组
    """
    test_file_path = TESTS_DIR / filename
    TESTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 保存测试代码到文件
    try:
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"💾 UI Executor: 测试代码已保存至 {test_file_path}")
    except Exception as e:
        print(f"❌ UI Executor: 保存文件失败: {e}")
        return False, str(e)

    # 2. 确保 Playwright 浏览器已安装
    _ensure_playwright_browsers()

    # 3. 如果有 target_url，自动生成 conftest.py
    if target_url:
        _ensure_conftest(target_url)

    # 4. 运行 pytest-playwright，强制捕捉截图
    print("🚀 UI Executor: 正在启动 Playwright 测试...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    # 清理旧的截图结果目录
    results_dir = BASE_DIR / "test-results"
    if results_dir.exists():
        import shutil
        shutil.rmtree(results_dir, ignore_errors=True)
    
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "-v",
                "--screenshot=only-on-failure",
                str(test_file_path)
            ],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=300
        )
    except subprocess.TimeoutExpired:
        print("❌ UI Executor: 测试执行超时（120秒），已强制终止。")
        return False, "❌ 测试执行超时（120秒），已强制终止。请检查目标网页是否可访问。", ""
    except Exception as e:
        print(f"❌ UI Executor: 调用 pytest 失败: {e}")
        return False, str(e), ""

    # 5. 解析输出
    output = result.stdout
    if result.stderr:
        output += "\n" + result.stderr
    is_success = (result.returncode == 0)
    
    crash_img_path = ""
    if not is_success and results_dir.exists():
        # 搜索 test-results 下面的所有 png 文件
        png_files = list(results_dir.rglob("*.png"))
        if png_files:
            crash_img_path = str(png_files[0].resolve())
            print(f"📸 UI Executor: 捕捉到崩溃快照 => {crash_img_path}")

    if is_success:
        print("✅ UI Executor: 所有 UI 测试通过！")
    else:
        print("❌ UI Executor: 测试存在失败用例！")

    print("\n--- UI 测试执行结果 ---")
    print(output)

    return is_success, output, crash_img_path
