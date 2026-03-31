import pytest
from agent.ui_generator import _get_dom_context

def test_dom_context_extraction():
    """
    测试 _get_dom_context 是否能从真实网页中提取出关键元素
    (1.1 改进点验证)
    """
    url = "https://example.com"
    print(f"\n测试抓取: {url}")
    
    context = _get_dom_context(url)
    
    print("\n抓取到的上下文内容预览:")
    print(context)
    
    # 验证关键信息
    assert "example.com" not in context.lower() or "DOM Context" in context
    assert "More information" in context or "<a>" in context
    assert "【DOM Context - 页面交互元素清单】" in context

if __name__ == "__main__":
    test_dom_context_extraction()
