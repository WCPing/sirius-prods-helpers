"""
backend/api/routes/conversation.py

会话管理及 AI 对话相关 API 路由。

接口列表：
  GET    /api/conversations                          - 列出所有会话
  POST   /api/conversations                          - 创建新会话
  GET    /api/conversations/{session_id}             - 获取会话详情
  GET    /api/conversations/{session_id}/history     - 获取会话消息历史
  POST   /api/conversations/{session_id}/messages    - 发送消息（AI 对话）
  DELETE /api/conversations/{session_id}/history     - 清空会话历史
  DELETE /api/conversations/{session_id}             - 删除会话
"""

import os
import logging
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from backend.api.models.request import CreateSessionRequest, SendMessageRequest
from backend.api.models.response import (
    ListSessionsResponse,
    SessionDetailResponse,
    SessionInfo,
    SessionHistoryResponse,
    MessageItem,
    ChatResponse,
    BaseResponse,
)
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["会话管理"])

# ---------------------------------------------------------------
# 懒加载：Agent 和 ConversationManager（避免启动时就加载重型模型）
# ---------------------------------------------------------------

_agent_executor = None
_conv_manager = None


def _get_conv_manager():
    """获取或初始化会话管理器（单例）"""
    global _conv_manager
    if _conv_manager is None:
        from backend.core.conversation_manager import ConversationManager
        _conv_manager = ConversationManager(
            persist_path=settings.CONVERSATION_PERSIST_PATH,
            max_messages_per_session=settings.MAX_MESSAGES_PER_SESSION,
        )
    return _conv_manager


def _get_agent():
    """获取或初始化 Agent（单例，首次调用时初始化）"""
    global _agent_executor
    if _agent_executor is None:
        from langchain_deepseek import ChatDeepSeek
        from langchain_anthropic import ChatAnthropic
        from langchain.agents import create_agent
        from langchain_core.messages import SystemMessage
        from backend.core.tools import (
            ListTablesTool,
            TableSchemaTool,
            SearchTablesTool,
            RelationshipTool,
            ExecuteSQLTool,
        )

        provider = settings.LLM_PROVIDER

        if provider == "claude":
            if not settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError("ANTHROPIC_AUTH_TOKEN 未在 .env 中配置")
            llm = ChatAnthropic(
                model=settings.CLAUDE_MODEL,
                anthropic_api_key=settings.ANTHROPIC_AUTH_TOKEN,
                anthropic_api_url=settings.ANTHROPIC_BASE_URL or None,
                temperature=0.1,
                max_tokens=2000,
            )
        else:
            llm = ChatDeepSeek(
                model="deepseek-chat",
                temperature=0.1,
                max_tokens=2000,
                timeout=None,
                max_retries=2,
            )

        tools = [
            ListTablesTool(),
            TableSchemaTool(),
            SearchTablesTool(),
            RelationshipTool(),
            ExecuteSQLTool(),
        ]

        system_message = SystemMessage(
            content="""You are a PDM expert assistant and Database Analyst. 
    Help users understand table structure, relationships, and query actual data from MySQL or Oracle databases.
    
    1. For conceptual searches, use 'search_tables'.
    2. For table details, use 'get_table_schema' with the table's CODE.
    3. For connections, use 'find_relationships'.
    4. To query actual data from MySQL or Oracle, use 'execute_sql'. 
       Before running SQL, always verify the table structure and database type.
       Try to limit results (e.g., LIMIT 5 or FETCH FIRST 5 ROWS ONLY) to avoid overwhelming the output.
    5. Respond in the user's language (Chinese/English)."""
        )

        _agent_executor = create_agent(llm, tools, system_prompt=system_message)
    return _agent_executor


def _session_to_info(session_id: str, conv_manager, is_current: bool) -> SessionInfo:
    """将 ConversationSession 转换为 SessionInfo"""
    session = conv_manager.sessions.get(session_id)
    if not session:
        return None
    return SessionInfo(
        session_id=session.session_id,
        name=session.name,
        message_count=session.message_count(),
        created_at=session.created_at,
        updated_at=session.updated_at,
        is_current=is_current,
    )


# ---------------------------------------------------------------
# 列出所有会话
# ---------------------------------------------------------------

