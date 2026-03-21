"""
backend/core/code_tools.py

代码相关 Agent 工具：语义搜索、结构查询、类详情、API 端点搜索。
"""

import os
import json
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


class SearchCodeTool(BaseTool):
    name: str = "search_code"
    description: str = (
        "Performs a semantic search across indexed code to find relevant code snippets. "
        "Input should be a natural language query describing what code you're looking for."
    )

    def _run(self, query: str) -> str:
        chroma_path = settings.CHROMA_DB_PATH
        embedding_fn = _get_embedding_fn()

        client = PersistentClient(path=chroma_path)
        try:
            collection = client.get_collection(name="code_chunks", embedding_function=embedding_fn)
        except Exception:
            return "Code index not found. Please index a code source first."

        results = collection.query(query_texts=[query], n_results=5)

        if not results["documents"][0]:
            return "No matching code found for your query."

        output = "Search Results (Top 5 code snippets):\n\n"
        for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0]), 1):
            file_path = meta.get("file_path", "unknown")
            chunk_type = meta.get("chunk_type", "")
            name = meta.get("name", "")
            qualified_name = meta.get("qualified_name", "")
            line_start = meta.get("line_start", 0)
            line_end = meta.get("line_end", 0)

            output += f"--- Result {i} ---\n"
            output += f"File: {file_path} (lines {line_start}-{line_end})\n"
            output += f"Type: {chunk_type} | Name: {qualified_name}\n"
            # Truncate long content
            content = doc[:500] if len(doc) > 500 else doc
            output += f"Content:\n{content}\n\n"

        return output


class GetCodeStructureTool(BaseTool):
    name: str = "get_code_structure"
    description: str = (
        "Gets the code structure (classes, methods, fields) for a specific file path. "
        "Input should be a file path or partial path to search for."
    )

    def _run(self, file_path: str) -> str:
        db_path = settings.SQLITE_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT chunk_type, name, qualified_name, line_start, line_end, summary
            FROM code_chunks
            WHERE file_path LIKE ?
            ORDER BY line_start
        """, (f"%{file_path}%",))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"No code structure found for path containing '{file_path}'."

        output = f"Code Structure for files matching '{file_path}':\n\n"
        for chunk_type, name, qualified_name, line_start, line_end, summary in rows:
            indent = "  " if chunk_type in ("method", "field") else ""
            output += f"{indent}[{chunk_type}] {qualified_name} (L{line_start}-L{line_end})\n"
            if summary:
                output += f"{indent}  {summary}\n"

        return output


class GetClassDetailTool(BaseTool):
    name: str = "get_class_detail"
    description: str = (
        "Gets detailed information about a specific class by name. "
        "Input should be a class name (e.g., 'UserController' or 'com.example.UserService')."
    )

    def _run(self, class_name: str) -> str:
        db_path = settings.SQLITE_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT chunk_id, file_path, chunk_type, name, qualified_name,
                   content, summary, metadata, line_start, line_end
            FROM code_chunks
            WHERE qualified_name LIKE ?
            ORDER BY chunk_type, line_start
        """, (f"%{class_name}%",))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"No class found matching '{class_name}'."

        output = f"Class Detail for '{class_name}':\n\n"
        for (chunk_id, file_path, chunk_type, name, qualified_name,
             content, summary, metadata_str, line_start, line_end) in rows:
            output += f"--- [{chunk_type}] {qualified_name} ---\n"
            output += f"File: {file_path} (L{line_start}-L{line_end})\n"
            output += f"Summary: {summary}\n"

            # Parse metadata for additional info
            try:
                metadata = json.loads(metadata_str) if metadata_str else {}
            except (json.JSONDecodeError, TypeError):
                metadata = {}

            if metadata.get("annotations"):
                ann_names = [f"@{a['name']}" for a in metadata["annotations"]]
                output += f"Annotations: {', '.join(ann_names)}\n"

            if metadata.get("api_path"):
                output += f"API Path: [{metadata.get('http_method', 'GET')}] {metadata['api_path']}\n"

            # Show content (truncated)
            content_preview = content[:600] if len(content) > 600 else content
            output += f"Code:\n{content_preview}\n\n"

        return output


