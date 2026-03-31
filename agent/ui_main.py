"""
agent/ui_main.py
UI 测试智能体主控程序

接收命令行参数：
  --url     目标网页 URL（必填）
  --req     测试需求文字描述
  --img     参考截图路径（可选）
  --out     输出文件名（可选，默认 test_ui.py）

工作流：
  1. 调用 ui_generator 生成 Playwright 测试代码
  2. 调用 ui_executor 运行测试
  3. 若失败，最多重试 MAX_RETRIES 次（每次让 LLM 修复）
"""

import sys
import os
# 确保无论从哪个目录调用都能找到 agent 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
from ui_generator import generate_ui_tests, fix_ui_tests, diagnose_ui_error
from ui_executor import run_ui_tests

MAX_RETRIES = 3

def main():
    parser = argparse.ArgumentParser(description="AI UI 自动化测试智能体 (Playwright)")
    parser.add_argument("--url",  type=str, required=True,  help="目标网页 URL（必填）")
    parser.add_argument("--req",  type=str, default="",     help="测试需求描述")
    parser.add_argument("--img",  type=str, default="",     help="参考截图路径（可选）")
    parser.add_argument("--out",  type=str, default="test_ui.py", help="输出测试文件名")
    args = parser.parse_args()

    print(f"🤖 UI Agent 启动！目标: {args.url}")
    print(f"📋 测试需求: {args.req or '（用户未填写，AI 将自动推断）'}")

    # 第一次生成
    code = generate_ui_tests(args.url, args.req or f"请测试 {args.url} 的主要功能", args.img)
    if not code:
        print("❌ 生成 UI 测试代码失败，Agent 中止。")
        return

    # 运行 + 自我修复循环
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n{'='*16} [ 第 {attempt} 次运行 UI 测试 ] {'='*16}")
        is_success, output, crash_img_path = run_ui_tests(code, args.out, target_url=args.url)

        if is_success:
            print(f"\n🏆 【胜利】所有 UI 测试全部通过！")
            return

        if attempt < MAX_RETRIES:
            print(f"\n[REFLECTION] 🧠 AI 发现报错！正在启动自省重试链 (Self-Correction)...")
            
            # 判断是否捕获到了视觉快照
            vlm_image = args.img
            if crash_img_path:
                print(f"[REFLECTION] 📸 提取到执行崩溃现场快照: {crash_img_path}，正在载入 VLM (视觉神经元)...")
                vlm_image = crash_img_path
            else:
                print(f"[REFLECTION] 🔍 正在深度读取 DOM 和报错栈，分析失败根因...")
                
            diagnosis = diagnose_ui_error(args.req, code, output, args.url, image_path=vlm_image)
            
            category = diagnosis.get("category", "LOCATOR_ISSUE")
            analysis = diagnosis.get("analysis", "未能提取有效分析内容")
            suggestion = diagnosis.get("suggestion", "重新尝试修复")

            print(f"[REFLECTION] 📊 诊断结论: 【{category}】")
            print(f"[REFLECTION] 🧐 错误分析: {analysis}")
            print(f"[REFLECTION] 💡 修复方案: {suggestion}")

            if category == "LOGIC_BUG":
                print(f"\n🚨 【触发吹哨】智能体判定这可能是一个真实的业务 Bug，正在生成根因分析报告...")
                # UI 测试通常没有单一源码文件，这里传入 URL 或特殊说明
                rca_report = analyze_root_cause(args.req, code, output, f"目标网页: {args.url}")
                print(f"\n--- 🕵️‍♂️ 智能缺陷诊断报告 ---")
                print(rca_report)
                print(f"---------------------------\n")
                print(f"为了防止掩盖缺陷，我将停止自动修复。请参考上方报告进行检查。")
                return

            print(f"[REFLECTION] 🔧 定位为非业务逻辑问题，正依据大模型建议重写测试脚本...")
            code = fix_ui_tests(code, output, args.url, image_path=vlm_image)
            if not code:
                print("❌ 修复失败，AI 返回空代码。")
                return
        else:
            print(f"\n💥 连续尝试 {MAX_RETRIES} 次均失败，放弃。请检查网页是否可访问，或更细化你的需求描述。")

if __name__ == "__main__":
    main()
