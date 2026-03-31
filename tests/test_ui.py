from playwright.sync_api import expect

def test_click_ab_testing_and_check_url():
    print("正在访问：https://the-internet.herokuapp.com/")
    page.goto("https://the-internet.herokuapp.com/")
    print("正在点击：A/B Testing")
    ab_test_link = page.locator("a:text('A/B Testing')")
    ab_test_link.click()
    print("正在检查页面 URL 是否包含 'wrong-url-part'")
    expect(page).to_contain_text("wrong-url-part")
    page.screenshot(path="tests/ui_result.png")