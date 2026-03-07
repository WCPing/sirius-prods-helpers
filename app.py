import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from tools import ListTablesTool, TableSchemaTool, SearchTablesTool, RelationshipTool, ExecuteSQLTool
from conversation_manager import ConversationManager

# Load environment variables
load_dotenv()

# ---------------------------------------------------------------
# 帮助信息
# ---------------------------------------------------------------
HELP_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║               PDM Assistant - 可用命令                       ║
╠══════════════════════════════════════════════════════════════╣
║  /new [名称]        创建新会话（可选指定名称）               ║
║  /sessions          列出所有会话                             ║
║  /switch <会话ID>   切换到指定会话（ID 前 8 位即可）         ║
║  /history [N]       查看对话历史（可选：只显示最近 N 条）    ║
║  /clear             清空当前会话的对话历史                   ║
║  /delete <会话ID>   删除指定会话                             ║
║  /status            显示当前会话信息                         ║
║  /help              显示此帮助信息                           ║
║  exit / quit        退出程序                                 ║
╚══════════════════════════════════════════════════════════════╝
"""

def create_llm():
    """Create LLM instance based on LLM_PROVIDER environment variable."""
    provider = os.getenv("LLM_PROVIDER", "deepseek").lower()

    if provider == "claude":
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
        model = os.getenv("CLAUDE_MODEL", "claude-4.6-sonnet")

        if not auth_token:
            raise ValueError("ANTHROPIC_AUTH_TOKEN is not set in .env")

        print(f"[LLM] Using Claude model: {model}")
        return ChatAnthropic(
            model=model,
            anthropic_api_key=auth_token,
            anthropic_api_url=base_url,
            temperature=0.1,
            max_tokens=2000,
        )
    else:
        # Default: DeepSeek
        print("[LLM] Using DeepSeek model: deepseek-chat")
        return ChatDeepSeek(
            model="deepseek-chat",
            temperature=0.1,
            max_tokens=2000,
            timeout=None,
            max_retries=2,
        )

def create_pdm_agent():
    # Initialize LLM
    llm = create_llm()

    # Initialize Tools
    tools = [
        ListTablesTool(),
        TableSchemaTool(),
        SearchTablesTool(),
        RelationshipTool(),
        ExecuteSQLTool()
    ]

    # Define the System Prompt
    system_message = SystemMessage(content="""You are a PDM expert assistant and Database Analyst. 
    Help users understand table structure, relationships, and query actual data from MySQL or Oracle databases.
    
    1. For conceptual searches, use 'search_tables'.
    2. For table details, use 'get_table_schema' with the table's CODE.
    3. For connections, use 'find_relationships'.
    4. To query actual data from MySQL or Oracle, use 'execute_sql'. 
       Before running SQL, always verify the table structure and database type.
       Try to limit results (e.g., LIMIT 5 or FETCH FIRST 5 ROWS ONLY) to avoid overwhelming the output.
    5. Respond in the user's language (Chinese/English).""")

    # Construct the Agent using LangGraph (Modern way)
    agent_executor = create_agent(llm, tools, system_prompt=system_message)
    
    return agent_executor


