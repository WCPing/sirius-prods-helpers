"""
backend/api/routes/conversation.py

会话管理及 AI 对话相关 API 路由。

接口列表：
  GET    /api/conversations                                  - 列出所有会话
  POST   /api/conversations                                  - 创建新会话
  GET    /api/conversations/{session_id}                     - 获取会话详情
  GET    /api/conversations/{session_id}/history             - 获取会话消息历史
  POST   /api/conversations/{session_id}/messages            - 发送消息（AI 对话）
  POST   /api/conversations/{session_id}/messages/stream     - 发送消息（SSE 流式）
  DELETE /api/conversations/{session_id}/history             - 清空会话历史
  DELETE /api/conversations/{session_id}                     - 删除会话
"""

import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from backend.api.models.request import CreateSessionRequest, SendMessageRequest, RenameSessionRequest
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
_summary_llm = None


DEFAULT_SESSION_NAME = "新的聊天"


def _get_summary_llm():
    """获取或初始化用于生成会话标题的轻量 LLM（单例，无工具）"""
    global _summary_llm
    if _summary_llm is None:
        from langchain_deepseek import ChatDeepSeek
        from langchain_anthropic import ChatAnthropic

        provider = settings.LLM_PROVIDER
        if provider == "claude":
            if not settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError("ANTHROPIC_AUTH_TOKEN 未在 .env 中配置")
            _summary_llm = ChatAnthropic(
                model=settings.CLAUDE_MODEL,
                anthropic_api_key=settings.ANTHROPIC_AUTH_TOKEN,
                anthropic_api_url=settings.ANTHROPIC_BASE_URL or None,
                max_tokens=64,
                timeout=30,
            )
        else:
            _summary_llm = ChatDeepSeek(
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=64,
                timeout=settings.LLM_TIMEOUT,
                max_retries=2,
            )
    return _summary_llm


def _generate_session_title(user_msg: str, ai_reply: str) -> str | None:
    """根据首轮对话生成简短的中文会话标题，失败返回 None。"""
    try:
        from langchain_core.messages import SystemMessage, HumanMessage

        # 截断过长内容以控制 token
        user_snippet = (user_msg or "").strip()[:500]
        ai_snippet = (ai_reply or "").strip()[:500]

        llm = _get_summary_llm()
        resp = llm.invoke([
            SystemMessage(
                content=(
                    "请根据用户问题和AI回复，生成一个极简的中文会话标题，"
                    "长度严格控制在 10 个汉字以内（不超过 10 字），"
                    "只输出标题文本，不要加引号、标点或额外说明。"
                )
            ),
            HumanMessage(
                content=f"【用户问题】\n{user_snippet}\n\n【AI回复】\n{ai_snippet}"
            ),
        ])

        raw = resp.content if hasattr(resp, "content") else str(resp)
        if isinstance(raw, list):
            text = ""
            for block in raw:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
                elif isinstance(block, str):
                    text += block
        else:
            text = str(raw)

        # 清洗：去除空白/引号/换行
        title = text.strip().strip('"').strip("'").strip("「").strip("」").strip("《").strip("》")
        title = title.splitlines()[0] if title else ""
        title = title.strip()
        if not title:
            return None
        # 限长 10 字
        if len(title) > 10:
            title = title[:10]
        return title
    except Exception as e:
        logger.warning(f"_generate_session_title 失败: {e}")
        return None


