import streamlit as st
import subprocess
import os
import pathlib
import sys
import base64
import PyPDF2
from docx import Document
from openai import OpenAI
from streamlit_paste_button import paste_image_button
from agent.api_generator import generate_api_tests
from agent.executor import run_tests
from agent.visual_engine import run_visual_regression
from agent.ci_generator import generate_ci_config, save_ci_config

# ============ 智谱大模型客户端 ============
# 这是真正的"大脑"，它会直接被 app.py 调用来理解你说的话
client = OpenAI(
    api_key="00e9329ebd37421abdcd15fc9225aed0.8OVf4p6b3lxwTQVt",
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

def extract_req_text(uploaded_file):
    """从各种格式文件中提取纯文本内容"""
    if uploaded_file.name.endswith('.pdf'):
        reader = PyPDF2.PdfReader(uploaded_file)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    elif uploaded_file.name.endswith('.docx'):
        doc = Document(uploaded_file)
        return "\n".join([para.text for para in doc.paragraphs])
    else:
        return uploaded_file.getvalue().decode("utf-8", errors="ignore")

def chat_with_agent(user_message: str, image_pil=None, context_docs: str = ""):
    """
    直接和大模型对话（真正的智能体对话层）
    - 如果有图片，用 glm-4v 视觉模型
    - 如果只有文字，用 glm-4-flash
    返回值: (response_text, should_run_tests)
    大模型会在它认为需要生成并运行测试的时候，在回复末尾加上 [RUN_TESTS]
    """
    system_prompt = """你是一个专业的 AI 软件测试助手 (QA Agent)。
你只使用 **Python** 语言，不使用 JavaScript 或其他语言。
你的底层测试框架是 **pytest + playwright-python**。

你拥有以下能力：
1. 分析代码、图片、PRD 文档，理解业务逻辑
2. 回答用户关于测试、代码、系统设计的任何问题
3. 当用户**明确要运行测试**时，在你的回答最后加上 [RUN_TESTS]

**何时加 [RUN_TESTS]**:
- 用户说"帮我生成测试"、"运行测试"、"进行 UI 测试"、"测试这个URL"等明确执行请求 → 加 [RUN_TESTS]
- 用户只是问问题、要分析建议 → 不加

**重要**: 当用户配置信息里有 "目标 URL" 时，说明他们已经填好了 URL，你无需再询问，
只需确认你理解了他们的需求并回复即可（同时加上 [RUN_TESTS] 触发流水线）。

不要在回复中展示 Playwright 代码，你的底层系统会自动生成，你只需要对话即可。
"""

    full_user_content = user_message
    if context_docs:
        full_user_content += f"\n\n【用户上传的文档内容】\n{context_docs}"

    try:
        if image_pil is not None:
            # 有图片 → 转 base64 → 用 GLM-4V
            import io
            buf = io.BytesIO()
            image_pil.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

            response = client.chat.completions.create(
                model="glm-4v",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{system_prompt}\n\n{full_user_content}"},
                            {"type": "image_url", "image_url": {"url": b64}}
                        ]
                    }
                ],
                temperature=0.7
            )
        else:
            # 无图片 → 纯文本对话
            history = [{"role": "system", "content": system_prompt}]
            for msg in st.session_state.messages[-8:]:  # 最近8条历史
                history.append({"role": msg["role"], "content": msg["content"]})
            history.append({"role": "user", "content": full_user_content})

            response = client.chat.completions.create(
                model="glm-4-flash",
                messages=history,
                temperature=0.7
            )

        reply = response.choices[0].message.content or ""
        should_run_tests = "[RUN_TESTS]" in reply
        clean_reply = reply.replace("[RUN_TESTS]", "").strip()
        return clean_reply, should_run_tests

    except Exception as e:
        return f"❌ 与大模型通信时发生错误: {e}", False


