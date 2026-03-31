import os
import sys
import subprocess
import time
import pathlib

def install_dependencies():
    """全自动补全缺失的依赖"""
    required_packages = [
        "psutil", "fastapi", "uvicorn", "pydantic", 
        "python-docx", "PyPDF2", "openai", "python-multipart"
    ]
    print("[*] Verifying Python library integrity...")
    for pkg in required_packages:
        try:
            check_name = "docx" if pkg == "python-docx" else pkg
            check_name = "multipart" if pkg == "python-multipart" else check_name
            __import__(check_name.replace("-", "_"))
        except ImportError:
            print(f"[+] Missing {pkg}, installing now...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"])

def clean_port(port):
    """暴力清理端口"""
    try:
        import psutil
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.pid:
                try:
                    p = psutil.Process(conn.pid)
                    print(f"[+] Force killing Port {port} (PID: {conn.pid})...")
                    p.kill()
                except:
                    pass
    except:
        pass

def start_services():
    base_dir = pathlib.Path(__file__).resolve().parent
    
    print("\n" + "="*50)
    print("🚀 XIAO ZE - OMNIPOTENT AUTO-LAUNCHER")
    print("="*50 + "\n")
    
    # 1. 环境预检
    install_dependencies()
    
    # 2. 端口重置
    clean_port(8000)
    clean_port(3000)
    
    # 3. 启动后端
    print("[*] Starting Backend (8000)...")
    # 关键修复点：将 tests/* 放在单引号或双引号内，防止 Windows Shell 非法展开
    backend_cmd = f'cmd /k "chcp 65001 && {sys.executable} -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload --reload-exclude \"tests/*\""'
    CREATE_NEW_CONSOLE = 0x00000010
    subprocess.Popen(backend_cmd, creationflags=CREATE_NEW_CONSOLE, cwd=str(base_dir))
    
    time.sleep(2)
    
    # 4. 启动前端
    print("[*] Starting Frontend (3000)...")
    frontend_dir = base_dir / "frontend"
    if frontend_dir.exists():
        if not (frontend_dir / "node_modules").exists():
            print("[!] node_modules missing, running npm install...")
            frontend_cmd = 'cmd /k "chcp 65001 && npm install && npm run dev"'
        else:
            frontend_cmd = 'cmd /k "chcp 65001 && npm run dev"'
        subprocess.Popen(frontend_cmd, creationflags=CREATE_NEW_CONSOLE, cwd=str(frontend_dir))
    
    print("\n" + "="*50)
    print("✅ STARTUP COMPLETE")
    print("👉 UI: http://localhost:3000")
    print("👉 Backend: Port 8000 (Check the new window for logs)")
    print("="*50 + "\n")

if __name__ == "__main__":
    start_services()