def _build_message_with_attachments(body) -> str:
    """
    处理请求体中的附件内容，将图片 OCR 和日志文本统一拼接到消息中。
    返回最终要发送给 LLM 的纯文本消息。
    """
    message = body.message or ""
    parts = [message] if message else []

    if body.images:
        from backend.core.ocr_service import process_images

        images_data = [img.model_dump() for img in body.images]
        ocr_text = process_images(images_data)
        if ocr_text:
            parts.append(f"---\n[附件图片OCR识别结果]\n{ocr_text}")

    if body.log_file:
        from backend.core.log_file_service import process_log_file

        log_file_data = body.log_file.model_dump()
        log_text = process_log_file(log_file_data)
        if log_text:
            filename = body.log_file.filename or "log.txt"
            parts.append(f"---\n[附件日志: {filename}]\n```\n{log_text}\n```")

    if not parts and (body.images or body.log_file):
        parts.append("请分析以下附件内容")

    elif (body.images or body.log_file) and not message:
        parts.insert(0, "请分析以下附件内容")

    return "\n\n".join(parts)


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
        from backend.core.code_tools import (
            SearchCodeTool,
            GetCodeStructureTool,
            GetClassDetailTool,
            SearchAPIEndpointsTool,
            GrepCodeTool,
        )
        from backend.core.trace_tools import (
            TraceComponentTool,
            FindConfigUsageTool,
            FindTableUsageTool,
        )
        from backend.core.config_tools import (
            ConfigLookupTool,
            ListConfigsTool,
        )

        provider = settings.LLM_PROVIDER

        if provider == "claude":
            if not settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError("ANTHROPIC_AUTH_TOKEN 未在 .env 中配置")
            llm = ChatAnthropic(
                model=settings.CLAUDE_MODEL,
                anthropic_api_key=settings.ANTHROPIC_AUTH_TOKEN,
                anthropic_api_url=settings.ANTHROPIC_BASE_URL or None,
                max_tokens=2000,
                timeout=settings.LLM_TIMEOUT,
            )
        else:
            llm = ChatDeepSeek(
                model="deepseek-chat",
                temperature=0.1,
                max_tokens=2000,
                timeout=settings.LLM_TIMEOUT,
                max_retries=2,
            )

        tools = [
            # 现有 PDM / 数据库工具（保留）
            ListTablesTool(),
            TableSchemaTool(),
            SearchTablesTool(),
            RelationshipTool(),
            ExecuteSQLTool(),
            # 代码工具
            SearchCodeTool(),
            GetCodeStructureTool(),
            GetClassDetailTool(),
            SearchAPIEndpointsTool(),
            GrepCodeTool(),
            # 链路追踪工具
            TraceComponentTool(),
            FindConfigUsageTool(),
            FindTableUsageTool(),
            # 配置工具
            ConfigLookupTool(),
            ListConfigsTool(),
        ]

        system_message = SystemMessage(
            content="""你是一个统一知识中枢助手，能够跨 PDM 数据模型、代码仓库、配置文件和数据库进行智能问答与链路追踪。

你拥有以下四大类工具：

## 1. PDM / 数据库工具
- `list_tables`: 列出 PDM 文档中的所有表
- `get_table_schema`: 获取指定表的详细 schema（列、类型、注释）
- `search_tables`: 语义搜索相关表
- `find_relationships`: 查找表的外键关系
- `execute_sql`: 在 MySQL 或 Oracle 上执行 SQL 查询

## 2. 代码工具
- `search_code`: 语义搜索代码片段（类、方法、模板等），支持中文查询
- `get_code_structure`: 获取文件的代码结构（类/方法/字段列表）
- `get_class_detail`: 获取指定类的详细信息（注解、方法、字段）
- `search_api_endpoints`: 搜索 Spring REST API 端点
- `grep_code`: 精确关键词搜索（CSS class、icon 名、变量名、字符串等）

## 3. 链路追踪工具
- `trace_component`: 追踪组件的完整调用链（Config → Controller → Service → Mapper → Table）
- `find_config_usage`: 查找引用指定配置键的所有代码
- `find_table_usage`: 查找引用指定数据库表的所有代码

## 4. 配置工具
- `config_lookup`: 配置项查找（先精确匹配 key，再语义搜索）
- `list_configs`: 配置文件概览（按文件分组展示配置数量）

## 工作原则
1. 根据用户问题类型选择合适的工具组合
2. 对于代码问题，优先使用语义搜索定位相关代码，再深入查看详情
3. 对于精确搜索（icon 名、CSS class、变量名等），使用 `grep_code`
4. 对于配置问题（数据库连接、端口号等），使用 `config_lookup`
5. 对于跨层追踪（如"某个表被哪些代码使用"），使用链路追踪工具
6. 执行 SQL 前，先确认表结构和数据库类型
7. 限制查询结果数量（如 LIMIT 5）避免输出过多
8. 使用用户的语言（中文/英文）回复"""
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
# 重命名会话
# ---------------------------------------------------------------

@router.patch(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="重命名会话",
    description="修改指定会话的名称。",
)
def rename_session(session_id: str, body: RenameSessionRequest):
    try:
        conv_manager = _get_conv_manager()
        session = conv_manager.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")

        new_name = body.name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="会话名称不能为空")

        ok = conv_manager.rename_session(session_id, new_name)
        if not ok:
            raise HTTPException(status_code=500, detail="重命名失败")

        info = SessionInfo(
            session_id=session.session_id,
            name=session.name,
            message_count=session.message_count(),
            created_at=session.created_at,
            updated_at=session.updated_at,
            is_current=session_id == conv_manager.current_session_id,
        )
        return SessionDetailResponse(success=True, message="会话已重命名", data=info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"rename_session error: {e}")
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
            ts = None
            if getattr(msg, "additional_kwargs", None):
                ts = msg.additional_kwargs.get("timestamp")
            if isinstance(msg, HumanMessage):
                messages.append(MessageItem(role="user", content=str(msg.content), timestamp=ts))
            elif isinstance(msg, AIMessage):
                messages.append(MessageItem(role="assistant", content=str(msg.content), timestamp=ts))
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

        # 处理附件内容（图片 OCR / 日志文本）
        final_message = _build_message_with_attachments(body)
        if not final_message.strip():
            raise HTTPException(status_code=400, detail="消息内容不能为空")

        # 先保存用户消息（防止 Agent 超时/失败后消息丢失）
        conv_manager.add_user_message(final_message)

        # 获取历史（已包含刚保存的用户消息）
        messages_to_send = conv_manager.get_history()

        # 调用 Agent
        try:
            agent = _get_agent()
            response = agent.invoke({"messages": messages_to_send})
        except Exception as e:
            logger.error(f"Agent 调用失败: {e}")
            raise HTTPException(
                status_code=504,
                detail=f"AI 响应超时或调用失败，您的消息已保存，请稍后重试。错误: {e}",
            )

        ai_msg = response["messages"][-1]

        # Claude 启用思考模式或工具调用时，content 可能是 blocks 列表
        # 需要提取其中的 text 块作为最终回复（丢弃 thinking 块）
        raw_content = ai_msg.content
        if isinstance(raw_content, str):
            assistant_content = raw_content
        elif isinstance(raw_content, list):
            text_parts = []
            for block in raw_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            assistant_content = "".join(text_parts)
        else:
            assistant_content = str(raw_content)

        # 保存 AI 回复
        conv_manager.add_ai_message(AIMessage(content=assistant_content))

        # 若会话名仍为默认值，且为首轮回复（消息数==2），则自动总结标题
        if session.message_count() == 2 and session.name == DEFAULT_SESSION_NAME:
            new_title = _generate_session_title(final_message, assistant_content)
            if new_title:
                conv_manager.rename_session(session_id, new_title)

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
# 发送消息（SSE 流式响应）
# ---------------------------------------------------------------

