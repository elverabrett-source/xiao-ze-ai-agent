import os
from openai import OpenAI
import re
import base64

# 我们复用你在 test.py 里面使用的智谱 API 配置
client = OpenAI(
    api_key="00e9329ebd37421abdcd15fc9225aed0.8OVf4p6b3lxwTQVt",
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

def _build_vision_kwargs(system_prompt: str, user_text: str, image_path: str = "") -> dict:
    """
    根据是否有图片，构造不同的大模型调用参数。
    如果有图片，使用 glm-4v 视觉模型；否则使用 glm-4-flash。
    注意：glm-4v 不支持 role=system，因此如果有图片就把 system 塞到 user 里。
    """
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
            
        return {
            "model": "glm-4v",
            "messages": [
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": f"{system_prompt}\\n\\n{user_text}"},
                        {"type": "image_url", "image_url": {"url": b64}}
                    ]
                }
            ]
        }
    else:
        return {
            "model": "glm-4-flash",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ]
        }

def _extract_python_code(raw_text: str) -> str:
    """通用的代码块提取工具函数"""
    match = re.search(r"```python\s*(.*?)\s*```", raw_text, re.DOTALL)
    if match: return match.group(1).strip()
    clean = re.sub(r"^```\w*\s*", "", raw_text.strip())
    clean = re.sub(r"```\s*$", "", clean.strip())
    return clean

def _call_agent(system_prompt: str, user_text: str, image_path: str = "") -> str:
    kwargs = _build_vision_kwargs(system_prompt, user_text, image_path)
    response = client.chat.completions.create(**kwargs, temperature=0.2)
    return response.choices[0].message.content.strip()

def generate_test_code(feature_desc: str, image_path: str = "") -> str:
    """
    基于 Multi-Agent 工作流，接收自然语言需求，生成 Pytest 测试代码。
    """
    print("🧠 Generator: 正在组建 API / 单元测试流水线团队...")
    image_hint = "【附带了场景截图，请看图分析边界场景】" if image_path else ""

    # ==========================
    # 角色 1：👨‍💼 需求分析师 Agent
    # ==========================
    print("\n[AGENT: 👨‍💼 需求分析] 正在将业务语言解构成原子测试边界点...")
    sys_analyst = "你是一名资深的测试需求分析师。你的任务是将模糊的业务逻辑描述解构成干练的测试点 Checklist（不需要写代码）。"
    user_analyst = f"待测业务描述：\n{feature_desc}\n{image_hint}\n请列出所有正常、边界、异常用例，保证测试覆盖率。"
    test_cases_plan = _call_agent(sys_analyst, user_analyst, image_path)
    print(f"[AGENT: 👨‍💼 需求分析] 提取分析完毕！产出摘要：{test_cases_plan[:200]}...\n")

    # ==========================
    # 角色 2：🧑‍💻 测试开发 Agent
    # ==========================
    print("[AGENT: 🧑‍💻 代码编排] 基于拟定的测试要求，正在编写高密度 Pytest 逻辑...")
    sys_coder = "你是一名顶级的 Python 测试开发专家。请严格只输出 Markdown 格式的 Python 代码块（使用 ```python）。"
    user_coder = f"""
业务上下文描述：
{feature_desc}

【已梳理的测试计划 Checklist】：
{test_cases_plan}

要求：
1. 必须使用 pytest 框架。
2. 包含所有的安排好的测试场景。
3. 如果不知道被测函数在哪导入，假设它在当前目录的同名模块中。
"""
    draft_code_raw = _call_agent(sys_coder, user_coder)
    draft_code = _extract_python_code(draft_code_raw)
    if not draft_code: return ""
    print(f"[AGENT: 🧑‍💻 代码编排] 测试初稿编写完成！（{len(draft_code)} 字符）\n")

    # ==========================
    # 角色 3：🕵️‍♂️ 审查官 Agent
    # ==========================
    print("[AGENT: 🕵️‍♂️ 审查官] 正在审查生成的脚本，寻找安全风险、死循环与遗漏依赖...")
    sys_critic = "你是一名严格的代码审查官。请审查下面待运行的测试代码。如果有问题，请直接输出修改后的完整代码；如果没有问题，原样输出。请始终使用 ```python 块返回代码。"
    user_critic = f"""
草稿代码：
```python
{draft_code}
```
请检查：
1. 是否缺少 `import pytest`？
2. 是否有严重语法错误或危险函数（os.system 等）？
"""
    final_code_raw = _call_agent(sys_critic, user_critic)
    final_code = _extract_python_code(final_code_raw)
    if not final_code: return draft_code

    print("[AGENT: 🕵️‍♂️ 审查官] 静态安全与逻辑审查通过，准予运行执行！🚦")
    return final_code

