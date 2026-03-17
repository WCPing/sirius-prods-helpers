"""
backend/core/trace_tools.py

链路追踪 Agent 工具：组件追踪、配置引用查找、表使用查找。
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


class TraceComponentTool(BaseTool):
    name: str = "trace_component"
    description: str = (
        "Traces the full call chain for a component: Config → Controller → Service → Mapper → Table. "
        "Input should be a component name, API path, or description of what you want to trace."
    )

    def _run(self, query: str) -> str:
        db_path = settings.SQLITE_DB_PATH
        chroma_path = settings.CHROMA_DB_PATH

        # Step 1: 语义搜索找到相关代码
        embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()
        client = PersistentClient(path=chroma_path)
        try:
            collection = client.get_collection(name="code_chunks", embedding_function=embedding_fn)
        except Exception:
            return "Code index not found. Please index a code source first."

        results = collection.query(query_texts=[query], n_results=3)

        if not results["documents"][0]:
            return f"No code found matching '{query}'."

        # 收集起始节点
        start_ids = []
        start_names = []
        for meta in results["metadatas"][0]:
            qname = meta.get("qualified_name", "")
            start_names.append(qname)
            # 查找对应的 chunk_id
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT chunk_id FROM code_chunks WHERE qualified_name = ?", (qname,))
            row = cursor.fetchone()
            conn.close()
            if row:
                start_ids.append(row[0])

        # Step 2: 沿 cross_references 展开链路
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        trace_output = f"Trace results for '{query}':\n\n"

        for start_name in start_names:
            trace_output += f"=== Starting from: {start_name} ===\n"

            # 查找从此节点出发的所有引用
            cursor.execute("""
                SELECT ref_type, to_type, to_key, context
                FROM cross_references
                WHERE from_id = ? OR from_name LIKE ?
                ORDER BY ref_type
            """, (start_name, f"%{start_name.split('.')[-1]}%"))

            outgoing = cursor.fetchall()
            if outgoing:
                trace_output += "Outgoing references:\n"
                for ref_type, to_type, to_key, context in outgoing:
                    trace_output += f"  → [{ref_type}] {to_type}: {to_key}\n"
                    if context:
                        trace_output += f"    Context: {context}\n"

            # 查找引用此节点的所有代码
            cursor.execute("""
                SELECT ref_type, from_type, from_id, from_name, context
                FROM cross_references
                WHERE to_key LIKE ?
                ORDER BY ref_type
            """, (f"%{start_name.split('.')[-1]}%",))

            incoming = cursor.fetchall()
            if incoming:
                trace_output += "Incoming references:\n"
                for ref_type, from_type, from_id, from_name, context in incoming:
                    trace_output += f"  ← [{ref_type}] {from_type}: {from_name} ({from_id})\n"
                    if context:
                        trace_output += f"    Context: {context}\n"

            if not outgoing and not incoming:
                trace_output += "  No cross-references found for this component.\n"

            trace_output += "\n"

        # Step 3: 尝试组装完整链路
        trace_output += self._build_full_chain(cursor, start_names)

        conn.close()
        return trace_output

    def _build_full_chain(self, cursor, start_names: list) -> str:
        """尝试从起始点构建 Config → Controller → Service → Mapper → Table 链。"""
        chain_parts = {
            "config": [],
            "controller": [],
            "service": [],
            "mapper": [],
            "table": [],
        }

        for name in start_names:
            short_name = name.split(".")[-1] if "." in name else name

            # 查找配置引用
            cursor.execute("""
                SELECT to_key, context FROM cross_references
                WHERE (from_id LIKE ? OR from_name LIKE ?) AND ref_type = 'reads_config'
            """, (f"%{short_name}%", f"%{short_name}%"))
            for to_key, ctx in cursor.fetchall():
                chain_parts["config"].append(f"${{{to_key}}}")

            # 判断组件类型
            cursor.execute("""
                SELECT metadata FROM code_chunks
                WHERE qualified_name LIKE ? AND chunk_type = 'class'
            """, (f"%{short_name}%",))
            for (meta_str,) in cursor.fetchall():
                try:
                    meta = json.loads(meta_str) if meta_str else {}
                except (json.JSONDecodeError, TypeError):
                    meta = {}
                annotations = [a.get("name", "") for a in meta.get("annotations", [])]
                if any(a in ("Controller", "RestController") for a in annotations):
                    chain_parts["controller"].append(name)
                elif any(a in ("Service",) for a in annotations):
                    chain_parts["service"].append(name)
                elif any(a in ("Mapper", "Repository") for a in annotations):
                    chain_parts["mapper"].append(name)

            # 查找表引用
            cursor.execute("""
                SELECT to_key FROM cross_references
                WHERE (from_id LIKE ? OR from_name LIKE ?)
                  AND ref_type IN ('queries_table', 'maps_to_entity')
            """, (f"%{short_name}%", f"%{short_name}%"))
            for (to_key,) in cursor.fetchall():
                chain_parts["table"].append(to_key)

        # 组装链路
        chain_str = ""
        if any(chain_parts.values()):
            chain_str += "--- Assembled Chain ---\n"
            if chain_parts["config"]:
                chain_str += f"Config: {', '.join(set(chain_parts['config']))}\n"
            if chain_parts["controller"]:
                chain_str += f"  → Controller: {', '.join(set(chain_parts['controller']))}\n"
            if chain_parts["service"]:
                chain_str += f"  → Service: {', '.join(set(chain_parts['service']))}\n"
            if chain_parts["mapper"]:
                chain_str += f"  → Mapper: {', '.join(set(chain_parts['mapper']))}\n"
            if chain_parts["table"]:
                chain_str += f"  → Table: {', '.join(set(chain_parts['table']))}\n"

        return chain_str


class FindConfigUsageTool(BaseTool):
    name: str = "find_config_usage"
    description: str = (
        "Finds all code locations that reference a specific configuration key "
        "(e.g., from @Value annotations or property files). "
        "Input should be the config key or partial key to search for."
    )

    def _run(self, config_key: str) -> str:
        db_path = settings.SQLITE_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT cr.from_type, cr.from_id, cr.from_name, cr.to_key, cr.context,
                   cc.file_path, cc.line_start
            FROM cross_references cr
            LEFT JOIN code_chunks cc ON cr.from_id = cc.qualified_name
            WHERE cr.to_key LIKE ? AND cr.ref_type = 'reads_config'
            ORDER BY cr.from_id
        """, (f"%{config_key}%",))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"No code references found for config key '{config_key}'."

        output = f"Config key '{config_key}' is referenced in:\n\n"
        for from_type, from_id, from_name, to_key, context, file_path, line_start in rows:
            output += f"- [{from_type}] {from_id}\n"
            if file_path:
                output += f"  File: {file_path}:{line_start}\n"
            output += f"  Key: {to_key}\n"
            if context:
                output += f"  Context: {context}\n"
            output += "\n"

        return output


class FindTableUsageTool(BaseTool):
    name: str = "find_table_usage"
    description: str = (
        "Finds all code that references a specific database table "
        "(through MyBatis mappers, @TableName annotations, SQL statements, etc.). "
        "Input should be the table name to search for."
    )

    def _run(self, table_name: str) -> str:
        db_path = settings.SQLITE_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT cr.ref_type, cr.from_type, cr.from_id, cr.from_name,
                   cr.to_key, cr.context,
                   cc.file_path, cc.line_start
            FROM cross_references cr
            LEFT JOIN code_chunks cc ON cr.from_id = cc.qualified_name
            WHERE cr.to_key LIKE ?
              AND cr.ref_type IN ('queries_table', 'maps_to_entity')
            ORDER BY cr.ref_type, cr.from_id
        """, (f"%{table_name}%",))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"No code references found for table '{table_name}'."

        output = f"Table '{table_name}' is referenced in:\n\n"
        for ref_type, from_type, from_id, from_name, to_key, context, file_path, line_start in rows:
            output += f"- [{ref_type}] {from_type}: {from_id}\n"
            if file_path:
                output += f"  File: {file_path}:{line_start}\n"
            if context:
                output += f"  Context: {context}\n"
            output += "\n"

        return output
