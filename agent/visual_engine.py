import os
import pathlib
from PIL import Image, ImageChops, ImageDraw
from openai import OpenAI
import base64
from io import BytesIO

# 初始化客户端
client = OpenAI(
    api_key="00e9329ebd37421abdcd15fc9225aed0.8OVf4p6b3lxwTQVt",
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

class VisualEngine:
    def __init__(self):
        self.base_dir = pathlib.Path(__file__).resolve().parent.parent
        self.baseline_dir = self.base_dir / "tests" / "baselines"
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.diff_dir = self.base_dir / "tests" / "diffs"
        self.diff_dir.mkdir(parents=True, exist_ok=True)

    def compare_images(self, baseline_path, current_path, diff_path):
        """像素级对比两张图，生成差异热图"""
        img1 = Image.open(baseline_path).convert("RGB")
        img2 = Image.open(current_path).convert("RGB")

        # 确保尺寸一致
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)

        diff = ImageChops.difference(img1, img2)
        
        # 增强差异显示
        # 如果有差异，则在 diff_path 保存一张高亮的图
        if diff.getbbox():
            # 创建红色遮罩标识差异
            mask = diff.convert("L").point(lambda x: 255 if x > 10 else 0)
            highlight = Image.new("RGB", img1.size, (255, 0, 0))
            result = Image.composite(highlight, img1, mask)
            result.save(diff_path)
            return True, diff
        return False, None

    def audit_with_ai(self, baseline_path, current_path, user_req=""):
        """使用 Vision LLM 审计视觉差异"""
        def encode_image(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')

        base64_baseline = encode_image(baseline_path)
        base64_current = encode_image(current_path)

        prompt = f"""你是一个资深的 UI/UX 审计专家。
我有两张网页截图：
1. [基准图]：这是之前的正确版本。
2. [当前图]：这是当前运行的版本。

用户测试需求: {user_req}

请对比两张图，判断【当前图】中出现的视觉变化是：
A. [NORMAL]：正常的业务更新（如文字内容变化、广告位轮播）。
B. [LAYOUT_BUG]：非预期的布局损坏（如按钮错位、内容重叠、颜色异常、白屏）。

请给出你的结论，并简洁说明理由。格式要求：
结论：[NORMAL/LAYOUT_BUG]
原因：一句话说明。
"""

        response = client.chat.completions.create(
            model="glm-4v",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_baseline}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_current}"}},
                    ]
                }
            ],
            temperature=0.1
        )
        return response.choices[0].message.content

def run_visual_regression(url, name, user_req=""):
    """
    视觉回归主流程
    """
    from playwright.sync_api import sync_playwright
    engine = VisualEngine()
    baseline_path = engine.baseline_dir / f"{name}_baseline.png"
    current_path = engine.base_dir / "tests" / f"{name}_current.png"
    diff_path = engine.diff_dir / f"{name}_diff.png"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(2000) # 等待渲染
        page.screenshot(path=str(current_path), full_page=True)
        browser.close()

    # 如果基准图不存在，则将当前图设为基准并返回
    if not baseline_path.exists():
        os.rename(current_path, baseline_path)
        return {"status": "NEW_BASELINE", "msg": f"未发现原基准图，已将当前截图设为基准: {name}"}

    # 1. 像素对比
    has_diff, _ = engine.compare_images(baseline_path, current_path, diff_path)
    
    if not has_diff:
        return {"status": "PASSED", "msg": "视觉对比 100% 匹配，未发现变动。"}

    # 2. AI 审计
    ai_report = engine.audit_with_ai(baseline_path, current_path, user_req)
    
    return {
        "status": "FAILED" if "LAYOUT_BUG" in ai_report else "WARNING",
        "msg": "发现视觉差异，已完成 AI 审计。",
        "report": ai_report,
        "baseline": str(baseline_path),
        "current": str(current_path),
        "diff": str(diff_path) if diff_path.exists() else None
    }