@router.post(
    "/{session_id}/messages/stream",
    summary="发送消息（SSE 流式）",
    description="向指定会话发送一条消息，AI Agent 以 SSE 流式逐 token 返回回复。",
)
async def send_message_stream(session_id: str, body: SendMessageRequest):
    conv_manager = _get_conv_manager()
    session = conv_manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")

    # 切换到目标会话
    conv_manager.switch_session(session_id)

    # 处理附件内容（图片 OCR / 日志文本）
    final_message = _build_message_with_attachments(body)
    if not final_message.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    # 保存用户消息
    conv_manager.add_user_message(final_message)

    # 获取历史（已包含刚保存的用户消息）
    messages_to_send = conv_manager.get_history()

    async def event_generator():
        full_content = ""
        try:
            agent = _get_agent()
            logger.info(f"[Stream] 开始流式调用 session={session_id}")
            async for event, metadata in agent.astream(
                {"messages": messages_to_send},
                stream_mode="messages",
            ):
                # 只输出 AIMessage 的文本 content（跳过 tool_call、HumanMessage、ToolMessage 等）
                if not isinstance(event, AIMessage):
                    continue
                if event.tool_calls:
                    continue

                # 提取文本 token
                # content 可能是 str（无工具场景）或 list（有工具场景，Anthropic 返回 content blocks）
                token = ""
                if isinstance(event.content, str):
                    token = event.content
                elif isinstance(event.content, list):
                    for block in event.content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            token += block.get("text", "")
                        elif isinstance(block, str):
                            token += block

                if token:
                    full_content += token
                    yield f"data: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"
            logger.info(f"[Stream] 流式完成 session={session_id}, length={len(full_content)}")
        except Exception as e:
            logger.error(f"[Stream] error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            # 保存完整 AI 回复
            if full_content:
                conv_manager.add_ai_message(AIMessage(content=full_content))
                # 若会话名仍为默认值，且为首轮回复（消息数==2），则自动总结标题
                try:
                    cur = conv_manager.sessions.get(session_id)
                    if cur and cur.message_count() == 2 and cur.name == DEFAULT_SESSION_NAME:
                        new_title = _generate_session_title(final_message, full_content)
                        if new_title:
                            conv_manager.rename_session(session_id, new_title)
                except Exception as e:
                    logger.warning(f"[Stream] 自动总结标题失败: {e}")
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
