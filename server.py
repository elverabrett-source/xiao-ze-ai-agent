import json
import os
import sys
import subprocess
import asyncio
import pathlib
import base64
import re
from datetime import datetime
from typing import Optional, List

import queue
import threading

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import PyPDF2
from docx import Document

# 导入业务 Agent 模块
from agent.api_generator import generate_api_tests
from agent.executor import run_tests
from agent.visual_engine import run_visual_regression
from agent.ci_generator import generate_ci_config, save_ci_config

app = FastAPI(title="Xiao Ze AI Testing Assistant")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AI 客户端初始化
client = OpenAI(
    api_key="00e9329ebd37421abdcd15fc9225aed0.8OVf4p6b3lxwTQVt",
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

# ===== 全局状态追踪 =====
last_test_context = {
    "logs": [],
    "test_type": "",
    "target_file": "",
    "target_url": "",
    "start_time": "",
    "end_time": "",
    "exit_code": None
}

# 全局进程对象，用于一键中断
global_test_process: Optional[asyncio.subprocess.Process] = None

def extract_req_text(uploaded_file, filename):
    """提取上传文档的文本内容"""
    try:
        if filename.endswith('.pdf'):
            reader = PyPDF2.PdfReader(uploaded_file.file)
            return "\n".join([page.extract_text() or "" for page in reader.pages])
        elif filename.endswith('.docx'):
            doc = Document(uploaded_file.file)
            return "\n".join([para.text for para in doc.paragraphs])
        return ""
    except Exception as e:
        return f"Error extracting text: {str(e)}"

# --- 1. AI 聊天与意图识别 ---
@app.post("/api/chat")
async def chat_with_ai(
    prompt: str = Form(...),
    history_json: str = Form("[]"),
    test_type: str = Form(""),
    target_url: str = Form(""),
    target_file: str = Form(""),
):
    import json
    try:
        # 解析历史对话
        history = json.loads(history_json) if history_json else []
        
        # 构建上下文感知的系统提示
        context_info = ""
        if test_type: context_info += f"\n当前测试模式: {test_type}"
        if target_url: context_info += f"\n当前目标URL: {target_url}"
        if target_file: context_info += f"\n当前目标文件: {target_file}"

        system_prompt = f"""你是一个UI自动化测试专家助手，名叫"小泽"。你能帮助用户执行测试、分析需求。{context_info}

【关键行为规则 - 必须严格遵守】：
1. 当用户说"跑"、"执行"、"运行"、"go"、"开始"、"run"、"测一下"、"试试"等词 → 你必须立刻在回复末尾加 [RUN_TESTS]，不要再问问题！
2. 当对话中已经明确了测试目标（URL或文件）后，用户要求执行 → 直接 [RUN_TESTS]
3. 只有在完全没有任何测试目标信息时，才能问一次确认

【控制指令】（附加在回复末尾，用户不可见）：
- [SET_MODE:UI] - 切换到UI自动化测试模式（用于网页测试）
- [SET_MODE:UNIT] - 切换到接口/单元测试模式
- [SET_MODE:NORMAL] - 切换到常规模式
- [SET_URL:https://...] - 同步目标URL
- [RUN_TESTS] - 立即触发测试执行

【模式判断】：
- 提到"UI"、"网页"、"浏览器"、"Playwright"、某个网站URL → [SET_MODE:UI]
- 提到"单元测试"、"接口测试"、某个文件 → [SET_MODE:UNIT]
- 提到"百度" → [SET_URL:https://www.baidu.com]，并 [SET_MODE:UI]
- 提到"谷歌" → [SET_URL:https://www.google.com]，并 [SET_MODE:UI]

规则优先级：执行意图 > 一切。有执行命令就必须加 [RUN_TESTS]。"""

        # 构建消息列表（包含历史）
        messages = [{"role": "system", "content": system_prompt}]
        # 添加历史（最多保留最近10条）
        for h in history[-10:]:
            role = h.get("role", "user")
            content = h.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        # 添加当前消息
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=messages
        )
        reply = response.choices[0].message.content
        should_run_tests = "[RUN_TESTS]" in reply
        # 清洗所有控制指令后再返回给用户
        clean_reply = reply.replace("[RUN_TESTS]", "").strip()
        return {"reply": clean_reply, "should_run_tests": should_run_tests}
    except Exception as e:
        return {"reply": f"❌ AI 出错: {str(e)}", "should_run_tests": False}


