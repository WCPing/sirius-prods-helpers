"""
backend/api/models/request.py

FastAPI 请求体 Pydantic 模型定义。
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ---------------------------------------------------------------
# PDM 查询请求模型
# ---------------------------------------------------------------

class SearchTablesRequest(BaseModel):
    """语义搜索表请求体"""
    query: str = Field(..., description="搜索关键词，例如：'用户信息'、'订单'", min_length=1)
    n_results: int = Field(default=5, description="返回结果数量", ge=1, le=20)

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "用户信息",
                "n_results": 5
            }
        }
    }


class ExecuteSQLRequest(BaseModel):
    """执行 SQL 查询请求体"""
    db_type: str = Field(..., description="数据库类型：'mysql' 或 'oracle'")
    sql: str = Field(..., description="要执行的 SQL 语句", min_length=1)

    model_config = {
        "json_schema_extra": {
            "example": {
                "db_type": "mysql",
                "sql": "SELECT * FROM users LIMIT 10"
            }
        }
    }


# ---------------------------------------------------------------
# 会话管理请求模型
# ---------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    """创建新会话请求体"""
    name: Optional[str] = Field(default="", description="会话名称（可选）")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "项目A分析"
            }
        }
    }


class ImageData(BaseModel):
    """上传图片数据"""
    data: str = Field(..., description="base64 编码的图片数据")
    filename: str = Field(default="", description="文件名")
    mime_type: str = Field(default="image/png", description="MIME 类型")


class SendMessageRequest(BaseModel):
    """向会话发送消息（AI 对话）请求体"""
    message: str = Field(default="", description="用户发送的消息内容")
    images: Optional[List[ImageData]] = Field(default=None, description="附件图片列表")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "查找与用户相关的所有表"
            }
        }
    }


# ---------------------------------------------------------------
# 知识源管理请求模型
# ---------------------------------------------------------------

class RegisterSourceRequest(BaseModel):
    """注册知识源请求体"""
    name: str = Field(..., description="知识源名称", min_length=1)
    source_type: str = Field(..., description="知识源类型：'pdm'、'git' 或 'local'")
    location: str = Field(..., description="知识源位置：Git URL 或本地路径", min_length=1)
    branch: str = Field(default="main", description="Git 分支（仅 git 类型有效）")
    include_patterns: str = Field(default="", description="文件匹配模式（逗号分隔）")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Sirius Backend",
                "source_type": "local",
                "location": "/path/to/project",
                "branch": "main",
                "include_patterns": ""
            }
        }
    }
