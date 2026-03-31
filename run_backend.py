import os
import sys
import subprocess
try:
    import psutil
    import watchfiles
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "psutil", "watchfiles"], check=True)
    import psutil

def kill_port(port):
    for conn in psutil.net_connections():
        if conn.laddr.port == port and conn.pid:
            try:
                p = psutil.Process(conn.pid)
                print(f"[清理] 正在强制终止端口 {port} 的旧进程 PID: {conn.pid}")
                p.kill()
            except Exception as e:
                print(f"清理错误: {e}")

if __name__ == "__main__":
    kill_port(8000)
    print("\n==============================================")
    print("🚀 正在启动 AI 测试助手 (已隔离 tests/ 目录，防崩溃版)")
    print("==============================================\n")
    
    cmd = [
        sys.executable, "-m", "uvicorn", 
        "server:app", 
        "--host", "0.0.0.0", 
        "--port", "8000", 
        "--reload", 
        "--reload-exclude", "tests",
        "--reload-exclude", "\"tests/*\""
    ]
    subprocess.run(cmd)
