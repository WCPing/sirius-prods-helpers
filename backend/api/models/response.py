"""
backend/api/models/response.py

FastAPI 响应体 Pydantic 模型定义。
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict


# ---------------------------------------------------------------
# 通用响应模型
# ---------------------------------------------------------------

class BaseResponse(BaseModel):
    """通用响应基类"""
    success: bool = Field(default=True, description="请求是否成功")
    message: str = Field(default="OK", description="响应消息")


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = Field(default=False)
    message: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(default=None, description="详细错误信息")


# ---------------------------------------------------------------
# PDM 查询响应模型
# ---------------------------------------------------------------

class ColumnInfo(BaseModel):
    """字段信息"""
    name: str = Field(..., description="字段名称")
    code: str = Field(..., description="字段代码")
    data_type: str = Field(default="", description="数据类型")
    length: str = Field(default="", description="长度")
    mandatory: bool = Field(default=False, description="是否必填")
    comment: str = Field(default="", description="字段注释")


class TableInfo(BaseModel):
    """表信息（简要）"""
    code: str = Field(..., description="表代码")
    name: str = Field(..., description="表名称")
    comment: str = Field(default="", description="表注释")


class TableDetailInfo(TableInfo):
    """表信息（详细，包含字段列表）"""
    columns: List[ColumnInfo] = Field(default_factory=list, description="字段列表")


class ListTablesResponse(BaseResponse):
    """列出所有表的响应"""
    data: List[TableInfo] = Field(default_factory=list, description="表列表")
    total: int = Field(default=0, description="总数量")


class TableDetailResponse(BaseResponse):
    """获取表详情的响应"""
    data: Optional[TableDetailInfo] = Field(default=None, description="表详细信息")


class SearchResult(BaseModel):
    """单条搜索结果"""
    code: str = Field(..., description="表代码")
    name: str = Field(..., description="表名称")
    document: str = Field(..., description="索引文档内容")
    score: Optional[float] = Field(default=None, description="相关度得分")


class SearchTablesResponse(BaseResponse):
    """语义搜索结果响应"""
    data: List[SearchResult] = Field(default_factory=list, description="搜索结果列表")
    query: str = Field(..., description="搜索关键词")


class RelationshipInfo(BaseModel):
    """关系信息"""
    name: str = Field(..., description="关系名称")
    parent_table: str = Field(..., description="父表代码")
    child_table: str = Field(..., description="子表代码")
    direction: str = Field(..., description="方向：Parent 或 Child")


class RelationshipsResponse(BaseResponse):
    """查询关系的响应"""
    data: List[RelationshipInfo] = Field(default_factory=list, description="关系列表")
    table_code: str = Field(..., description="查询的表代码")


class ExecuteSQLResponse(BaseResponse):
    """执行 SQL 查询的响应"""
    data: Any = Field(default=None, description="查询结果（行列表或影响行数）")
    db_type: str = Field(..., description="执行的数据库类型")
    row_count: int = Field(default=0, description="返回行数")


# ---------------------------------------------------------------
# 索引管理响应模型
# ---------------------------------------------------------------

class IndexStatusResponse(BaseResponse):
    """索引状态响应"""
    indexed_files: List[str] = Field(default_factory=list, description="已索引的文件列表")
    total_tables: int = Field(default=0, description="已索引的表总数")
    total_columns: int = Field(default=0, description="已索引的字段总数")


class ReindexResponse(BaseResponse):
    """重建索引响应"""
    indexed_count: int = Field(default=0, description="本次索引的文件数量")


# ---------------------------------------------------------------
# 会话管理响应模型
# ---------------------------------------------------------------

class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str = Field(..., description="会话 ID")
    name: str = Field(..., description="会话名称")
    message_count: int = Field(default=0, description="消息数量")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="最后更新时间")
    is_current: bool = Field(default=False, description="是否为当前活跃会话")


class ListSessionsResponse(BaseResponse):
    """列出所有会话的响应"""
    data: List[SessionInfo] = Field(default_factory=list, description="会话列表")
    total: int = Field(default=0, description="会话总数")


class SessionDetailResponse(BaseResponse):
    """会话详情响应"""
    data: Optional[SessionInfo] = Field(default=None, description="会话信息")


class MessageItem(BaseModel):
    """单条消息"""
    role: str = Field(..., description="消息角色：user 或 assistant")
    content: str = Field(..., description="消息内容")


class SessionHistoryResponse(BaseResponse):
    """会话历史响应"""
    session_id: str = Field(..., description="会话 ID")
    session_name: str = Field(..., description="会话名称")
    messages: List[MessageItem] = Field(default_factory=list, description="消息历史")
    total: int = Field(default=0, description="消息总数")


class ChatResponse(BaseResponse):
    """AI 对话响应"""
    session_id: str = Field(..., description="会话 ID")
    reply: str = Field(..., description="AI 回复内容")
