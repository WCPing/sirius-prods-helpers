"""
backend/config.py

统一配置管理模块，读取 .env 环境变量并提供全局配置对象。
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ---------------------------------------------------------------
    # API 服务配置
    # ---------------------------------------------------------------
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_RELOAD: bool = os.getenv("API_RELOAD", "true").lower() == "true"

    # CORS 跨域允许的源列表，多个用逗号分隔，默认允许所有
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")

    # ---------------------------------------------------------------
    # 数据库路径配置
    # ---------------------------------------------------------------
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "./data/metadata.db")
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
    PDM_FILES_DIR: str = os.getenv("PDM_FILES_DIR", "./files")

    # ---------------------------------------------------------------
    # 会话管理配置
    # ---------------------------------------------------------------
    CONVERSATION_PERSIST_PATH: str = os.getenv(
        "CONVERSATION_PERSIST_PATH", "./data/conversations.json"
    )
    MAX_MESSAGES_PER_SESSION: int = int(
        os.getenv("MAX_MESSAGES_PER_SESSION", "50")
    )

    # ---------------------------------------------------------------
    # LLM 配置
    # ---------------------------------------------------------------
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek").lower()
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    ANTHROPIC_AUTH_TOKEN: str = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
    ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-4.6-sonnet")

    # LLM 请求超时（秒），默认 120 秒
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "120"))

    # ---------------------------------------------------------------
    # 数据库连接配置
    # ---------------------------------------------------------------
    MYSQL_URL: str = os.getenv("MYSQL_URL", "")
    ORACLE_URL: str = os.getenv("ORACLE_URL", "")

    # ---------------------------------------------------------------
    # 知识源配置
    # ---------------------------------------------------------------
    REPOS_DIR: str = os.getenv("REPOS_DIR", "./data/repos")

    # ---------------------------------------------------------------
    # 嵌入模型配置
    # ---------------------------------------------------------------
    MODEL_NAME: str = os.getenv("MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2")

    # ---------------------------------------------------------------
    # 代码索引配置
    # ---------------------------------------------------------------
    CODE_CHUNK_MAX_LINES: int = int(os.getenv("CODE_CHUNK_MAX_LINES", "100"))
    CODE_INDEX_EXTENSIONS: list = os.getenv(
        "CODE_INDEX_EXTENSIONS",
        ".java,.js,.hbs,.xml,.yml,.yaml,.properties"
    ).split(",")
    CODE_EXCLUDE_DIRS: list = os.getenv(
        "CODE_EXCLUDE_DIRS",
        "target,build,dist,node_modules,.git,.svn,test,tests,__pycache__"
    ).split(",")


# 单例配置对象
settings = Settings()