@router.get(
    "",
    response_model=ListSessionsResponse,
    summary="列出所有会话",
    description="返回所有对话会话的列表，按最后更新时间降序排列。",
)
def list_sessions():
    try:
        conv_manager = _get_conv_manager()
        sessions_data = conv_manager.list_sessions()
        sessions = [SessionInfo(**s) for s in sessions_data]
        return ListSessionsResponse(
            success=True,
            message="获取成功",
            data=sessions,
            total=len(sessions),
        )
    except Exception as e:
        logger.error(f"list_sessions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 创建新会话
# ---------------------------------------------------------------

@router.post(
    "",
    response_model=SessionDetailResponse,
    summary="创建新会话",
    description="创建一个新的对话会话，并将其设置为当前活跃会话。",
)
def create_session(body: CreateSessionRequest):
    try:
        conv_manager = _get_conv_manager()
        session = conv_manager.new_session(name=body.name or "")
        info = SessionInfo(
            session_id=session.session_id,
            name=session.name,
            message_count=session.message_count(),
            created_at=session.created_at,
            updated_at=session.updated_at,
            is_current=True,
        )
        return SessionDetailResponse(success=True, message="会话已创建", data=info)
    except Exception as e:
        logger.error(f"create_session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 获取会话详情
# ---------------------------------------------------------------

@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="获取会话详情",
    description="根据会话 ID 获取会话的基本信息。",
)
def get_session(session_id: str):
    try:
        conv_manager = _get_conv_manager()
        session = conv_manager.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")

        info = SessionInfo(
            session_id=session.session_id,
            name=session.name,
            message_count=session.message_count(),
            created_at=session.created_at,
            updated_at=session.updated_at,
            is_current=session_id == conv_manager.current_session_id,
        )
        return SessionDetailResponse(success=True, message="获取成功", data=info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 获取会话消息历史
# ---------------------------------------------------------------

@router.get(
    "/{session_id}/history",
    response_model=SessionHistoryResponse,
    summary="获取会话消息历史",
    description="返回指定会话的完整对话历史（不含 SystemMessage）。",
)
def get_session_history(session_id: str):
    try:
        conv_manager = _get_conv_manager()
        session = conv_manager.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")

        messages = []
        for msg in session.messages:
            if isinstance(msg, HumanMessage):
                messages.append(MessageItem(role="user", content=str(msg.content)))
            elif isinstance(msg, AIMessage):
                messages.append(MessageItem(role="assistant", content=str(msg.content)))
            # 跳过 SystemMessage

        return SessionHistoryResponse(
            success=True,
            message="获取成功",
            session_id=session.session_id,
            session_name=session.name,
            messages=messages,
            total=len(messages),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_session_history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 发送消息（AI 对话）
# ---------------------------------------------------------------

@router.post(
    "/{session_id}/messages",
    response_model=ChatResponse,
    summary="发送消息（AI 对话）",
    description="向指定会话发送一条消息，由 AI Agent 处理并返回回复。此接口会将消息追加到会话历史中。",
)
def send_message(session_id: str, body: SendMessageRequest):
    try:
        conv_manager = _get_conv_manager()
        session = conv_manager.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")

        # 切换到目标会话
        conv_manager.switch_session(session_id)

        # 获取历史 + 当前消息
        history = conv_manager.get_history()
        current_msg = HumanMessage(content=body.message)
        messages_to_send = history + [current_msg]

        # 调用 Agent
        agent = _get_agent()
        response = agent.invoke({"messages": messages_to_send})

        ai_msg = response["messages"][-1]
        assistant_content = str(ai_msg.content)

        # 保存本轮消息到会话历史
        conv_manager.add_user_message(body.message)
        conv_manager.add_ai_message(AIMessage(content=assistant_content))

        return ChatResponse(
            success=True,
            message="对话成功",
            session_id=session_id,
            reply=assistant_content,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"send_message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 清空会话历史
# ---------------------------------------------------------------

@router.delete(
    "/{session_id}/history",
    response_model=BaseResponse,
    summary="清空会话历史",
    description="清空指定会话的所有对话历史记录（保留会话本身）。",
)
def clear_session_history(session_id: str):
    try:
        conv_manager = _get_conv_manager()
        session = conv_manager.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")

        session.clear()
        conv_manager._save()

        return BaseResponse(success=True, message=f"会话 '{session.name}' 的历史已清空")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"clear_session_history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 删除会话
# ---------------------------------------------------------------

@router.delete(
    "/{session_id}",
    response_model=BaseResponse,
    summary="删除会话",
    description="删除指定会话及其所有历史记录。若删除当前活跃会话，将自动切换到其他会话。",
)
def delete_session(session_id: str):
    try:
        conv_manager = _get_conv_manager()
        if session_id not in conv_manager.sessions:
            raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")

        session_name = conv_manager.sessions[session_id].name
        success = conv_manager.delete_session(session_id)

        if not success:
            raise HTTPException(status_code=500, detail="删除会话失败")

        return BaseResponse(success=True, message=f"会话 '{session_name}' 已删除")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