def handle_command(cmd: str, conv_manager: ConversationManager) -> bool:
    """
    处理斜杠命令。

    Args:
        cmd: 用户输入的命令字符串（已去除首尾空白）
        conv_manager: 会话管理器实例

    Returns:
        True 表示命令已处理，False 表示不是有效命令。
    """
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if command == "/help":
        print(HELP_TEXT)

    elif command == "/new":
        session = conv_manager.new_session(name=arg)
        print(f"\n✅ 已创建新会话: [{session.session_id[:8]}] {session.name}")

    elif command == "/sessions":
        print("\n📋 所有会话：")
        print(conv_manager.format_sessions_table())
        print()

    elif command == "/switch":
        if not arg:
            print("❌ 请提供会话 ID（前 8 位即可）。例如: /switch abc12345")
            return True
        # 支持前缀匹配
        matched = [
            sid for sid in conv_manager.sessions
            if sid.startswith(arg)
        ]
        if not matched:
            print(f"❌ 未找到 ID 前缀为 '{arg}' 的会话。")
        elif len(matched) > 1:
            print(f"❌ 前缀 '{arg}' 匹配到多个会话，请提供更多字符以唯一匹配。")
        else:
            session = conv_manager.switch_session(matched[0])
            print(f"\n✅ 已切换至会话: [{session.session_id[:8]}] {session.name}")

    elif command == "/history":
        # 解析可选的 N 参数（最近 N 条）
        max_display = 0
        if arg:
            try:
                max_display = int(arg)
                if max_display <= 0:
                    raise ValueError
            except ValueError:
                print(f"❌ 参数错误：'/history {arg}' 中的 N 必须是正整数。例如: /history 10")
                return True
        print()
        print(conv_manager.format_history(max_display=max_display))

    elif command == "/clear":
        conv_manager.clear_current_session()
        session = conv_manager.get_current_session()
        print(f"\n🗑️  会话 [{session.session_id[:8]}] 的对话历史已清空。")

    elif command == "/delete":
        if not arg:
            print("❌ 请提供会话 ID（前 8 位即可）。例如: /delete abc12345")
            return True
        matched = [
            sid for sid in conv_manager.sessions
            if sid.startswith(arg)
        ]
        if not matched:
            print(f"❌ 未找到 ID 前缀为 '{arg}' 的会话。")
        elif len(matched) > 1:
            print(f"❌ 前缀 '{arg}' 匹配到多个会话，请提供更多字符以唯一匹配。")
        else:
            sid = matched[0]
            name = conv_manager.sessions[sid].name
            conv_manager.delete_session(sid)
            print(f"\n🗑️  会话 [{sid[:8]}] '{name}' 已删除。")

    elif command == "/status":
        session = conv_manager.get_current_session()
        print(f"\n📌 当前会话状态:")
        print(f"   ID:     {session.session_id[:8]}...")
        print(f"   名称:   {session.name}")
        print(f"   消息数: {session.message_count()} 条（最大 {session.max_messages} 条）")
        print(f"   创建于: {session.created_at[:19]}")
        print(f"   更新于: {session.updated_at[:19]}")
        print()

    else:
        return False  # 不是已知命令

    return True


if __name__ == "__main__":
    # 初始化 Agent
    agent_executor = create_pdm_agent()

    # 初始化多轮对话管理器（会话自动从磁盘恢复）
    conv_manager = ConversationManager(
        persist_path=os.getenv("CONVERSATION_PERSIST_PATH", "./data/conversations.json"),
        max_messages_per_session=int(os.getenv("MAX_MESSAGES_PER_SESSION", "50")),
    )

    # 显示启动信息
    current = conv_manager.get_current_session()
    print("=" * 60)
    print("  PDM Assistant 已就绪！（输入 /help 查看所有命令）")
    print(f"  当前会话: [{current.session_id[:8]}] {current.name}")
    print(f"  历史消息: {current.message_count()} 条")
    print("=" * 60)

    while True:
        # 显示会话提示符
        session = conv_manager.get_current_session()
        try:
            user_input = input(f"\n[{session.name}] You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 再见！")
            break

        if not user_input:
            continue

        # 处理退出命令
        if user_input.lower() in ["exit", "quit"]:
            print("👋 再见！")
            break

        # 处理斜杠命令
        if user_input.startswith("/"):
            handled = handle_command(user_input, conv_manager)
            if not handled:
                print(f"❓ 未知命令: {user_input}。输入 /help 查看可用命令。")
            continue

        # -------------------------------------------------------
        # 多轮对话：获取历史 + 追加当前用户消息，一起传给 Agent
        # -------------------------------------------------------
        history = conv_manager.get_history()
        current_human_msg = HumanMessage(content=user_input)
        messages_to_send = history + [current_human_msg]

        try:
            response = agent_executor.invoke({"messages": messages_to_send})
        except Exception as e:
            print(f"\n❌ Agent 调用失败: {e}")
            continue

        # 取出 AI 回复（LangGraph 的结果在最后一条消息）
        ai_msg = response["messages"][-1]
        assistant_content = ai_msg.content
        print(f"\nAssistant: {assistant_content}")

        # 将本轮的用户消息和 AI 回复保存到上下文历史
        conv_manager.add_user_message(user_input)
        conv_manager.add_ai_message(AIMessage(content=assistant_content))
