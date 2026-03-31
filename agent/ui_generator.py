"""
agent/ui_generator.py
AI 驱动的 UI 自动化测试生成器（基于 Playwright）

功能：
- 接收目标网页URL、截图、以及用户描述的测试需求
- 调用大模型（GLM-4 / GLM-4V）生成标准的 Playwright Python 测试脚本
- 生成的测试符合 pytest-playwright 规范，可以直接运行
"""

import os
import re
import base64
from openai import OpenAI
from playwright.sync_api import sync_playwright

# 复用同一个智谱客户端
client = OpenAI(
    api_key="00e9329ebd37421abdcd15fc9225aed0.8OVf4p6b3lxwTQVt",
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

# 系统提示词：教会大模型生成合格的 Playwright 测试代码
UI_TEST_SYSTEM_PROMPT = """你是一个专业的 UI 自动化测试工程师，精通 Playwright（Python）。
你的任务是根据用户描述的测试目标或提供的网页截图，生成规范、完整、可直接运行的 Playwright 测试脚本。

【必须遵守的代码规范】:
1. 使用 pytest-playwright 风格，即使用 `page` fixture，不要自己 launch browser
2. 测试函数名必须以 `test_` 开头
3. 对每一个测试操作之后，必须加上合适的 `expect()` 断言
4. 使用 `page.locator()` 选择器，优先用 role/text 选择器，而非 xpath 或 css
5. **如果下方提供了 [DOM Context]，请务必根据其中提供的真实 id、role 或 text 进行定位，不要臆造不存在的选择器。**
6. 不要写任何注释之外的多余内容，只输出纯 Python 代码
7. 必须 import `from playwright.sync_api import expect`
8. **非常重要：断言元素存在/可见之前，必须先执行让该元素出现的操作。**
   例如，如果一个"删除"按钮是点击"添加"后才会出现的，
   则必须先执行 add_button.click()，再去 expect(remove_button).to_be_visible()
9. 如果需要等待元素出现，使用 `page.wait_for_selector()` 或 `expect(locator).to_be_visible(timeout=5000)`
10. 每个测试用例要完整、独立，从 goto URL 开始
11. **【操作透明度要求】**：
    - 在进行每一个 click, fill, check 等操作之前，必须先 print 一行中文日志，例如：`print("正在点击：[按钮名称]")`。
    - 在测试脚本的最后（断言成功后），必须执行 `page.screenshot(path="tests/ui_result.png")` 以保存最终画面截图。

【输出格式】:
只输出一个 Python 文件的完整代码，不要有任何解释性文字、不要加 ```python``` 包裹。
"""

DIAGNOSIS_SYSTEM_PROMPT = """你是一个资深的软件测试专家 (QA Auditor)。
你的任务是：分析一段自动生成的 Playwright 测试代码失败的原因，并判定它究竟是【定位器失效】还是【真实的业务 Bug】。

你需要根据以下信息进行判断：
1. 用户测试需求：用户原本想测什么。
2. 失败的测试代码：AI 写的脚本。
3. 运行报错 (Traceback)：报错的具体位置和错误类型。
4. [DOM Context]：网页上真实的元素清单（包含 href, role, text 等）。

【判定标准】：
- **LOCATOR_ISSUE (定位器/适配问题)**：
    - 报错是 `Timeout` 或 `Selector matched 0 elements`。
    - 且你从 [DOM Context] 中能看到相似但属性略有差别的元素（例如点击“登录”，代码里用的是 id="login"，但实际变成了 id="btn-login"）。
    - 这种情况下，测试需要“自愈”。

- **LOGIC_BUG (业务逻辑故障)**：
    - 断言失败 (AssertionError)。例如：需求要求点击后跳转到 /dashboard，代码也点击了正确按钮，但网页实际跳转到了 /error 或留在原处。
    - 或者出现了非预期的报错（如 500 错误页面）。
    - 这种情况下，**严禁修改测试用例以迎合错误结果**，必须报告 Bug。

- **ENVIRONMENT_ERROR (环境问题)**：
    - 网络超时、404、浏览器崩溃。

【输出格式要求】：
请以 JSON 格式输出你的诊断报告，包含以下字段：
{
  "category": "LOCATOR_ISSUE" | "LOGIC_BUG" | "ENVIRONMENT_ERROR",
  "analysis": "简洁的中文分析，说明你为什么这么判定",
  "suggestion": "建议采取的行动（修复代码 或 检查业务 Bug）"
}
"""

RCA_SYSTEM_PROMPT = """你是一个顶级的代码审计专家。
你的任务是：根据测试失败的报错和业务源代码，分析出导致 Bug 的根本原因。

【分析维度】:
1. **问题描述**: 简述测试为什么失败。
2. **源码定位**: 指出 Bug 出现在哪一个文件的哪一行（或哪几个函数）。
3. **修复建议**: 提供修复后的代码补丁或逻辑修改建议。

【输出格式】:
请严格按照以下格式输出：
结论：[DESC]
定位：[FILE_NAME:LINE_NUMBER]
理由：[WHY_IT_FAILED]
修复建议：
```python
# 修复后的代码
```
"""


def _get_dom_context(url: str) -> str:
    """
    通过 Playwright 预访问网页，抓取交互元素的元数据，辅助 LLM 精确选择定位器。
    (新增 1.1 改进点：精准 UI 定位)
    """
    # 提醒：这是为了解决 AI 生成测试时“瞎猜”选择器的问题
    print(f"🔍 UI Generator: 正在预访问 [{url}] 以提取 DOM 上下文...")
    try:
        with sync_playwright() as p:
            # 1. 启动无头浏览器进行背景调查
            browser = p.chromium.launch(headless=True)
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            context = browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent=user_agent
            )
            page = context.new_page()
            
            # 2. 访问目标 URL，不再死等网络静止（针对大型站点优化）
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            # 3. 在浏览器内执行 JS 脚本，筛选出所有可能的交互元素（按钮、链接、输入框等）
            elements_data = page.evaluate("""
                () => {
                    // 选取带有交互嫌疑的标签和属性
                    const interactives = Array.from(document.querySelectorAll(
                        'button, a, input, select, textarea, [role], [onclick], [cursor="pointer"]'
                    ));
                    
                    return interactives.map(el => {
                        const rect = el.getBoundingClientRect();
                        // 过滤掉不可见或面积太小的无效元素
                        if (rect.width < 2 || rect.height < 2) return null;
                        
                        return {
                            tag: el.tagName.toLowerCase(),
                            text: el.innerText.trim().substring(0, 50).replace(/\\n/g, ' '),
                            id: el.id || '',
                            name: el.getAttribute('name') || '',
                            role: el.getAttribute('role') || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            placeholder: el.getAttribute('placeholder') || '',
                            type: el.getAttribute('type') || '',
                            href: el.getAttribute('href') || '', // 新增：链接跳转地址
                            src: el.getAttribute('src') || '',   // 新增：图片/媒体源地址
                            onclick: el.getAttribute('onclick') ? 'Yes' : '' // 新增：是否有内联点击事件
                        };
                    }).filter(x => x !== null).slice(0, 60); // 截取前 60 个，避免 Context 溢出
                }
            """)
            
            browser.close()
            
            if not elements_data:
                return "（未能抓取到明显的交互元素，页面可能由纯动态脚本渲染）"
                
            # 4. 将抓取到的“零件清单”格式化为文本，喂给大模型参考
            lines = ["【DOM Context - 页面交互元素清单】:"]
            for info in elements_data:
                parts = [f"<{info['tag']}>"]
                if info['text']: parts.append(f"文本:\"{info['text']}\"")
                if info['id']: parts.append(f"id:\"{info['id']}\"")
                if info['role']: parts.append(f"role:\"{info['role']}\"")
                if info['ariaLabel']: parts.append(f"aria-label:\"{info['ariaLabel']}\"")
                if info['placeholder']: parts.append(f"placeholder:\"{info['placeholder']}\"")
                if info['name']: parts.append(f"name:\"{info['name']}\"")
                if info['href']: parts.append(f"href:\"{info['href']}\"")
                if info['src']: parts.append(f"src:\"{info['src']}\"")
                if info['onclick']: parts.append(f"onclick:\"Yes\"")
                lines.append("  - " + " | ".join(parts))
            
            return "\n".join(lines)
            
    except Exception as e:
        # 即使提取失败，也要能容错，让 AI 回退到原有的猜测模式
        print(f"⚠️ UI Generator: DOM 上下文提取告警 - {e}")
        return f"（DOM 上下文提取失败: {str(e)}）"


