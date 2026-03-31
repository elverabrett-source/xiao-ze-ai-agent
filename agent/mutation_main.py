import argparse
import sys
import os
import pathlib

# 添加当前目录到 path
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from mutation_engine import MutationEngine
from executor import run_tests

def main():
    parser = argparse.ArgumentParser(description="AI Mutation Tester")
    parser.add_argument("--file", type=str, required=True, help="待测业务代码文件 (.py)")
    parser.add_argument("--test", type=str, required=True, help="对应的测试脚本 (.py)")
    args = parser.parse_args()

    target_file = args.file
    test_file = args.test

    if not os.path.exists(target_file):
        print(f"❌ 错误：找不到业务代码文件 {target_file}")
        return
    if not os.path.exists(test_file):
        print(f"❌ 错误：找不到测试文件 {test_file}")
        return

    print(f"🕵️‍♂️ AI 变异测试启动！")
    print(f"📦 目标代码: {target_file}")
    print(f"🧪 验证脚本: {test_file}")

    engine = MutationEngine(target_file)
    mutants = engine.generate_mutants()
    
    if not mutants:
        print("⚠️ 未发现可变异的逻辑点（如 ==, >, +, True 等）。")
        return

    print(f"🚀 发现 {len(mutants)} 个潜在变异点，开始侦测测试用例杀伤力...")
    
    results = []
    kills = 0
    
    # 备份原始文件
    backup_file = target_file + ".bak"
    if os.path.exists(backup_file):
        os.remove(backup_file)
    os.rename(target_file, backup_file)
    
    try:
        for i, (content, desc, line_no) in enumerate(mutants):
            # 写入变异代码
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 运行测试
            success, output = run_tests(test_file)
            
            # 如果测试失败 (success=False)，说明 Mutant 被杀死了 (测试有效)
            if not success:
                print(f"✅ Mutant #{i+1} 被查杀！({desc})")
                results.append({"id": i+1, "desc": desc, "status": "KILLED", "line": line_no})
                kills += 1
            else:
                print(f"❌ Mutant #{i+1} 存活！测试用例未能捕获该逻辑变异。({desc})")
                results.append({"id": i+1, "desc": desc, "status": "SURVIVED", "line": line_no})
                
    finally:
        # 恢复原始文件
        if os.path.exists(target_file):
            os.remove(target_file)
        os.rename(backup_file, target_file)
        
    score = (kills / len(mutants)) * 100
    print(f"\n📊 --- 变异测试总结 ---")
    print(f"杀伤率 (Mutation Score): {score:.1f}%")
    print(f"总变异体: {len(mutants)}")
    print(f"成功击杀: {kills}")
    print(f"存活数目: {len(mutants) - kills}")
    
    if score < 100:
        print(f"\n💡 建议：你的测试用例还不够强！有 {len(mutants) - kills} 个逻辑变异未能被捕获。")
    else:
        print(f"\n🏆 完美！你的测试用例具有极高的杀伤力，覆盖了所有关键逻辑变异。")

if __name__ == "__main__":
    main()
