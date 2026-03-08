"""
run_api.py

FastAPI 服务快捷启动脚本。

直接运行：
    python run_api.py

端口、Host 等配置通过 .env 文件中的以下字段控制：
    API_HOST     = 127.0.0.1
    API_PORT     = 8000
    API_RELOAD   = true
"""

import os
import uvicorn
from dotenv import load_dotenv

# 加载 .env 配置
load_dotenv()

if __name__ == "__main__":
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"

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