# --- 2. 核心测试运行流水线 (异步流式输出) ---
@app.post("/api/test/run")
async def run_test_endpoint(
    target_file: str = Form(""),
    test_file_out: str = Form("test_generated.py"),
    desc: str = Form(""),
    target_url: str = Form(""),
    test_type: str = Form("Unit"),
    context_file: Optional[UploadFile] = File(None),
    image_file: Optional[UploadFile] = File(None)
):
    async def stream_logs():
        # 重要：立即 yield 确保 HTTP 连接建立，防止 Network Error
        yield "[SYSTEM] 📡 正在建立双向通信链路并准备测试沙箱...\n"
        global last_test_context, global_test_process
        collected_logs = []
        
        try:
            # 初始化本次运行上下文
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            last_test_context.update({
                "logs": [], "test_type": test_type, "target_file": target_file,
                "target_url": target_url, "start_time": current_time, "exit_code": None
            })
            
            base_dir = pathlib.Path(__file__).resolve().parent
            
            # 1. 尝试从描述中嗅探并同步 URL
            effective_url = target_url  # 使用本地副本，避免 Python 闭包作用域错误
            url_match = re.search(r'(https?://[^\s)\]]+)', desc or "")
            if url_match and (not target_url or "baidu" in target_url or "example" in target_url):
                effective_url = url_match.group(1)
                last_test_context["target_url"] = effective_url

            # 2. 路由逻辑：API 还是 UI/Unit
            if test_type == "API 接口测试 (Swagger)":
                yield "[SYSTEM] 🧠 AI 正在解析接口并生成 Pytest 用例...\n"
                api_code = generate_api_tests(target_file, "API 扫描", {"Auth": "Bearer token"})
                test_path = base_dir / "tests" / test_file_out
                test_path.parent.mkdir(exist_ok=True)
                with open(test_path, "w", encoding="utf-8") as f: f.write(api_code)
                success, output = run_tests(str(test_path))
                for line in output.split('\n'): yield f"{line}\n"
                return

            # 3. 构建命令行执行指令
            is_ui = "UI" in test_type or "playwright" in test_type.lower() or (url_match and "Unit" in test_type)
            if is_ui:
                cmd = [sys.executable, "-u", "agent/ui_main.py", "--url", effective_url or "https://mail.qq.com", "--out", test_file_out]
                if desc: cmd.extend(["--req", desc])
            else:
                cmd = [sys.executable, "-u", "agent/main.py", "--out", test_file_out]
                if target_file: cmd.extend(["--file", target_file])
                if desc: cmd.extend(["--desc", desc])

            # 4. 文档与图像附件注入
            if context_file and context_file.filename:
                txt = extract_req_text(context_file, context_file.filename)
                req_path = base_dir / "tests" / "req.txt"
                with open(req_path, "w", encoding="utf-8") as f: f.write(txt)
                cmd.extend(["--req-file", str(req_path)])
            if image_file and image_file.filename:
                img_path = base_dir / "tests" / "req_image.png"
                with open(img_path, "wb") as f: f.write(await image_file.read())
                cmd.extend(["--img" if is_ui else "--image-file", str(img_path)])

            # 5. 用 subprocess.Popen + 线程队列 实现稳定的流式输出（兼容 Windows）
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(base_dir),
                env=env
            )
            global_test_process = process

            log_queue = queue.Queue()

            def _reader(proc, q):
                try:
                    for raw in iter(proc.stdout.readline, b''):
                        q.put(raw.decode('utf-8', errors='replace'))
                finally:
                    q.put(None)  # 哨兵，表示结束

            reader_thread = threading.Thread(target=_reader, args=(process, log_queue), daemon=True)
            reader_thread.start()

            # 6. 主线程从队列取日志，yield 给前端
            while True:
                try:
                    line = log_queue.get(timeout=0.5)
                    if line is None:
                        break
                    collected_logs.append(line.rstrip())
                    yield line
                except queue.Empty:
                    if process.poll() is not None:
                        break
                    await asyncio.sleep(0.1)

            process.wait()
            yield f"\n[Process Completed with Exit Code {process.returncode}]\n"

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            error_msg = f"\n[CRITICAL ERROR] 流水线执行中止: {str(e)}\n{tb}\n"
            collected_logs.append(error_msg)
            yield error_msg

        finally:
            global_test_process = None
            last_test_context["logs"] = collected_logs
            last_test_context["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if 'process' in locals() and hasattr(process, 'returncode'):
                last_test_context["exit_code"] = process.returncode

    return StreamingResponse(stream_logs(), media_type="text/plain")

# --- 3. 进程熔断与停止 ---
@app.post("/api/test/stop")
async def stop_test():
    global global_test_process
    if global_test_process and global_test_process.returncode is None:
        try:
            pid = global_test_process.pid
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
            else:
                global_test_process.terminate()
            global_test_process = None
            return {"status": "success", "message": f"任务已强制终止 (PID: {pid})"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "info", "message": "当前没有活跃任务"}

# --- 4. 报告导出 ---
@app.get("/api/report/export")
async def export_report():
    if not last_test_context["logs"]:
        return JSONResponse({"status": "error", "message": "没有可用的测试历史记录，请先运行测试"}, status_code=400)
    
    report_content = f"""# 小泽测试助手 - 执行报告
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
测试类型: {last_test_context['test_type']}
目标 URL: {last_test_context['target_url']}
启动时间: {last_test_context['start_time']}
结束时间: {last_test_context['end_time']}
状态码: {last_test_context['exit_code']}

## 执行日志概要
```text
{"\n".join(last_test_context['logs'][-20:])}
```
"""
    export_path = pathlib.Path("tests/test_report.md")
    with open(export_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    return FileResponse(path=export_path, filename="test_report.md", media_type='text/markdown')

# --- 5. 变异测试引擎 (Mutation Engine) ---
@app.post("/api/mutation/run")
async def run_mutation_pipeline(
    target_file: str = Form(...),
    test_file: str = Form(...)
):
    async def mutate_stream():
        yield "[SYSTEM] 🕵️‍♂️ 正在初始化 AI 变异引擎，挂载业务代码...\n"
        base_dir = pathlib.Path(__file__).resolve().parent
        cmd = [sys.executable, "agent/mutation_main.py", "--file", target_file, "--test", test_file]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=base_dir
        )
        while True:
            line = await process.stdout.readline()
            if not line: break
            yield line.decode('utf-8', errors='replace')
        await process.wait()

    return StreamingResponse(mutate_stream(), media_type="text/plain")

# --- 6. 视觉自愈诊断 (Visual Self-Healing) ---
@app.post("/api/visual/scan")
async def run_visual_scan(url: str = Form(...), name: str = Form("default"), req: str = Form("")):
    try:
        result = run_visual_regression(url, name, req)
        return result
    except Exception as e:
        return {"status": "error", "message": f"视觉扫描失败: {str(e)}"}

# --- 7. CI 配置生成 (CI/CD) ---
@app.post("/api/ci/generate")
async def generate_ci(platform: str = Form("Github Actions")):
    try:
        config = generate_ci_config(platform)
        save_ci_config(config, platform)
        return {"status": "success", "config": config}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
