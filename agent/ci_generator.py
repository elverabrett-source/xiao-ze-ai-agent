"""
agent/ci_generator.py
CI/CD 配置文件生成器

支持：
  - GitHub Actions (.github/workflows/ai-test.yml)
  - GitLab CI (.gitlab-ci.yml)
"""

import pathlib

# ============ GitHub Actions 模板 ============

GITHUB_ACTIONS_TEMPLATE = """name: AI 智能体自动化测试

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10']

    steps:
      - name: 检出代码
        uses: actions/checkout@v4

      - name: 配置 Python ${{{{ matrix.python-version }}}}
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ matrix.python-version }}}}

      - name: 安装核心依赖
        run: |
          python -m pip install --upgrade pip
          pip install pytest pytest-cov requests
{extra_install}
      - name: 运行测试
        run: |
{test_commands}
"""

# ============ GitLab CI 模板 ============

GITLAB_CI_TEMPLATE = """stages:
  - test

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"

cache:
  paths:
    - .cache/pip/

test:
  stage: test
  image: python:3.10-slim
  before_script:
    - python -m pip install --upgrade pip
    - pip install pytest pytest-cov requests
{extra_install}
  script:
{test_commands}
"""


def generate_ci_config(platform: str, test_types: list) -> str:
    """
    根据平台和测试类型生成 CI 配置文件内容

    Args:
        platform: 'github' 或 'gitlab'
        test_types: 包含 'unit', 'ui', 'api', 'visual' 的列表
    """
    extra_install_lines = []
    test_command_lines = []

    # 单元测试
    if "unit" in test_types:
        test_command_lines.append("pytest tests/ -v --cov=src --cov-report=term-missing")

    # API 接口测试
    if "api" in test_types:
        test_command_lines.append("pytest tests/test_api_*.py -v")

    # UI 测试 (Playwright)
    if "ui" in test_types or "visual" in test_types:
        extra_install_lines.append("pip install playwright")
        extra_install_lines.append("python -m playwright install --with-deps chromium")

    if "ui" in test_types:
        test_command_lines.append("pytest tests/test_ui*.py -v --headed=false")

    # 视觉回归测试
    if "visual" in test_types:
        extra_install_lines.append("pip install Pillow")
        test_command_lines.append("python -c \"from agent.visual_engine import run_visual_regression; print('Visual engine OK')\"")

    # 如果用户没有显式选择，则默认运行全部
    if not test_command_lines:
        test_command_lines.append("pytest tests/ -v")

    # 格式化
    if platform == "github":
        extra_install = ""
        if extra_install_lines:
            extra_install = "\n".join([f"          {line}" for line in extra_install_lines]) + "\n"

        test_commands = "\n".join([f"          {line}" for line in test_command_lines])

        return GITHUB_ACTIONS_TEMPLATE.format(
            extra_install=extra_install,
            test_commands=test_commands
        )

    elif platform == "gitlab":
        extra_install = ""
        if extra_install_lines:
            extra_install = "\n".join([f"    - {line}" for line in extra_install_lines]) + "\n"

        test_commands = "\n".join([f"    - {line}" for line in test_command_lines])

        return GITLAB_CI_TEMPLATE.format(
            extra_install=extra_install,
            test_commands=test_commands
        )

    return "# 暂不支持该平台"


def save_ci_config(platform: str, content: str, project_root: str = ".") -> str:
    """将生成的配置保存到项目对应路径"""
    root = pathlib.Path(project_root)

    if platform == "github":
        target = root / ".github" / "workflows" / "ai-test.yml"
        target.parent.mkdir(parents=True, exist_ok=True)
    elif platform == "gitlab":
        target = root / ".gitlab-ci.yml"
    else:
        return "不支持的平台"

    with open(target, "w", encoding="utf-8") as f:
        f.write(content)

    return str(target)
