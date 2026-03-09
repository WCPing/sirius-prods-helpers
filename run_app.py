"""
run_app.py

前后台一键启动脚本（后端 API + 前台 Web 同时启动）。

直接运行：
    python run_app.py

端口、Host 等配置通过 .env 文件中的以下字段控制：
    API_HOST     = 127.0.0.1
    API_PORT     = 8000
    API_RELOAD   = true

注意：
  - 如果只需启动后端（例如配合 test_api.sh 做接口测试），请使用 run_api.py。
  - 前台开发服务器将在后台进程启动，默认运行在 http://localhost:5173。
"""

import os
import subprocess
import uvicorn
from dotenv import load_dotenv

# 加载 .env 配置
load_dotenv()


def start_frontend():
    """在后台启动前台开发服务器（cd frontend && npm run dev）。"""
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    print("🌐 启动前台开发服务器（npm run dev）...")
    print(f"   目录   : {frontend_dir}")
    print(f"   地址   : http://localhost:5173")
    print()
    # 在后台启动，不阻塞当前进程
    subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
    )


if __name__ == "__main__":
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"
    # 一键同时启动前台
    start_frontend()

    print(f"🚀 启动 PDM Assistant API 服务...")
    print(f"   Host   : {host}")
    print(f"   Port   : {port}")
    print(f"   Reload : {reload}")
    print(f"   Docs   : http://localhost:{port}/docs")
    print()

    uvicorn.run(
        "backend.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )
