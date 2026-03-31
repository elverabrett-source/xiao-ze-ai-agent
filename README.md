# 🤖 小泽测试助手 (Xiao Ze AI Testing Assistant)

> **让 AI 成为你的首席测试工程师。**  
> 基于 LLM + Playwright + Pytest 的全栈式自动化测试智能体。

[![GitHub Repo](https://img.shields.io/badge/GitHub-Repository-blue?logo=github)](https://github.com/elverabrett-source/xiao-ze-ai-agent)
[![Tech Stack](https://img.shields.io/badge/Stack-FastAPI%20|%20React%20|%20Vite-green)](#)

## 🌟 项目亮点 (Key Highlights)

小泽不仅仅是一个测试工具，它是一个**具备自愈能力的测试智能体**。它能听懂你的自然语言指令，自动分析网页，编写脚本，并在脚本执行失败时通过“视觉+DOM”双重自省进行自我修复。

### 1. 💬 聊天驱动的测试流水线 (Chat-Driven)
无需编写繁琐的配置代码。你只需对它说：“帮我测一下百度搜索框的关键词提示功能”，小泽会自动：
*   识别意图并切换至 **UI 自动化模式**。
*   自动填充目标 URL 并准备测试环境。
*   实时流式输出测试执行日志。

### 2. 🧠 智能自愈系统 (Self-Correction)
*   **报错自诊断**：当 Playwright 脚本执行失败（如元素定位不到），小泽会深度扫描报错堆栈和 DOM 树。
*   **视觉快照分析**：自动捕捉失败瞬间的截图，并将截图发给大模型（如 GLM-4v）进行视觉比对。
*   **代码自动修正**：AI 会根据诊断结果重新生成并优化测试脚本，直到任务通过。

### 3. 🛡️ 稳如磐石的执行引擎
*   **双端实时通信**：基于 FastAPI 的流式输出，确保你在前端能看到毫秒级的进度响应。
*   **Windows 深度兼容**：特别优化了子进程管理与字符编码，支持 Windows 环境下的稳定长效运行。
*   **进程熔断机制**：提供始终在线的 [中止] 按钮，一键强制停止异常任务。

---

## 🛠️ 技术栈 (Tech Stack)

| 维度 | 技术选型 |
| :--- | :--- |
| **前端** | React 18, Vite, Tailwind CSS, Lucide Icons |
| **后端** | FastAPI (Python 3.10+), Uvicorn |
| **AI 核心** | GLM-4 / GPT-4o (支持多模态视觉) |
| **自动化框架** | Playwright (UI), Pytest (Unit/API) |
| **文档解析** | python-docx, PyPDF2 |

---

## 🚀 快速开始 (Quick Start)

### 1. 获取项目
```powershell
git clone https://github.com/elverabrett-source/xiao-ze-ai-agent.git
cd xiao-ze-ai-agent
```

### 2. 一键启动
项目内置了自愈启动器，会自动安装缺失依赖并清理端口：
```powershell
python start.py
```
*   **前端地址**：`http://localhost:3000`
*   **后端 API**：`http://localhost:8000`

---

## 📸 核心界面展示

*   **配置面板**：动态表单，根据测试场景自适应输入项。
*   **指令中心**：支持上传 PRD 文档或截图，进行多模态需求解析。
*   <img width="540" height="484" alt="image" src="https://github.com/user-attachments/assets/4b20a657-a396-421c-8bc5-062265a2491c" />

*   **执行监控器**：极客风 Terminal 风格，带有智能清理与中止功能。

---

## 📅 版本蓝图 (Roadmap)
- [x] UI/Unit/API 测试模式切换
- [x] Windows 环境稳定性加固
- [x] AI 控制 Token 智能联动
- [ ] 接入多 Agent 协同（开发、测试、运维三方会审）
- [ ] 自动化测试报告一键网页部署

---

> **“小泽，让天下没有难测的代码。”**  
> 开发者：[@elverabrett-source](https://github.com/elverabrett-source)
