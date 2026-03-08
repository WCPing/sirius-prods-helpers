"""
conversation_manager.py

多轮对话上下文管理模块。

功能：
- 维护多个会话（session），每个会话有独立的对话历史
- 支持将会话历史持久化到本地 JSON 文件，程序重启后可恢复
- 支持限制最大上下文消息数量，防止上下文窗口溢出
- 提供会话的创建、切换、清空、删除、列举等管理操作
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    messages_from_dict,
    messages_to_dict,
)

logger = logging.getLogger(__name__)


class ConversationSession:
    """表示一个独立的对话会话。"""

    def __init__(
        self,
        session_id: str,
        name: str = "",
        max_messages: int = 50,
    ):
        """
        Args:
            session_id: 会话唯一标识
            name: 会话的可读名称
            max_messages: 保留的最大消息数（超出后自动裁剪最早的消息）
        """
        self.session_id = session_id
        self.name = name or f"会话 {session_id[:8]}"
        self.max_messages = max_messages
        self.messages: List[BaseMessage] = []
        self.created_at: str = datetime.now().isoformat()
        self.updated_at: str = self.created_at

    def add_message(self, message: BaseMessage) -> None:
        """添加一条消息到历史记录，并在超出限制时自动裁剪。"""
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()

        # 超出最大消息数时，移除最早的非 SystemMessage 消息对
        if len(self.messages) > self.max_messages:
            non_system_indices = [
                i for i, m in enumerate(self.messages)
                if not isinstance(m, SystemMessage)
            ]
            if len(non_system_indices) >= 2:
                # 移除最早的一对消息
                self.messages.pop(non_system_indices[0])
                # 索引变了，重新找
                non_system_indices = [
                    i for i, m in enumerate(self.messages)
                    if not isinstance(m, SystemMessage)
                ]
                if non_system_indices:
                    self.messages.pop(non_system_indices[0])

        logger.debug(
            f"[Session {self.session_id[:8]}] 消息数: {len(self.messages)}"
        )

    def get_history(self) -> List[BaseMessage]:
        """返回完整的消息历史列表。"""
        return list(self.messages)

    def clear(self) -> None:
        """清空对话历史（保留 SystemMessage）。"""
        self.messages = [m for m in self.messages if isinstance(m, SystemMessage)]
        self.updated_at = datetime.now().isoformat()
        logger.info(f"[Session {self.session_id[:8]}] 对话历史已清空。")

    def message_count(self) -> int:
        """返回非 SystemMessage 的消息数量。"""
        return sum(1 for m in self.messages if not isinstance(m, SystemMessage))

    def to_dict(self) -> Dict[str, Any]:
        """序列化为可 JSON 存储的字典。"""
        return {
            "session_id": self.session_id,
            "name": self.name,
            "max_messages": self.max_messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": messages_to_dict(self.messages),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSession":
        """从字典反序列化恢复会话。"""
        session = cls(
            session_id=data["session_id"],
            name=data.get("name", ""),
            max_messages=data.get("max_messages", 50),
        )
        session.created_at = data.get("created_at", datetime.now().isoformat())
        session.updated_at = data.get("updated_at", session.created_at)
        try:
            session.messages = messages_from_dict(data.get("messages", []))
        except Exception as e:
            logger.warning(f"恢复会话消息失败，将使用空历史: {e}")
            session.messages = []
        return session

    def __repr__(self) -> str:
        return (
            f"ConversationSession(id={self.session_id[:8]}, "
            f"name='{self.name}', messages={self.message_count()})"
        )


class ConversationManager:
    """
    多会话上下文管理器。

    支持：
    - 创建 / 切换 / 删除 / 列举会话
    - 自动持久化（保存到 JSON 文件）
    - 控制每个会话的最大上下文长度
    """

    def __init__(
        self,
        persist_path: str = "./data/conversations.json",
        max_messages_per_session: int = 50,
    ):
        """
        Args:
            persist_path: 持久化文件路径。设为 None 则不持久化。
            max_messages_per_session: 每个会话默认保留的最大消息数。
        """
        self.persist_path = persist_path
        self.max_messages_per_session = max_messages_per_session
        self.sessions: Dict[str, ConversationSession] = {}
        self.current_session_id: Optional[str] = None

        # 从磁盘加载已有会话
        self._load()

        # 确保至少有一个默认会话
        if not self.sessions:
            self.new_session(name="默认会话")

    # ---------------------------------------------------------------
    # 会话管理
    # ---------------------------------------------------------------

    def new_session(self, name: str = "") -> ConversationSession:
        """创建一个新会话，并将其设为当前会话。"""
        session_id = str(uuid.uuid4())
        session = ConversationSession(
            session_id=session_id,
            name=name or f"会话 {len(self.sessions) + 1}",
            max_messages=self.max_messages_per_session,
        )
        self.sessions[session_id] = session
        self.current_session_id = session_id
        self._save()
        logger.info(f"新建会话: {session}")
        return session

    def switch_session(self, session_id: str) -> Optional[ConversationSession]:
        """切换当前会话。返回切换后的会话，失败返回 None。"""
        if session_id not in self.sessions:
            logger.warning(f"会话 {session_id} 不存在。")
            return None
        self.current_session_id = session_id
        logger.info(f"已切换至会话: {self.sessions[session_id]}")
        return self.sessions[session_id]

    def get_current_session(self) -> ConversationSession:
        """返回当前活跃会话，若不存在则自动创建。"""
        if self.current_session_id not in self.sessions:
            return self.new_session()
        return self.sessions[self.current_session_id]

    def delete_session(self, session_id: str) -> bool:
        """删除指定会话。若删除的是当前会话，自动切换到其他会话。"""
        if session_id not in self.sessions:
            return False
        del self.sessions[session_id]
        if self.current_session_id == session_id:
            # 切换到第一个可用会话，若无则创建新会话
            if self.sessions:
                self.current_session_id = next(iter(self.sessions))
            else:
                self.new_session(name="默认会话")
        self._save()
        logger.info(f"会话 {session_id[:8]} 已删除。")
        return True

    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话的摘要信息。"""
        result = []
        for sid, session in self.sessions.items():
            result.append({
                "session_id": sid,
                "name": session.name,
                "message_count": session.message_count(),
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "is_current": sid == self.current_session_id,
            })
        # 按更新时间降序排列
        result.sort(key=lambda x: x["updated_at"], reverse=True)
        return result

    # ---------------------------------------------------------------
    # 消息操作（操作当前会话）
    # ---------------------------------------------------------------

    def add_user_message(self, content: str) -> None:
        """向当前会话添加用户消息。"""
        self.get_current_session().add_message(HumanMessage(content=content))
        self._save()

    def add_ai_message(self, message: BaseMessage) -> None:
        """向当前会话添加 AI 回复消息（支持 AIMessage 对象）。"""
        self.get_current_session().add_message(message)
        self._save()

    def get_history(self) -> List[BaseMessage]:
        """返回当前会话的完整消息历史。"""
        return self.get_current_session().get_history()

    def clear_current_session(self) -> None:
        """清空当前会话的对话历史（保留 SystemMessage）。"""
        self.get_current_session().clear()
        self._save()

    # ---------------------------------------------------------------
    # 持久化
    # ---------------------------------------------------------------

    def _save(self) -> None:
        """将所有会话序列化保存到 JSON 文件。"""
        if not self.persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            data = {
                "current_session_id": self.current_session_id,
                "sessions": {
                    sid: session.to_dict()
                    for sid, session in self.sessions.items()
                },
            }
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存会话失败: {e}")

    def _load(self) -> None:
        """从 JSON 文件加载会话数据。"""
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for sid, sdata in data.get("sessions", {}).items():
                self.sessions[sid] = ConversationSession.from_dict(sdata)
            self.current_session_id = data.get("current_session_id")
            logger.info(
                f"已从 {self.persist_path} 加载 {len(self.sessions)} 个会话。"
            )
        except Exception as e:
            logger.error(f"加载会话失败，将使用空会话: {e}")
            self.sessions = {}
            self.current_session_id = None

    # ---------------------------------------------------------------
    # 格式化输出（用于 CLI 显示）
    # ---------------------------------------------------------------

    def format_sessions_table(self) -> str:
        """格式化所有会话为可读的表格字符串。"""
        sessions = self.list_sessions()
        if not sessions:
            return "  (暂无会话)"
        lines = []
        lines.append(f"  {'#':<4} {'状态':<6} {'名称':<20} {'消息数':<8} 会话ID")
        lines.append("  " + "-" * 70)
        for i, s in enumerate(sessions, 1):
            flag = "▶ " if s["is_current"] else "  "
            lines.append(
                f"  {flag}{i:<3} {'当前' if s['is_current'] else '':<6} "
                f"{s['name']:<20} {s['message_count']:<8} {s['session_id'][:8]}..."
            )
        return "\n".join(lines)

    def format_history(self, max_display: int = 0) -> str:
        """
        格式化当前会话的对话历史为可读字符串。

        Args:
            max_display: 最多显示最近几条消息（0 表示全部显示）
        """
        session = self.get_current_session()
        # 只显示 Human / AI 消息，跳过 SystemMessage
        history = [m for m in session.messages if not isinstance(m, SystemMessage)]

        if not history:
            return "  (当前会话暂无对话记录)"

        if max_display > 0:
            history = history[-max_display:]

        lines = []
        lines.append(
            f"  📜 会话历史 [{session.session_id[:8]}] {session.name}"
            f"  （共 {session.message_count()} 条，显示最近 {len(history)} 条）"
        )
        lines.append("  " + "─" * 70)

        for msg in history:
            if isinstance(msg, HumanMessage):
                role = "You"
                prefix = "  👤"
            elif isinstance(msg, AIMessage):
                role = "Assistant"
                prefix = "  🤖"
            else:
                role = type(msg).__name__
                prefix = "  ❓"

            content = str(msg.content)
            lines.append(f"{prefix} [{role}]")
            for line in content.splitlines():
                lines.append(f"     {line}")
            lines.append("")

        return "\n".join(lines)
