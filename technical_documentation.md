# 项目技术文档 (AI 测试智能体)

## 1. 项目概览
本项目实现了一个 **AI 驱动的测试智能体**，能够根据用户提供的代码、文档、图片等多模态输入，自动生成 **单元测试 (pytest)** 与 **UI 测试 (Playwright)**，并可通过 Streamlit UI 交互式触发。

## 2. 目录结构
```
AI-test/
├─ app.py                 # Streamlit 前端入口，负责 UI、参数收集、调用后端
├─ agent/
│   ├─ main.py            # LLM 调用入口，解析用户意图并返回回复
│   ├─ generator.py       # 生成 pytest 测试代码的模块
│   ├─ executor.py        # 执行 pytest 测试的模块
│   ├─ ui_generator.py    # 生成 Playwright UI 测试代码的模块（基于系统提示）
│   ├─ ui_executor.py     # 执行 Playwright 测试的模块（无头模式）
│   └─ ui_main.py         # 统一入口，接收 URL、需求描述等参数并调用 ui_generator
├─ src/
│   └─ math_utils.py      # 示例业务代码（可自行替换）
├─ tests/
│   ├─ test_math_utils.py # 示例单元测试（由 AI 生成）
│   └─ test_ui.py         # 示例 UI 测试（Playwright）
└─ requirements.txt       # 项目依赖（streamlit, pytest, playwright, …）
```

## 3. 关键功能
| 功能 | 实现位置 | 说明 |
|------|----------|------|
| **多模态输入** | `app.py` | 支持文件上传（PDF/DOCX/TXT）和剪贴板图片粘贴（`streamlit-paste-button`） |
| **自动生成单元测试** | `agent/generator.py` | 根据代码、文档、图片生成 pytest 测试文件 |
| **自动生成 UI 测试** | `agent/ui_generator.py` | 根据 URL 与需求描述生成 Playwright 测试脚本 |
| **意图检测 & 自动触发** | `agent/main.py` + `app.py` | 当用户明确请求生成/运行测试时，在回复末尾添加 `[RUN_TESTS]`，`app.py` 捕获并启动相应流水线 |
| **手动运行开关** | `app.py` | 侧边栏 `🚀 AI 说需要测试时自动触发 pytest`（默认开）以及 `▶️ 立即运行测试` 按钮（绕过 LLM） |
| **测试流水线** | `agent/executor.py` / `agent/ui_executor.py` | 调用 `pytest` 或 `playwright`，实时在 UI 中展示日志 |

## 4. 环境与依赖
```bash
# 推荐使用 Python 3.10+
pip install -r requirements.txt
# 安装 Playwright 浏览器（首次运行后）
playwright install
```
`requirements.txt` 包含：
- streamlit
- pytest
- pytest-playwright
- playwright
- openai (或对应的 LLM SDK)
- PyPDF2、python-docx（文档解析）
- streamlit-paste-button（剪贴板图片）

## 5. 启动方式
### 5.1 启动 UI
```bash
python -m streamlit run app.py
```
打开浏览器后左侧面板可配置：
- **测试类型**：单元测试 / UI 测试 / 两者都要
- **待测文件**、**测试输出文件**（可选）
- **目标网页 URL**（UI 测试必填）
- **测试需求描述**（多行文本，可自行补充）
- **自动触发开关** 与 **立即运行按钮**

### 5.2 运行测试
- **自动模式**：在聊天框输入 `帮我生成测试`、`进行 UI 测试` 等，AI 会在回复后自动触发对应流水线。
- **手动模式**：勾选/取消自动开关后，点击 **▶️ 立即运行测试** 按钮，直接启动选中的测试类型。

## 6. 生成的测试文件位置
- 单元测试文件：`tests/<test_file_out>.py`（默认 `test_generated.py`）
- UI 测试文件：`tests/<ui_test_out>`（默认 `test_ui.py`）
- 运行时会在 `tests/` 目录下创建/覆盖相应文件。

## 7. 常见问题排查
| 场景 | 可能原因 | 解决方案 |
|------|----------|----------|
| **Playwright 浏览器未安装** | `playwright install` 未执行 | 运行 `playwright install` 安装 Chromium/Firefox/WebKit |
| **测试未自动触发** | 自动开关关闭或未在聊天中明确请求 | 打开侧边栏的自动触发开关，或使用 **立即运行测试** 按钮 |
| **图片粘贴失效** | `streamlit-paste-button` 组件状态被清除 | 已通过 `st.session_state` 与动态 `key` 机制保持图片，确保在发送请求前未触发页面重新渲染 |
| **生成的 UI 测试逻辑错误** | AI 未遵守 “先操作后断言” 规则 | 已在 `ui_generator.py` 的系统提示中强化此规则；如仍有问题，可在需求描述中明确步骤顺序 |

## 8. 扩展与自定义
- **新增业务代码**：在 `src/` 目录添加模块，更新 `app.py` 中的 `target_file` 输入即可。
- **自定义测试模板**：修改 `agent/generator.py` 或 `agent/ui_generator.py` 中的 Prompt，加入公司内部测试规范。
- **CI 集成**：在 CI 脚本中直接调用 `python -m pytest` 与 `playwright test`，无需 UI。

---
*本文档由 AI 测试智能体自动生成，持续同步项目最新结构与功能。*
