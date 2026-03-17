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


class SearchCodeTool(BaseTool):
    name: str = "search_code"
    description: str = (
        "Performs a semantic search across indexed code to find relevant code snippets. "
        "Input should be a natural language query describing what code you're looking for."
    )

    def _run(self, query: str) -> str:
        chroma_path = settings.CHROMA_DB_PATH
        embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()

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
