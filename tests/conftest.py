import pytest

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """全局注入 User-Agent，绕过基础反爬"""
    return {
        **browser_context_args,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

@pytest.fixture(autouse=True)
def goto_target(page):
    """自动在每个测试开始前导航到目标 URL，并增加加载缓冲"""
    page.goto("https://mail.qq.com", wait_until="domcontentloaded", timeout=90000)
    # 针对大型重载量站点的柔性等待
    page.wait_for_timeout(2000)
