import requests
import json
import re
from openai import OpenAI
import os

# 初始化客户端 (使用与 app.py 相同的配置)
client = OpenAI(
    api_key="00e9329ebd37421abdcd15fc9225aed0.8OVf4p6b3lxwTQVt",
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

API_TEST_SYSTEM_PROMPT = """你是一个资深的 API 测试专家。
你的任务是：根据提供的 API 文档（OpenAPI/Swagger）或接口描述，编写高质量的 Python pytest 自动化测试脚本。

【技术栈要求】:
- 使用 `pytest` 框架。
- 使用 `requests` 库发送 HTTP 请求。
- 断言应包括：状态码校验、响应体关键字段校验、数据结构校验。

【编写规范】:
1. 在脚本开头导入必要库：`import pytest`, `import requests`, `import json`。
2. 每一个 API 接口应生成至少两个测试用例：
    - 一个 **Positive Case** (正常参数，预期 2xx)。
    - 一个 **Negative Case** (缺失必填项或格式错误，预期 4xx)。
3. 使用 `pytest.mark.parametrize` 处理多组参数测试（如果适用）。
4. 允许通过全局变量 `BASE_URL` 和 `HEADERS` 来配置基础路径和认证信息。
5. 必须包含详细的中文注释，说明测试目的。

【输出格式】:
只输出一个 Python 文件的完整代码，不要有任何解析、不要加 ```python``` 包裹。
"""

def fetch_openapi_doc(url: str) -> str:
    """尝试抓取 Swagger/OpenAPI JSON 结构并精简"""
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            doc = resp.json()
            # 精简：只保留 paths 结构，避免 Token 消耗过大
            paths = doc.get("paths", {})
            return json.dumps({"paths": paths}, indent=2, ensure_ascii=False)[:3000] # 截断保护
    except Exception as e:
        return f"获取文档失败: {str(e)}"
    return "解析文档为空"

def generate_api_tests(doc_url_or_desc: str, requirements: str, headers_json: str = "{}") -> str:
    """
    生成 API 测试代码
    """
    print(f"🚀 API Generator: 正在为输入来源生成测试代码...")
    
    doc_context = ""
    # 判断输入是否为 URL
    if doc_url_or_desc.startswith("http"):
        doc_context = fetch_openapi_doc(doc_url_or_desc)
    else:
        doc_context = doc_url_or_desc

    try:
        headers = json.loads(headers_json)
    except:
        headers = {}

    user_prompt = f"""
【API 上下文/文档】:
{doc_context}

【附加测试需求】:
{requirements}

【环境配置】:
- BASE_URL: 如果文档中有指定则使用，否则请根据上下文推测一个默认值。
- DEFAULT_HEADERS: {json.dumps(headers)}

请生成完整的 API 测试脚本。
"""

    response = client.chat.completions.create(
        model="glm-4-flash",
        messages=[
            {"role": "system", "content": API_TEST_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1
    )

    code = response.choices[0].message.content or ""
    # 清理 markdown
    code = re.sub(r"^```python\s*", "", code.strip())
    code = re.sub(r"```$", "", code.strip())
    
    print(f"✨ API Generator: 成功生成 API 测试代码（{len(code)} 字符）")
    return code.strip()
