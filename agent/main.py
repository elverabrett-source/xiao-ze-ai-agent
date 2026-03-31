import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
from generator import generate_test_code, fix_test_code, improve_coverage
from ui_generator import analyze_root_cause
from executor import run_tests_from_code

def main():
    parser = argparse.ArgumentParser(description="AI 自动化软件测试智能体")
    parser.add_argument(
        "--desc", 
        type=str, 
        help="被测函数/模块的功能描述（如果不用 --file）"
    )
    parser.add_argument(
        "--file", 
        type=str, 
        help="被测代码文件的路径，Agent 将读取该文件来生成测试"
    )
    parser.add_argument(
        "--out",
        type=str,
        default="test_generated.py",
        help="生成的测试文件名称"
    )
    parser.add_argument(
        "--req-file",
        type=str,
        default="",
        help="从长篇文档提取的需求内容文本文件路径"
    )
    parser.add_argument(
        "--image-file",
        type=str,
        default="",
        help="上传的流程截图路径"
    )
    
    args = parser.parse_args()
    
    feature_desc = ""
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                feature_desc = f"请为以下代码（文件路径推断为 {args.file}）编写测试：\n\n{f.read()}\n"
        except Exception as e:
            print(f"❌ 无法读取文件 {args.file}: {e}")
            return
    elif args.desc:
        feature_desc = args.desc
    elif args.req_file or args.image_file:
        feature_desc = "请根据我提供的补充需求信息（文档/图片），为对应的业务逻辑编写最严谨的自动化测试代码。"
    else:
        print("❌ 错误：必须提供 --desc（描述）、--file（源代码） 或上传附件其中之一！")
        return
        
    if args.req_file:
        try:
            with open(args.req_file, "r", encoding="utf-8", errors="ignore") as f:
                feature_desc += f"\n\n【补充的长篇需求文档说明】\n{f.read()}\n"
        except Exception as e:
            print(f"⚠️ 读取补充需求文档失败: {e}")
        
    print(f"🤖 Agent 启动！收到测试任务（长度 {len(feature_desc)} 字符）")
    
    # 【改动重点】：引入一个最大重试次数的常量
    MAX_RETRIES = 3
    
    # 第一次：生成初始代码
    code = generate_test_code(feature_desc, args.image_file)
    
    if not code:
        print("❌ Agent 运行中止：生成测试代码失败。")
        return
        
    print(f"✨ 成功生成初始测试代码，准备首次运行。")
    
    # === 阶段 1：自动修复循环 (Self-Correction Loop) ===
    is_all_green = False
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n================ [ 第 {attempt} 次尝试 ] ================")
        
        # 调用执行器，接收 3 个返回值
        is_success, output, coverage_percent = run_tests_from_code(code, args.out)
        
        if is_success:
            print(f"🎉 阶段一圆满完成：测试代码已经全部变绿！")
            is_all_green = True
            break
        else:
            if attempt < MAX_RETRIES:
                print("[REFLECTION] ⚠️ 执行发现报错！AI 正在挂载报错栈并进行反思重试 (Self-Correction)...")
                code = fix_test_code(code, output, feature_desc, args.image_file)
                if not code: return
                if code.startswith("BUG_DETECTED"):
                    print("\n[REFLECTION] 🚨🚨🚨 [警报] 发现业务代码缺陷！正在生成根因分析报告... 🚨🚨🚨")
                    # 读取最新源码作为上下文
                    source_content = ""
                    if args.file:
                        with open(args.file, "r", encoding="utf-8") as f:
                            source_content = f.read()
                    
                    rca_report = analyze_root_cause(feature_desc, code, output, source_content)
                    print(f"\n--- 🕵️‍♂️ 智能缺陷诊断报告 ---")
                    print(rca_report)
                    print(f"---------------------------\n")
                    print("🚨🚨🚨 Agent 已停止测试，请人类开发者参考上方建议修复业务代码！ 🚨🚨🚨\n")
                    return
            else:
                print(f"💥 连续尝试 {MAX_RETRIES} 次均失败，放弃修复。")
                return

    # === 阶段 2：覆盖率猎手循环 (Coverage Hunter Loop) ===
    if is_all_green:
        MAX_COV_RETRIES = 3
        for cov_attempt in range(1, MAX_COV_RETRIES + 1):
            if coverage_percent >= 100:
                print("\n🏆 【终极胜利】测试全绿且覆盖率达到 100%！Agent 下班了！")
                return
                
            print(f"\n================ [ 冲击覆盖率 第 {cov_attempt} 轮 ] ================")
            print(f"📉 当前覆盖率仅为 {coverage_percent}%，开始针对未覆盖行生成补充用例...")
            
            # 使用大模型专项提高覆盖率
            code = improve_coverage(code, output, feature_desc, args.image_file)
            if not code: return
            
            # 再次运行校验
            is_success, output, coverage_percent = run_tests_from_code(code, args.out)
            if not is_success:
                print("⚠️ 哎呀！本来全绿的，新生成的用例报错了！(为防止无限循环，终止覆盖率提升)")
                break
                
        print(f"✅ 最终定格覆盖率: {coverage_percent}% (尝试次数用尽或遇到冲突)")


if __name__ == "__main__":
    main()