class SearchAPIEndpointsTool(BaseTool):
    name: str = "search_api_endpoints"
    description: str = (
        "Searches for API endpoints (Spring REST mappings) in the indexed code. "
        "Input should be a keyword to filter endpoints (e.g., 'user', 'login', '/api/v1')."
    )

    def _run(self, keyword: str) -> str:
        db_path = settings.SQLITE_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Search for methods with api_path in metadata
        cursor.execute("""
            SELECT name, qualified_name, file_path, metadata, line_start, summary
            FROM code_chunks
            WHERE chunk_type = 'method'
              AND metadata LIKE '%api_path%'
              AND (metadata LIKE ? OR qualified_name LIKE ? OR summary LIKE ?)
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"No API endpoints found matching '{keyword}'."

        output = f"API Endpoints matching '{keyword}':\n\n"
        for name, qualified_name, file_path, metadata_str, line_start, summary in rows:
            try:
                metadata = json.loads(metadata_str) if metadata_str else {}
            except (json.JSONDecodeError, TypeError):
                metadata = {}

            api_path = metadata.get("api_path", "")
            http_method = metadata.get("http_method", "GET")

            if api_path:
                output += f"[{http_method}] {api_path}\n"
                output += f"  Method: {qualified_name}\n"
                output += f"  File: {file_path}:{line_start}\n"
                if summary:
                    output += f"  Summary: {summary}\n"
                output += "\n"

        return output or f"No API endpoints with paths found matching '{keyword}'."


class GrepCodeTool(BaseTool):
    name: str = "grep_code"
    description: str = (
        "在索引的代码内容中精确搜索关键词（类似 grep）。"
        "适用于搜索精确的类名、函数名、CSS class、icon 名、变量名等。"
        "输入要搜索的关键词字符串。"
    )

    def _run(self, keyword: str) -> str:
        db_path = settings.SQLITE_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1) 先在 SQLite content 中搜索（快速路径）
        cursor.execute("""
            SELECT file_path, chunk_type, name, content, line_start, line_end
            FROM code_chunks
            WHERE content LIKE ?
            LIMIT 10
        """, (f"%{keyword}%",))

        rows = cursor.fetchall()

        # 2) 如果 SQLite 没找到，回退到源文件搜索（处理 content 截断问题）
        if not rows:
            rows = self._grep_source_files(cursor, keyword)

        conn.close()

        if not rows:
            return f"No code found containing '{keyword}'."

        output = f"Grep results for '{keyword}' (up to 10 matches):\n\n"
        for i, (file_path, chunk_type, name, content, line_start, line_end) in enumerate(rows, 1):
            output += f"--- Match {i} ---\n"
            output += f"File: {file_path} (lines {line_start}-{line_end})\n"
            output += f"Type: {chunk_type} | Name: {name}\n"

            # Show context around the keyword match
            lines = content.splitlines()
            matched_lines = []
            for j, line in enumerate(lines):
                if keyword.lower() in line.lower():
                    start = max(0, j - 1)
                    end = min(len(lines), j + 2)
                    for k in range(start, end):
                        prefix = ">>>" if k == j else "   "
                        matched_lines.append(f"  {prefix} L{line_start + k}: {lines[k][:200]}")
                    matched_lines.append("")
                    if len(matched_lines) > 15:
                        break

            if matched_lines:
                output += "Context:\n" + "\n".join(matched_lines) + "\n"
            else:
                output += f"Content (truncated): {content[:300]}\n"

            output += "\n"

        return output

    def _grep_source_files(self, cursor, keyword: str) -> list:
        """回退搜索：在源文件中搜索关键词（处理 SQLite content 被截断的情况）。"""
        # 获取知识源的 location（代码根目录）
        cursor.execute("SELECT id, location FROM knowledge_sources WHERE source_type IN ('git', 'local')")
        sources = cursor.fetchall()

        results = []
        for source_id, code_dir in sources:
            if not os.path.isdir(code_dir):
                continue

            # 获取该知识源的所有已索引文件路径
            cursor.execute(
                "SELECT rel_path FROM indexed_files WHERE source_id = ?",
                (source_id,),
            )
            indexed_paths = [row[0] for row in cursor.fetchall()]

            for rel_path in indexed_paths:
                abs_path = os.path.join(code_dir, rel_path)
                if not os.path.isfile(abs_path):
                    continue
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    for line_no, line in enumerate(lines, 1):
                        if keyword in line:
                            # 提取匹配行周围的上下文
                            start = max(0, line_no - 3)
                            end = min(len(lines), line_no + 2)
                            context = "".join(lines[start:end])
                            results.append((
                                rel_path,
                                "file_grep",
                                os.path.basename(rel_path),
                                context,
                                start + 1,
                                end,
                            ))
                            break  # 每个文件只取第一个匹配
                except Exception:
                    continue

                if len(results) >= 10:
                    break
            if len(results) >= 10:
                break

        return results
