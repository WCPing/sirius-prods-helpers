"""
backend/api/main.py

FastAPI 主应用入口。

启动命令：
    uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000

API 文档：
    Swagger UI : http://localhost:8000/docs
    ReDoc      : http://localhost:8000/redoc
"""

import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import pdm, conversation, knowledge
from backend.config import settings

# ---------------------------------------------------------------
# 统一日志配置（全局唯一入口，其他模块只需 logging.getLogger(__name__)）
# ---------------------------------------------------------------
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_formatter = logging.Formatter(LOG_FORMAT)
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)

# 控制台输出
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)
_root_logger.addHandler(_console_handler)

# 文件输出：启动时按时间戳生成日志文件，如 app_20260319_140000.log
_log_filename = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
_file_handler = logging.FileHandler(
    filename=os.path.join(LOG_DIR, _log_filename),
    encoding="utf-8",
)
_file_handler.setFormatter(_formatter)
_root_logger.addHandler(_file_handler)

# 对第三方库降噪，避免刷屏
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# 生命周期事件
# ---------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭钩子"""
    logger.info("=" * 60)
    logger.info("  知识中枢助手 API 服务已启动")
    logger.info(f"  LLM Provider : {settings.LLM_PROVIDER}")
    logger.info(f"  SQLite DB    : {settings.SQLITE_DB_PATH}")
    logger.info(f"  Chroma DB    : {settings.CHROMA_DB_PATH}")
    logger.info(f"  API Docs     : http://{settings.API_HOST}:{settings.API_PORT}/docs")
    logger.info("=" * 60)
    yield
    logger.info("知识中枢助手 API 服务已关闭")


# ---------------------------------------------------------------
# FastAPI 应用实例
# ---------------------------------------------------------------
app = FastAPI(
    title="知识中枢助手 API",
    description="""
## 知识中枢助手 - RESTful API

基于 LangChain + FastAPI 构建的统一知识中枢智能查询服务，支持 PDM 数据模型、代码仓库、配置文件的跨域智能问答与链路追踪。

### 功能模块

- **PDM 查询** (`/api/pdm/`): 列表、详情、语义搜索、关系查询、SQL 执行
- **会话管理** (`/api/conversations/`): 创建、查询、对话、删除会话
- **知识源管理** (`/api/knowledge-sources/`): 注册、同步、索引、统计知识源

### 快速开始

1. 确保已通过 `python scripts/index_code.py` 索引代码文件
2. 在 `.env` 中配置好 LLM API Key
3. 调用 `/api/knowledge-sources` 查看已注册的知识源
4. 调用 `/api/conversations` 创建会话并开始 AI 对话
""",
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------
# CORS 中间件（支持前端跨域访问）
# ---------------------------------------------------------------
origins = settings.CORS_ORIGINS
# 如果配置为 "*"，则允许所有来源
if origins == ["*"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ---------------------------------------------------------------
# 注册路由
# ---------------------------------------------------------------
API_PREFIX = "/api"

app.include_router(pdm.router, prefix=API_PREFIX)
app.include_router(conversation.router, prefix=API_PREFIX)
app.include_router(knowledge.router, prefix=API_PREFIX)


# ---------------------------------------------------------------
# 根路由 / 健康检查
# ---------------------------------------------------------------
@app.get("/", tags=["系统"], summary="服务状态")
def root():
    return {
        "name": "知识中枢助手 API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["系统"], summary="健康检查")
def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------
# 直接运行入口（开发环境）
# ---------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
    )