def fix_test_code(failed_code: str, error_msg: str, feature_desc: str, image_path: str = "") -> str:
    """
    【自我修复机制 (Self-Correction)】
    当 Executor 运行测试失败时，我们会把：
    1. 原始的需求描述 (feature_desc)
    2. 刚刚写错的代码 (failed_code)
    3. 终端里 pytest 弹出的红字报错 (error_msg)
    统一发给大模型，让大模型“知道错在哪里”，从而精准修复。
    """
    prompt = f"""
    你是一个骨灰级的 Python 测试工程师。你刚刚写的一段 `pytest` 测试代码运行失败了。
    请你根据以下的报错信息，修改测试代码，使其全部通过。

    【原始待测需求/函数描述】
    {feature_desc}

    【你刚刚写的失败测试代码】
    ```python
    {failed_code}
    ```

    【Pytest 的报错信息】
    {error_msg}

    【修复要求】
    1. **千万别忘了在代码开头加上 `import pytest`！** 你的上一个版本经常因为缺少 `import pytest` 导致 NameError。
    2. 如果是因为导入路径或者语法错误，请修改测试代码解决它。
    3. **【核心捉虫使命】**：如果测试报错是因为“被测代码的业务逻辑本身就写错了”（比如遇到被测函数抛出了莫名其妙的 ValueError 等），而你认为你原本写的测试用例是对的——**绝不要为了让测试通过而修改你的测试代码！** 
       你要做的是，直接在控制台输出：`BUG_DETECTED: <简短分析为什么是被测代码错了>`，**并且不要输出任何 Python 代码**。
    4. 只有当你明确是因为“你的测试用例写得有问题”时，才输出修复后的合法的 Python 代码（依然不要包含 Markdown 代码块修饰符）。
    """

    print("🧠 Generator (Fix Mode): 正在阅读报错信息，尝试修复测试代码...")
    
    try:
        kwargs = _build_vision_kwargs(
            system_prompt="你是一个严格只输出 Python 代码的机器，绝不输出其他多余字符。你的任务是修复代码BUG。",
            user_text=prompt,
            image_path=image_path
        )
        response = client.chat.completions.create(
            **kwargs,
            temperature=0.2 # 修复代码依然需要严谨，不能太发散
        )
        
        raw_code = response.choices[0].message.content.strip()
        
        match = re.search(r"```python\s*(.*?)\s*```", raw_code, re.DOTALL)
        if match:
            return match.group(1).strip()
            
        clean_code = re.sub(r"^```\w*\s*", "", raw_code)
        clean_code = re.sub(r"```\s*$", "", clean_code)
        
        return clean_code.strip()
        
    except Exception as e:
        print(f"❌ Generator 修复代码时发生错误: {e}")
        return ""

def improve_coverage(current_code: str, coverage_report: str, feature_desc: str, image_path: str = "") -> str:
    """
    【覆盖率提升机制 (Coverage Hunter)】
    当所有测试都通过，但覆盖率不到 100% 时，把覆盖率报告发给大模型。
    大模型需要阅读报告里面列出的 "Missing" 行号，专门为这些没跑到的行补充测试用例。
    """
    prompt = f"""
    你是一个骨灰级的 Python 测试工程师。你写的 `pytest` 测试代码目前已经全部通过了，干得好！
    但是，测试覆盖率尚未达到 100%。以下是 `pytest-cov` 给出的覆盖率报告。

    【被测源文件业务流】
    {feature_desc}

    【当前的测试代码】
    ```python
    {current_code}
    ```

    【Pytest 覆盖率报告 (含未覆盖行号 Missing lines)】
    {coverage_report}

    【补充测试要求】
    1. 请仔细阅读覆盖率报告中的 `Missing` 这一列，找出是哪些行代码没被覆盖到（比如 12-14 行）。
    2. 请分析为什么这些代码没被测到？（比如：是不是因为某个 if 分支没有写对应的测试用例？）
    3. **请在你现有的测试代码基础上，补充新的用例来覆盖这些漏掉的代码。**
    4. 依然要保持原本所有测试通过！
    5. **最重要的一点**：你必须且只能输出补充完整后的全新 Python 测试文件代码全文，不要有任何 Markdown 修饰符（比如 ```python ），也不要输出任何前言后语。
    """

    print("🧠 Generator (Coverage Mode): 正在分析覆盖率报告，专门补充遗漏用例...")
    
    try:
        kwargs = _build_vision_kwargs(
            system_prompt="你是一个严格只输出 Python 代码的机器，绝不输出其他多余字符。你的任务是提升测试用例的覆盖率。",
            user_text=prompt,
            image_path=image_path
        )
        response = client.chat.completions.create(
            **kwargs,
            temperature=0.3 # 提升覆盖率需要一点发散思维去猜补缺失逻辑
        )
        
        raw_code = response.choices[0].message.content.strip()
        
        match = re.search(r"```python\s*(.*?)\s*```", raw_code, re.DOTALL)
        if match:
            return match.group(1).strip()
            
        clean_code = re.sub(r"^```\w*\s*", "", raw_code)
        clean_code = re.sub(r"```\s*$", "", clean_code)
        
        return clean_code.strip()
        
    except Exception as e:
        print(f"❌ Generator 补充用例时发生错误: {e}")
        return ""

if __name__ == "__main__":
    # 简单测试一下
    test_desc = "一个计算两数相加的加法函数 add，只能接受数字，如果是字符串要抛出 TypeError"
    code = generate_test_code(test_desc)
    print("--- 生成的代码如下 ---")
    print(code)