def run_test_pipeline(target_file: str, test_file_out: str, desc: str, image_pil=None, req_docs: str = ""):
    """
    调用底层测试流水线（pytest 自动化链路）
    只有用户明确要求生成测试时才由 chat_with_agent 触发这个函数。
    """
    base_dir = pathlib.Path(__file__).resolve().parent
    cmd = [sys.executable, "-u", "agent/main.py", "--out", test_file_out]

    if target_file and target_file.strip():
        cmd.extend(["--file", target_file.strip()])
    if desc:
        cmd.extend(["--desc", desc])

    if req_docs:
        req_path = base_dir / "tests" / "req.txt"
        with open(req_path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(req_docs)
        cmd.extend(["--req-file", str(req_path)])

    if image_pil is not None:
        img_path = base_dir / "tests" / "req_image.png"
        image_pil.save(img_path, format="PNG")
        cmd.extend(["--image-file", str(img_path)])

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=base_dir,
        bufsize=1,
        encoding='utf-8',
        errors='replace',
        env=env
    )

# ============ 网页 UI ============
st.set_page_config(page_title="Obsidian Pulse AI QA", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# ============ 注入 Obsidian Pulse CSS ============
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Manrope:wght@500;700;800&display=swap');

/* 全局背景色、文本色与字体 */
html, body, [class*="css"], [data-testid="stAppViewContainer"], [data-testid="stHeader"], .stApp {
    background-color: #0B0E14 !important;
    color: #ECEDF6 !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stBottomBlockContainer"], [data-testid="stBottom"] > div {
    background-color: #0B0E14 !important;
}

h1, h2, h3, h4, h5, h6, p, span, label, div[data-testid="stMarkdownContainer"] * {
    font-family: 'Manrope', sans-serif !important;
    color: #ECEDF6 !important;
    letter-spacing: -0.01em;
}

h1, h2, h3 {
    color: #FFFFFF !important;
}

.stTextInput label, .stSelectbox label, .stTextArea label, .stFileUploader label {
    color: #85ADFF !important;
}

/* 侧边栏样式 */
[data-testid="stSidebar"] {
    background-color: #10131A !important;
    border-right: 1px solid rgba(115, 117, 125, 0.15) !important;
}

/* 顶部与底部的暗影过度 */
.stApp::before {
    content: "";
    position: fixed;
    top: 0; left: 0; width: 100%; height: 2px;
    background: linear-gradient(90deg, #3B82F6, #8B5CF6);
    z-index: 100;
}

/* 按钮 - Primary (带有渐变与发光效果) */
button[kind="primary"] {
    background: linear-gradient(45deg, #3B82F6, #8B5CF6) !important;
    border: none !important;
    border-radius: 0.75rem !important;
    color: #FFFFFF !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 700 !important;
    transition: all 0.3s ease !important;
}
button[kind="primary"]:hover {
    box-shadow: 0 0 15px rgba(139, 92, 246, 0.5) !important;
    transform: translateY(-1px);
}

/* 普通按钮 - Ghost/Outline 效果 */
button[kind="secondary"] {
    background-color: rgba(28, 32, 40, 0.6) !important;
    border: 1px solid rgba(133, 173, 255, 0.2) !important;
    border-radius: 0.75rem !important;
    color: #85ADFF !important;
    transition: all 0.3s ease !important;
}
button[kind="secondary"]:hover {
    background-color: rgba(59, 130, 246, 0.1) !important;
    border-color: #3B82F6 !important;
    box-shadow: 0 0 10px rgba(59, 130, 246, 0.3) !important;
}

/* 输入框、文本区与下拉框 */
.stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div, div.stChatInput {
    background-color: #1C2028 !important;
    color: #ECEDF6 !important;
    border: 1px solid rgba(115, 117, 125, 0.2) !important;
    border-radius: 0.5rem !important;
}
.stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus, .stSelectbox>div>div>div:focus, div.stChatInput:focus-within {
    border-color: #3B82F6 !important;
    box-shadow: 0 0 8px rgba(59, 130, 246, 0.3) !important;
}

/* 消息气泡 & Expander 卡片 - 玻璃拟态 (Glassmorphism) */
[data-testid="stExpander"], div[data-testid="stChatMessage"] {
    background-color: rgba(28, 32, 40, 0.6) !important;
    backdrop-filter: blur(16px);
    border: 1px solid rgba(115, 117, 125, 0.15) !important;
    border-radius: 0.75rem !important;
}

/* 区分 User 与 Assistant 的气泡边框 */
div[data-testid="stChatMessageContent"] {
    background: transparent !important;
}

/* Toggle 开关 */
.st-emotion-cache-1ebinxp { /* 假设这是 toggle 轨道的类名之一，Streamlit 会变但尽量用原生 */ }

/* 下拉选项背景 */
div[role="listbox"] {
    background-color: #1C2028 !important;
    border: 1px solid rgba(115, 117, 125, 0.2) !important;
}
div[role="option"]:hover, div[role="option"][aria-selected="true"] {
    background-color: rgba(59, 130, 246, 0.2) !important;
    color: #85ADFF !important;
}

/* 成功与失败的 Toast 提示条也可稍作深色处理，视具体结构而定 */

</style>
""", unsafe_allow_html=True)

st.title("⚡ The Ethereal Engine")
st.markdown("*Obsidian Pulse Command Center* —— 你的专属高级 AI 软件测试智能体。你可以输入命令、分析代码或直接执行全量测试流水线。")

with st.sidebar:
    st.markdown("### ⚙️ Command Configuration")
    st.caption("Intelligence Core Parameters (仅自动运行测试时生效)")
    
    test_type = st.selectbox(
        "🧪 测试类型",
        ["接口/单元测试 (Unit)", "UI 自动化测试 (Playwright)", "API 接口测试 (Swagger)", "视觉回归测试 (Visual)", "全量自动化测试 (Full Suite)"],
        index=0
    )
    
    # 接口测试配置
    if test_type in ["接口/单元测试 (Unit)", "全量自动化测试 (Full Suite)"]:
        target_file = st.text_input("待测文件路径", value="", placeholder="例如 src/math_utils.py（可选）")
        test_file_out = st.text_input("测试输出文件名称", value="", placeholder="例如 test_generated.py（可选）")
    elif test_type == "API 接口测试 (Swagger)":
        target_file = st.text_input("🔗 Swagger URL / 接口描述", value="", placeholder="https://petstore.swagger.io/v2/swagger.json")
        test_file_out = st.text_input("API 测试输出文件名", value="test_api_generated.py")
        api_headers = st.text_area("🔑 认证 Headers (JSON)", value="{}", help="例如 {'Authorization': 'Bearer xxx'}")
    else:
        target_file = ""
        test_file_out = "test_generated.py"
    
    # UI 测试配置
    if test_type in ["UI 自动化测试 (Playwright)", "全量自动化测试 (Full Suite)", "视觉回归测试 (Visual)"]:
        target_url = st.text_input("🌐 目标网页 URL", value="", placeholder="https://example.com")
        if test_type == "视觉回归测试":
            visual_name = st.text_input("📸 视觉基准名称", value="homepage")
        else:
            ui_test_out = st.text_input("UI 测试文件名", value="test_ui.py")
        ui_req_input = st.text_area(
            "📋 测试需求描述",
            value="",
            placeholder="例如：测试登录功能，输入错误密码时应显示错误提示；测试搜索框能正常返回结果...",
            height=100
        )
    else:
        target_url = ""
        ui_test_out = "test_ui.py"
        ui_req_input = ""
    
    auto_run = st.toggle("🚀 满足条件时自动执行测试", value=True)
    if not auto_run:
        st.caption("关闭状态下，AI 只分析和回答，不会自动跑测试。")
    
    st.markdown("---")
    run_now = st.button("⚡ EXECUTE PIPELINE", type="primary", use_container_width=True)
    st.caption("忽略 AI 对话，直接启动测试流水线")
    
    mutation_run = st.button("☢️ MUTATION ENGINE (Kill-Rate)", use_container_width=True)
    st.caption("评估测试用例对逻辑漏洞的查杀强度 (需指定靶标文件)")

    st.markdown("---")
    st.markdown("### 📦 Pipeline Generation")
    ci_platform = st.selectbox("目标平台", ["GitHub Actions", "GitLab CI"])
    ci_test_types = st.multiselect(
        "包含的测试类型",
        ["unit", "ui", "api", "visual"],
        default=["unit"]
    )
    export_ci = st.button("🚀 GENERATE CI CONFIG", use_container_width=True)

    st.markdown("---")
    st.markdown("### 📂 Context & Attachments")
    req_file = st.file_uploader("Document (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"])
    img_file = st.file_uploader("Reference Image (JPG/PNG)", type=["png", "jpg", "jpeg"])

    st.caption("Or Paste Image:")
    if "paste_key" not in st.session_state:
        st.session_state.paste_key = 0
    paste_result = paste_image_button(
        label="📋 Ctrl+V (Paste)",
        background_color="#FF4B4B",
        hover_background_color="#FF6B6B",
        errors='ignore',
        key=f"paste_btn_{st.session_state.paste_key}"
    )
    if paste_result.image_data is not None:
        st.session_state.pasted_image = paste_result.image_data
    if "pasted_image" in st.session_state and st.session_state.pasted_image is not None:
        st.success("图片已准备好！")
        st.image(st.session_state.pasted_image, width=180)
        if st.button("🗑️ 清除图片"):
            st.session_state.pasted_image = None
            st.session_state.paste_key += 1
            st.rerun()

# ============ 聊天主界面 ============
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ============ 直接运行测试按钮处理 ============
if run_now:
    with st.chat_message("assistant"):
        st.markdown(f"**⚡ INITIATING [{test_type}] TEST SUITE...**")
        
        # 收集图片（如有）
        direct_image = None
        if "pasted_image" in st.session_state and st.session_state.pasted_image is not None:
            direct_image = st.session_state.pasted_image
            st.session_state.pasted_image = None
            st.session_state.paste_key += 1
        
        # 1. 接口/单元测试
        if test_type in ["接口/单元测试 (Unit)", "全量自动化测试 (Full Suite)"]:
            st.markdown("### 🧪 单元/接口测试 (Pytest)")
            log_container = st.empty()
            process = run_test_pipeline(target_file, test_file_out, "", direct_image, "")
            full_logs = ""
            for line in process.stdout:
                full_logs += line + "\n"
                # 对单元测试日志也进行精简显示，并捕获 RCA 关键词
                if any(k in line for k in ["正在", "✨", "✅", "❌", "⚠️", "🚨", "定位", "结论", "修复建议", "---", "🕵️‍♂️"]):
                    log_container.markdown(f"```text\n{full_logs.splitlines()[-10:]}\n```")
                else:
                    # 如果日志太乱，至少保证最后几行可见
                    log_container.markdown(f"```text\n{line}\n```")
            process.wait()
            if process.returncode == 0:
                st.success("✅ 单元测试全部通过！")
            else:
                st.error("🚨 单元测试存在失败！")
        
        # 2. API 测试 (Requests)
        if test_type == "API 接口测试 (Swagger)":
            st.markdown("### 🔗 API 接口测试 (Swagger)")
            if not target_file:
                st.warning("⚠️ 请输入 Swagger URL 或接口描述！")
            else:
                with st.spinner("🧠 AI 正在解析文档并生成 API 测试用例..."):
                    api_code = generate_api_tests(target_file, "请覆盖核心业务接口的增删改查", api_headers)
                    if api_code:
                        with st.expander("📝 查看生成的 API 测试源码", expanded=False):
                            st.code(api_code, language="python")
                        
                        # 运行测试
                        st.markdown("**🚀 正在运行 API 测试...**")
                        test_file_path = pathlib.Path(__file__).resolve().parent / "tests" / test_file_out
                        test_file_path.parent.mkdir(exist_ok=True)
                        with open(test_file_path, "w", encoding="utf-8") as f:
                            f.write(api_code)
                        
                        success, output = run_tests(str(test_file_path))
                        st.text_area("API 测试完整日志", output, height=250)
                        if success:
                            st.success("✅ 所有 API 接口测试通过！")
                        else:
                            st.error("🚨 API 测试存在失败点，请检查接口状态。")

        # 3. UI 测试 (Playwright)
        if test_type in ["UI 自动化测试 (Playwright)", "全量自动化测试 (Full Suite)", "视觉回归测试 (Visual)"]:
            st.markdown("### 🌐 UI 自动化测试 (Playwright)")
            if not target_url:
                st.warning("⚠️ 请先填写目标网页 URL！")
            else:
                st.markdown(f"**目标 URL: `{target_url}`**")
                ui_log_container = st.empty()
                img_path_str = ""
                if direct_image:
                    import io
                    img_save_path = pathlib.Path(__file__).resolve().parent / "tests" / "req_image.png"
                    direct_image.save(img_save_path, format="PNG")
                    img_path_str = str(img_save_path)
                
                ui_cmd = [sys.executable, "-u", "agent/ui_main.py", "--url", target_url, "--out", ui_test_out]
                if ui_req_input:
                    ui_cmd.extend(["--req", ui_req_input])
                if img_path_str:
                    ui_cmd.extend(["--img", img_path_str])
                
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                base_dir = pathlib.Path(__file__).resolve().parent
                ui_process = subprocess.Popen(ui_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                               text=True, cwd=base_dir, bufsize=1, encoding="utf-8",
                                               errors="replace", env=env)
                ui_logs = ""
                clean_logs = []
                for line in ui_process.stdout:
                    ui_logs += line + "\n"
                    # 只保留业务日志、诊断日志、报警日志以及 RCA 结果
                    if any(k in line for k in ["正在", "诊断", "结论", "理由", "建议", "报警", "定位", "修复建议", "FAILED ", "PASSED ", "🕵️‍♂️"]):
                        clean_logs.append(line.strip())
                        display_logs = clean_logs[-10:] if len(clean_logs) > 10 else clean_logs
                        ui_log_container.markdown("\n".join([f"- {l}" for l in display_logs]))
                ui_process.wait()

                # --- 尝试解析错误原因 ---
                error_summary = ""
                if ui_process.returncode != 0:
                    for line in reversed(ui_logs.split('\n')):
                        if "E   " in line or "AssertionError" in line:
                            error_summary = line.replace("E   ", "").strip()
                            break

                if ui_process.returncode == 0:
                    st.success("✅ UI 测试全部通过！")
                else:
                    st.error(f"🚨 UI 测试存在失败！\n\n**报错摘要：** {error_summary or '可能遇到了 Bug，请看上方 AI 诊断'}")

                # 展示截图
                res_img_path = base_dir / "tests" / "ui_result.png"
                if res_img_path.exists():
                    st.image(str(res_img_path), caption="最终执行截图")
        
        if test_type == "视觉回归测试 (Visual)":
            if not target_url:
                st.warning("⚠️ 请先填写目标网页 URL！")
            else:
                with st.spinner("🔍 正在捕获快照并对比视觉基准..."):
                    res = run_visual_regression(target_url, visual_name, ui_req_input)
                    
                    st.divider()
                    st.subheader(f"📊 视觉回归报告: {res['status']}")
                    st.info(res['msg'])
                    
                    if "report" in res:
                        with st.expander("🧐 AI 深度诊断结论", expanded=True):
                            st.write(res['report'])
                    
                    if "baseline" in res:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.image(res['baseline'], caption="基准图 (Baseline)")
                        with col2:
                            st.image(res['current'], caption="当前图 (Current)")
                        with col3:
                            if res['diff']:
                                st.image(res['diff'], caption="差异热图 (Diff Map)")
                            else:
                                st.write("✅ 未检测到像素级差异")

# ============ 导出 CI/CD 配置 ============
if "export_ci" in locals() and export_ci:
    with st.chat_message("assistant"):
        platform_key = "github" if ci_platform == "GitHub Actions" else "gitlab"
        st.markdown(f"**📦 正在为 {ci_platform} 生成 CI/CD 配置...**")
        
        yaml_content = generate_ci_config(platform_key, ci_test_types)
        
        # 预览
        st.code(yaml_content, language="yaml")
        
        # 保存到项目
        base_dir = pathlib.Path(__file__).resolve().parent
        saved_path = save_ci_config(platform_key, yaml_content, str(base_dir))
        st.success(f"✅ 配置文件已保存至: `{saved_path}`")
        
        # 提供下载
        file_name = "ai-test.yml" if platform_key == "github" else ".gitlab-ci.yml"
        st.download_button(
            label="⬇️ 下载配置文件",
            data=yaml_content,
            file_name=file_name,
            mime="text/yaml"
        )

if "mutation_run" in locals() and mutation_run:
    if not target_file or not test_file_out:
        st.warning("⚠️ 运行变异测试需要先在左侧填写【待测文件路径】和【输出文件名】！")
    else:
        with st.chat_message("assistant"):
            st.markdown(f"**☢️ MUTATION ENGINE ACTIVE: Targeting `{target_file}`...**")
            log_container = st.empty()
            
            # 由于变异测试是阻塞式的，我们直接调用 mutation_main
            mu_cmd = [sys.executable, "-u", "agent/mutation_main.py", "--file", target_file, "--test", f"tests/{test_file_out}"]
            
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            base_dir = pathlib.Path(__file__).resolve().parent
            
            mu_process = subprocess.Popen(mu_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           text=True, cwd=base_dir, bufsize=1, encoding="utf-8",
                                           errors="replace", env=env)
            mu_logs = ""
            for line in mu_process.stdout:
                mu_logs += line + "\n"
                log_container.markdown(f"```text\n{mu_logs}\n```")
            mu_process.wait()
            st.success("🎯 变异测试完成！请查阅上方日志中的【杀伤率】评价。")

# ============ 聊天输入处理 ============
if prompt := st.chat_input("Enter command, ask a query, or type 'run tests'..."):
    # 收集当前上下文
    active_image = None
    if img_file is not None:
        from PIL import Image
        import io
        active_image = Image.open(io.BytesIO(img_file.getvalue()))
    elif "pasted_image" in st.session_state and st.session_state.pasted_image is not None:
        active_image = st.session_state.pasted_image
        # 图片使用一次就清除，不让它持续附带在之后的每条消息里
        st.session_state.pasted_image = None
        st.session_state.paste_key += 1

    doc_text = ""
    if req_file is not None:
        doc_text = extract_req_text(req_file)

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if active_image:
            st.image(active_image, width=150, caption="附带的图片")

    with st.chat_message("assistant"):
        # 把侧边栏的配置信息注入到对话上下文，让 AI 知道用户的测试环境配置
        sidebar_context = f"\n\n【当前测试配置】测试类型: {test_type}"
        if target_url:
            sidebar_context += f" | 目标 URL: {target_url}"
        if target_file:
            sidebar_context += f" | 待测文件: {target_file}"
        
        with st.spinner("⚡ Cognitive Engine is processing..."):
            reply, should_run_tests = chat_with_agent(prompt + sidebar_context, active_image, doc_text)

        st.markdown(reply)

        if should_run_tests and auto_run:
            
            # --- 接口/单元测试流水线 ---
            if test_type in ["接口/单元测试 (pytest)", "两种都要"]:
                st.markdown("---")
                st.markdown("**🚀 检测到测试生成请求，正在启动 pytest 流水线...**")
                log_container = st.empty()
                process = run_test_pipeline(target_file, test_file_out, prompt, active_image, doc_text)
    
                full_logs = ""
                for line in process.stdout:
                    full_logs += line + "\n"
                    log_container.markdown(f"```text\n{full_logs}\n```")
                process.wait()
    
                if process.returncode == 0:
                    st.success("✅ 单元测试流水线执行完毕！")
                else:
                    st.error("🚨 单元测试执行遇到问题！")
                reply += f"\n\n```text\n{full_logs}\n```"

            # --- UI 测试流水线 (Playwright) ---
            if test_type in ["UI 测试 (Playwright)", "两种都要"]:
                st.markdown("---")
                if not target_url:
                    st.warning("⚠️ 请在左侧配置中填写目标网页 URL，才能运行 UI 测试！")
                else:
                    st.markdown(f"**🌐 正在启动 Playwright UI 测试 → `{target_url}`...**")
                    ui_log_container = st.empty()
                    
                    # 组合 UI 测试需求文本
                    ui_req = prompt
                    if doc_text:
                        ui_req += f"\n\n【背景需求文档】\n{doc_text[:3000]}"
                    
                    # 构建命令
                    img_path_str = ""
                    if active_image:
                        import pathlib, io
                        img_save_path = pathlib.Path(__file__).resolve().parent / "tests" / "req_image.png"
                        active_image.save(img_save_path, format="PNG")
                        img_path_str = str(img_save_path)
                    
                    ui_cmd = [
                        sys.executable, "-u", "agent/ui_main.py",
                        "--url", target_url,
                        "--req", ui_req,
                        "--out", ui_test_out,
                    ]
                    if img_path_str:
                        ui_cmd.extend(["--img", img_path_str])
                        
                    env = os.environ.copy()
                    env["PYTHONIOENCODING"] = "utf-8"
                    base_dir = pathlib.Path(__file__).resolve().parent
                    
                    ui_process = subprocess.Popen(
                        ui_cmd,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, cwd=base_dir,
                        bufsize=1, encoding="utf-8", errors="replace", env=env
                    )
                    ui_logs = ""
                    clean_logs = []
                    for line in ui_process.stdout:
                        ui_logs += line + "\n"
                        # 过滤冗余，保留关键诊断与执行信息
                        if any(k in line for k in ["正在", "诊断", "结论", "理由", "建议", "报警", "FAILED ", "PASSED "]):
                            clean_logs.append(line.strip())
                            display_logs = clean_logs[-10:] if len(clean_logs) > 10 else clean_logs
                            ui_log_container.markdown("\n".join([f"- {l}" for l in display_logs]))
                    ui_process.wait()

                    # --- 解析错误原因 ---
                    error_summary = ""
                    if ui_process.returncode != 0:
                        for line in reversed(ui_logs.split('\n')):
                            if "E   " in line or "AssertionError" in line:
                                error_summary = line.replace("E   ", "").strip()
                                break
                    
                    # --- 新增：展示生成的代码 ---
                    try:
                        with open(base_dir / "tests" / ui_test_out, "r", encoding="utf-8") as f:
                            generated_code = f.read()
                        with st.expander("📝 查看本次生成的 UI 测试源码", expanded=False):
                            st.code(generated_code, language="python")
                    except: pass

                    # --- 新增：展示截图结果 ---
                    res_img_path = base_dir / "tests" / "ui_result.png"
                    if res_img_path.exists():
                        st.image(str(res_img_path), caption="📸 UI 测试执行最终截图")

                    if ui_process.returncode == 0:
                        st.success("✅ UI 测试全部通过！")
                    else:
                        st.error(f"🚨 UI 测试存在失败！\n\n**报错摘要：** {error_summary or '未知错误，请查看下方日志或源码'}")
                    reply += f"\n\n**UI 测试日志：**\n```text\n{ui_logs}\n```"

        st.session_state.messages.append({"role": "assistant", "content": reply})