def _call_llm(user_prompt: str, image_path: str = "") -> str:
    """内部函数：根据是否有图片选择合适的模型调用方式"""
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        response = client.chat.completions.create(
            model="glm-4v",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{UI_TEST_SYSTEM_PROMPT}\n\n{user_prompt}"},
                    {"type": "image_url", "image_url": {"url": b64}}
                ]
            }],
            temperature=0.1
        )
    else:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": UI_TEST_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1
        )

    raw = response.choices[0].message.content or ""
    # 使用正则安全提取被 ```python ... ``` 包裹的真实代码，忽略一切人类废话
    match = re.search(r"```python\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 兜底：如果没写 ```python，尝试去掉首尾的普通 ``` 
    raw = re.sub(r"^```\w*\s*", "", raw.strip())
    raw = re.sub(r"```$", "", raw.strip())
    return raw.strip()


def generate_ui_tests(target_url: str, test_requirement: str, image_path: str = "") -> str:
    """
    主函数：基于 Multi-Agent 工作流，生成针对指定 URL 的 Playwright UI 测试代码
    """
    print(f"🎨 UI Generator: 正在为 [{target_url}] 组建测试生成流水线...")
    dom_context = _get_dom_context(target_url)
    image_hint = "（附带了网页截图，请结合视觉效果与下方 [DOM Context] 共同分析）" if image_path else ""

    # ==========================
    # 角色 1：👨‍💼 需求分析师 Agent
    # ==========================
    print(f"\n[AGENT: 👨‍💼 需求分析] 正在将业务语言解构成原子测试边界点...")
    analyst_prompt = f"""
你是一名资深的测试需求分析师。你的任务是将用户模糊的需求转化为高度明确的测试用例 Checklist。
不要写代码，只写必须验证的功能点。

目标网页 URL：{target_url}
用户测试需求：{test_requirement} {image_hint}
[DOM Context]：
{dom_context}

要求：
1. 请仅针对用户明确要求的元素拆解测试点。
2. 每个测试点必须包含：前置条件、操作步骤、预期断言。
3. 如果用户描述模糊，请挑出 1-3 个最具代表性的核心元素。
"""
    test_cases_plan = _call_llm(analyst_prompt, image_path)
    print(f"[AGENT: 👨‍💼 需求分析] 分析完成，已提取以下测试计划：\n{test_cases_plan[:300]}...\n")

    # ==========================
    # 角色 2：🧑‍💻 测试开发 Agent
    # ==========================
    print(f"[AGENT: 🧑‍💻 代码编排] 基于拟定的测试要求，正在编写高密度 Pytest 挂载逻辑...")
    coder_prompt = f"""
你是一名顶级的 Python 自动化测试开发专家 (Playwright + Pytest)。
请严格按照以下《测试计划》编写可以直接独立运行的 Pytest 测试脚本。

目标网页 URL：{target_url}
【测试计划 Checklist】：
{test_cases_plan}

[DOM Context] 作为辅助信息：
{dom_context}

注意：
1. page.goto() 调用时直接使用完整 URL："{target_url}"
2. 代码最外层必须包含 `import pytest` 等必要包。
3. 请使用 `page.expect_url` 或基于 DOM 元素存在性的强壮的校验断言。
"""
    draft_code = _call_llm(coder_prompt)
    if not draft_code:
        print("❌ Coder Agent 生成失败，返回空集。")
        return ""
    print(f"[AGENT: 🧑‍💻 代码编排] 初稿编写完成！（{len(draft_code)} 字符）\n")

    # ==========================
    # 角色 3：🕵️‍♂️ 审查官 Agent
    # ==========================
    print(f"[AGENT: 🕵️‍♂️ 审查官] 正在审查生成的脚本，寻找安全风险、死循环与遗漏依赖...")
    critic_prompt = f"""
你是一名冷酷无情的代码审查官。
下面是你的一名初级开发写的测试脚本草稿：
```python
{draft_code}
```

请检查：
1. 是否缺少 `import pytest` 或 `from playwright.sync_api`？
2. 是否存在潜在死循环或是危险的文件系统读写 (`os.system` / `shutil`)？
3. URL 是否错误？

如果有问题，请直接输出修改后的**完整** Python 代码。如果没有问题，也请输出完整原始代码，不要有任何 Markdown 修饰或多余对话。
"""
    final_code = _call_llm(critic_prompt)
    if not final_code:
        print("❌ Critic Agent 审查后致死截断，退回初稿。")
        return draft_code

    print(f"[AGENT: 🕵️‍♂️ 审查官] 静态审查通过，授予最终执行绿灯！🚦")
    return final_code


def fix_ui_tests(failed_code: str, error_output: str, target_url: str, image_path: str = "") -> str:
    """
    自我修复函数：当 Playwright 测试运行失败时，让 LLM 修复测试代码

    参数:
        failed_code: 之前生成但运行失败的 Playwright 代码
        error_output: pytest 运行时的报错输出
        target_url: 目标 URL
        image_path: 可选截图路径
    """
    print("🔧 UI Generator (Fix Mode): 正在分析 Playwright 测试报错，修复中...")

    user_prompt = f"""
目标网页 URL：{target_url}

下面是运行失败的 Playwright 测试代码：
```python
{failed_code}
```

pytest 运行时的报错信息：
```
{error_output[-2000:]}
```

请分析报错原因（通常是选择器不对、元素未找到、断言错误等 UI 问题）并输出修复后的完整 Playwright 测试代码。
"""

    return _call_llm(user_prompt, image_path)


def analyze_root_cause(req: str, code: str, error: str, target_source: str) -> str:
    """
    3.2 核心功能：分析业务代码的根因并给出修复建议
    """
    print(f"🕵️‍♂️ RCA Engine: 正在深度分析业务逻辑缺陷...")
    
    user_prompt = f"""
【测试需求】: {req}
【运行报错】: {error}
【测试脚本代码】:
{code}

【被测业务代码】:
{target_source}

请根据以上信息，找出业务代码中的 Bug，并给出修复建议。
"""
    
    response = client.chat.completions.create(
        model="glm-4-flash",
        messages=[
            {"role": "system", "content": RCA_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1
    )
    return response.choices[0].message.content


def diagnose_ui_error(req: str, code: str, error: str, url: str, image_path: str = "") -> dict:
    """
    1.2 核心功能：诊断测试失败的根源
    返回字典：{"category": "...", "analysis": "...", "suggestion": "..."}
    """
    print(f"🔍 UI Generator (Diagnosis): 正在诊断测试失败原因...")
    dom_context = _get_dom_context(url)
    
    image_hint = ""
    if image_path and os.path.exists(image_path):
         image_hint = "【附带了崩溃瞬间的屏幕快照辅助，请结合截图中各元素的相对位置、遮挡关系等物理表现一并分析。】"
    
    user_prompt = f"""
【用户需求】: {req}
【测试代码】: 
```python
{code}
```
【报错信息】: 
{error[-2000:]}

【当前页面的真实 DOM Context】:
{dom_context}

{image_hint}
请给出你的诊断报告。
"""
    
    import json
    try:
        if image_path and os.path.exists(image_path):
            import base64
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            response = client.chat.completions.create(
                model="glm-4v",
                messages=[{
                    "role": "user",
                    "content": [
                         {"type": "text", "text": f"{DIAGNOSIS_SYSTEM_PROMPT}\n\n{user_prompt}"},
                         {"type": "image_url", "image_url": {"url": b64}}
                    ]
                }],
                temperature=0.1
            )
        else:
            response = client.chat.completions.create(
                model="glm-4-flash",
                messages=[
                    {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1
            )
        
        # 兼容性处理：无论模型废话多少，精准提取 JSON
        content = response.choices[0].message.content or ""
        match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if match:
            content = match.group(1).strip()
        else:
            # 兜底截断
            content = re.sub(r"^```json\s*", "", content.strip())
            content = re.sub(r"```$", "", content.strip())
        
        res = json.loads(content)
        return res
    except Exception as e:
        print(f"⚠️ UI Generator: 诊断过程出错 - {e}")
        return {
            "category": "ENVIRONMENT_ERROR",
            "analysis": f"诊断逻辑执行异常: {str(e)}",
            "suggestion": "请人工查阅日志"
        }
