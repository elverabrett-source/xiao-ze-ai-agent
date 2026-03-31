import re
import os

class MutationEngine:
    """
    1.3 核心组件：变异引擎
    用于对目标代码进行微小逻辑修改，生成“变异体”。
    """
    
    MUTATION_RULES = {
        r' == ': ' != ',
        r' != ': ' == ',
        r' > ': ' <= ',
        r' < ': ' >= ',
        r' >= ': ' < ',
        r' <= ': ' > ',
        r' \+ ': ' - ',
        r' - ': ' + ',
        r' \* ': ' / ',
        r' / ': ' * ',
        r'True': 'False',
        r'False': 'True',
        r' and ': ' or ',
        r' or ': ' and ',
    }

    def __init__(self, target_file):
        self.target_file = target_file
        with open(target_file, 'r', encoding='utf-8') as f:
            self.original_content = f.read()

    def generate_mutants(self):
        """
        生成所有可能的单点变异体。
        返回格式：[(mutant_content, description, line_no), ...]
        """
        mutants = []
        lines = self.original_content.split('\n')
        
        for i, line in enumerate(lines):
            # 跳过注释和空行
            if line.strip().startswith('#') or not line.strip():
                continue
                
            for pattern, replacement in self.MUTATION_RULES.items():
                if re.search(pattern, line):
                    # 执行替换
                    new_line = re.sub(pattern, replacement, line, count=1)
                    mutant_lines = lines.copy()
                    mutant_lines[i] = new_line
                    
                    description = f"将 {pattern.strip()} 替换为 {replacement.strip()} (第 {i+1} 行)"
                    mutants.append(('\n'.join(mutant_lines), description, i+1))
                    
        return mutants

def run_mutation_test(target_file, test_file):
    """
    辅助函数：执行变异测试流程
    """
    from executor import run_tests
    engine = MutationEngine(target_file)
    mutants = engine.generate_mutants()
    
    if not mutants:
        return "⚠️ 未发现可变异的逻辑点。"

    print(f"🚀 发现 {len(mutants)} 个潜在变异点，开始侦测杀伤力...")
    
    results = []
    kills = 0
    
    # 备份原始文件
    backup_file = target_file + ".bak"
    os.rename(target_file, backup_file)
    
    try:
        for content, desc, line in mutants:
            # 写入变异代码
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 运行测试
            success, output = run_tests(test_file)
            
            # 如果测试失败，说明 Mutant 被杀死了 (Good)
            if not success:
                results.append({"desc": desc, "status": "KILLED", "line": line})
                kills += 1
            else:
                results.append({"desc": desc, "status": "SURVIVED", "line": line})
                
    finally:
        # 恢复原始文件
        if os.path.exists(target_file):
            os.remove(target_file)
        os.rename(backup_file, target_file)
        
    score = (kills / len(mutants)) * 100
    return {
        "score": score,
        "total": len(mutants),
        "kills": kills,
        "details": results
    }
