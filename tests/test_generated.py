import pytest
from playwright.sync_api import expect

@pytest.fixture(scope="function")
def page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        yield page
        browser.close()

def test_home_links(page):
    page.goto("https://mail.qq.com")
    links = [
        ("QQ邮箱", "/"),
        ("基本版", "https://wap.mail.qq.com"),
        ("English", "https://wx.mail.qq.com?cancel_login=true&lang=en"),
        ("手机版", "https://app.mail.qq.com/"),
        ("企业邮箱", "https://exmail.qq.com?referrer=index_top")
    ]
    for text, url in links:
        print(f"正在点击：{text}")
        page.click(f"role=link text={text}")
        expect(page).to_have_url(url)

def test_footer_links(page):
    page.goto("https://mail.qq.com")
    links = [
        ("了解更多表情符号", "https://mail.qq.com/zh_CN/htmledition/features/about_symbolization.html"),
        ("关于腾讯", "https://www.tencent.com"),
        ("服务条款", "https://wx.mail.qq.com/list/readtemplate?name=app_intro.html#/agreement/mailService"),
        ("隐私政策", "https://wx.mail.qq.com/list/readtemplate?name=app_intro.html#/agreement/appPolicy"),
        ("联系我们", "https://open.mail.qq.com/feedback/feedbackhome"),
        ("帮助中心", "https://help.mail.qq.com"),
        ("账号与安全", "https://wx.mail.qq.com/account"),
        ("粤公网安备  44030002000001号", "http://www.beian.gov.cn/portal/registerSystemInfo?recordcode=44030002000001"),
        ("ICP备案号  粤B2-20090059", "https://beian.miit.gov.cn/#/Integrated/index"),
        ("增值电信业务经营许可证  粤B2-20090059", "https://beian.miit.gov.cn/#/Integrated/index")
    ]
    for text, url in links:
        print(f"正在点击：{text}")
        page.click(f"role=link text={text}")
        expect(page).to_have_url(url)

def test_layout_and_content(page):
    page.goto("https://mail.qq.com")
    expect(page).to_contain_text("QQ邮箱")
    expect(page).to_contain_text("基本版")
    expect(page).to_contain_text("English")
    expect(page).to_contain_text("手机版")
    expect(page).to_contain_text("企业邮箱")
    expect(page).to_contain_text("了解更多表情符号")
    expect(page).to_contain_text("关于腾讯")
    expect(page).to_contain_text("服务条款")
    expect(page).to_contain_text("隐私政策")
    expect(page).to_contain_text("联系我们")
    expect(page).to_contain_text("帮助中心")
    expect(page).to_contain_text("账号与安全")
    expect(page).to_contain_text("粤公网安备  44030002000001号")
    expect(page).to_contain_text("ICP备案号  粤B2-20090059")
    expect(page).to_contain_text("增值电信业务经营许可证  粤B2-20090059")
    expect(page).to_be_visible("role=link text=QQ邮箱")
    expect(page).to_be_visible("role=link text=基本版")
    expect(page).to_be_visible("role=link text=English")
    expect(page).to_be_visible("role=link text=手机版")
    expect(page).to_be_visible("role=link text=企业邮箱")
    expect(page).to_be_visible("role=link text=了解更多表情符号")
    expect(page).to_be_visible("role=link text=关于腾讯")
    expect(page).to_be_visible("role=link text=服务条款")
    expect(page).to_be_visible("role=link text=隐私政策")
    expect(page).to_be_visible("role=link text=联系我们")
    expect(page).to_be_visible("role=link text=帮助中心")
    expect(page).to_be_visible("role=link text=账号与安全")
    expect(page).to_be_visible("role=link text=粤公网安备  44030002000001号")
    expect(page).to_be_visible("role=link text=ICP备案号  粤B2-20090059")
    expect(page).to_be_visible("role=link text=增值电信业务经营许可证  粤B2-20090059")

def test_page_response_speed(page):
    page.goto("https://mail.qq.com")
    start_time = page.evaluate("performance.now")
    page.wait_for_timeout(5000)
    end_time = page.evaluate("performance.now")
    duration = end_time - start_time
    assert duration < 5000, "页面加载时间过长"

def test_links_validity(page):
    page.goto("https://mail.qq.com")
    links = [
        ("QQ邮箱", "/"),
        ("基本版", "https://wap.mail.qq.com"),
        ("English", "https://wx.mail.qq.com?cancel_login=true&lang=en"),
        ("手机版", "https://app.mail.qq.com/"),
        ("企业邮箱", "https://exmail.qq.com?referrer=index_top"),
        ("了解更多表情符号", "https://mail.qq.com/zh_CN/htmledition/features/about_symbolization.html"),
        ("关于腾讯", "https://www.tencent.com"),
        ("服务条款", "https://wx.mail.qq.com/list/readtemplate?name=app_intro.html#/agreement/mailService"),
        ("隐私政策", "https://wx.mail.qq.com/list/readtemplate?name=app_intro.html#/agreement/appPolicy"),
        ("联系我们", "https://open.mail.qq.com/feedback/feedbackhome"),
        ("帮助中心", "https://help.mail.qq.com"),
        ("账号与安全", "https://wx.mail.qq.com/account"),
        ("粤公网安备  44030002000001号", "http://www.beian.gov.cn/portal/registerSystemInfo?recordcode=44030002000001"),
        ("ICP备案号  粤B2-20090059", "https://beian.miit.gov.cn/#/Integrated/index"),
        ("增值电信业务经营许可证  粤B2-20090059", "https://beian.miit.gov.cn/#/Integrated/index")
    ]
    for text, url in links:
        print(f"正在点击：{text}")
        page.click(f"role=link text={text}")
        expect(page).to_have_url(url)

def test_language_switch(page):
    page.goto("https://mail.qq.com")
    page.click("role=link text=English")
    expect(page).to_contain_text("English")
    page.click("role=link text=QQ邮箱")
    expect(page).to_not_contain_text("English")