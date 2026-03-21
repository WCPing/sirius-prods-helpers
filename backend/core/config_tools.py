"""
backend/core/config_tools.py

配置相关 Agent 工具：配置查找、配置列表。
"""

import sqlite3
import logging
from langchain.tools import BaseTool
from chromadb import PersistentClient
from chromadb.utils import embedding_functions

from backend.config import settings

logger = logging.getLogger(__name__)


def _get_embedding_fn():
    """统一的嵌入函数工厂，使用多语言模型。"""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=settings.MODEL_NAME
    )


class ConfigLookupTool(BaseTool):
    name: str = "config_lookup"
    description: str = (
        "查找配置项。先按 key 精确匹配（如 spring.datasource.url），"
        "再走语义搜索。适用于查询数据库连接配置、端口号、第三方服务地址等。"
        "输入配置关键词或自然语言描述。"
    )

    def _run(self, query: str) -> str:
        db_path = settings.SQLITE_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Step 1: Exact key match in SQLite
        cursor.execute("""
            SELECT file_path, config_key, config_value, config_type, profile, comment
            FROM config_entries
            WHERE config_key LIKE ?
            ORDER BY config_key
            LIMIT 10
        """, (f"%{query}%",))

        rows = cursor.fetchall()
        conn.close()

        if rows:
            output = f"Config entries matching '{query}' (exact key match):\n\n"
            for file_path, key, value, config_type, profile, comment in rows:
                output += f"  {key} = {value}\n"
                output += f"    File: {file_path}"
                if profile:
                    output += f" [profile: {profile}]"
                output += f"\n"
                if comment:
                    output += f"    Comment: {comment}\n"
            return output

        # Step 2: Semantic search in ChromaDB
        chroma_path = settings.CHROMA_DB_PATH
        embedding_fn = _get_embedding_fn()
        client = PersistentClient(path=chroma_path)

        try:
            collection = client.get_collection(
                name="config_entries", embedding_function=embedding_fn
            )
        except Exception:
            return f"Config index not found. No config entries matching '{query}'."

        results = collection.query(query_texts=[query], n_results=5)

        if not results["documents"][0]:
            return f"No config entries found matching '{query}'."

        output = f"Config entries matching '{query}' (semantic search):\n\n"
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            output += f"  {meta.get('key_path', '')}\n"
            output += f"    {doc}\n"
            if meta.get("profile"):
                output += f"    Profile: {meta['profile']}\n"
            output += "\n"

        return output


class ListConfigsTool(BaseTool):
    name: str = "list_configs"
    description: str = (
        "列出配置文件概览，按文件分组展示配置数量和 profile 信息。"
        "可选输入 source_id 或文件路径进行过滤，不输入则返回所有。"
    )

    def _run(self, filter_text: str = "") -> str:
        db_path = settings.SQLITE_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if filter_text:
            cursor.execute("""
                SELECT file_path, config_type, profile, COUNT(*) as cnt
                FROM config_entries
                WHERE file_path LIKE ? OR source_id LIKE ?
                GROUP BY file_path, config_type, profile
                ORDER BY file_path
            """, (f"%{filter_text}%", f"%{filter_text}%"))
        else:
            cursor.execute("""
                SELECT file_path, config_type, profile, COUNT(*) as cnt
                FROM config_entries
                GROUP BY file_path, config_type, profile
                ORDER BY file_path
            """)

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "No config entries found in the index."

        output = "Config Files Overview:\n\n"
        total = 0
        for file_path, config_type, profile, cnt in rows:
            profile_str = f" [profile: {profile}]" if profile else ""
            output += f"  {file_path} ({config_type}{profile_str}): {cnt} entries\n"
            total += cnt

        output += f"\nTotal: {total} config entries across {len(rows)} files\n"
        return output
