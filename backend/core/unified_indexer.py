"""
backend/core/unified_indexer.py

统一索引器：管理 SQLite schema 扩展 + ChromaDB 多 Collection + 索引调度。
保留现有 PDM 4 张表不动，新增 5 张表用于代码/配置索引。
"""

import os
import hashlib
import json
import sqlite3
import logging
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.utils import embedding_functions

from backend.config import settings

logger = logging.getLogger(__name__)


class UnifiedIndexer:
    """统一索引器，管理 PDM + 代码 + 配置的索引生命周期。"""

    def __init__(self):
        self.db_path = settings.SQLITE_DB_PATH
        self.chroma_path = settings.CHROMA_DB_PATH

        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        os.makedirs(self.chroma_path, exist_ok=True)

        # 初始化新增的 SQLite 表
        self._init_sqlite()

        # ChromaDB 客户端和嵌入函数
        self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
        self.embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()

        # 保留现有 pdm_metadata collection，新增 code_chunks 和 config_entries
        self.code_collection = self.chroma_client.get_or_create_collection(
            name="code_chunks",
            embedding_function=self.embedding_fn,
        )
        self.config_collection = self.chroma_client.get_or_create_collection(
            name="config_entries",
            embedding_function=self.embedding_fn,
        )

    # ------------------------------------------------------------------
    # SQLite schema 扩展（新增 5 张表，保留现有 4 张 PDM 表）
    # ------------------------------------------------------------------

    def _init_sqlite(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_sources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                location TEXT NOT NULL,
                branch TEXT DEFAULT 'main',
                include_patterns TEXT DEFAULT '',
                status TEXT DEFAULT 'registered',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_chunks (
                chunk_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                chunk_type TEXT NOT NULL,
                language TEXT NOT NULL,
                name TEXT NOT NULL,
                qualified_name TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                line_start INTEGER DEFAULT 0,
                line_end INTEGER DEFAULT 0,
                FOREIGN KEY(source_id) REFERENCES knowledge_sources(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_entries (
                entry_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                config_key TEXT NOT NULL,
                config_value TEXT DEFAULT '',
                config_type TEXT DEFAULT 'property',
                FOREIGN KEY(source_id) REFERENCES knowledge_sources(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS indexed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                rel_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_id, rel_path),
                FOREIGN KEY(source_id) REFERENCES knowledge_sources(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cross_references (
                ref_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                from_type TEXT NOT NULL,
                from_id TEXT NOT NULL,
                from_name TEXT DEFAULT '',
                to_type TEXT NOT NULL,
                to_key TEXT NOT NULL,
                ref_type TEXT NOT NULL,
                context TEXT DEFAULT '',
                FOREIGN KEY(source_id) REFERENCES knowledge_sources(id)
            )
        """)

        # 高频查询字段索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_code_chunks_qualified_name ON code_chunks(qualified_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_code_chunks_source_id ON code_chunks(source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_code_chunks_file_path ON code_chunks(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_code_chunks_chunk_type ON code_chunks(chunk_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cross_references_to_key ON cross_references(to_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cross_references_ref_type ON cross_references(ref_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cross_references_from_id ON cross_references(from_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_indexed_files_source ON indexed_files(source_id, rel_path)")

        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # 索引调度
    # ------------------------------------------------------------------

    def index_source(self, source_id: str):
        """按 source_type 分发到对应索引方法。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT source_type, location FROM knowledge_sources WHERE id = ?", (source_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.error(f"Knowledge source '{source_id}' not found")
            return

        source_type, location = row

        if source_type == "pdm":
            self.index_pdm_source(source_id, location)
        elif source_type in ("git", "local"):
            self.index_code_source(source_id, location)
        else:
            logger.warning(f"Unknown source type: {source_type}")

    def index_pdm_source(self, source_id: str, pdm_dir: str):
        """复用 PDMParser 逻辑索引 PDM 文件。"""
        from backend.core.parser import PDMParser
        from backend.core.indexer import PDMIndexer

        if not os.path.exists(pdm_dir):
            logger.error(f"PDM directory not found: {pdm_dir}")
            return

        # 使用现有的 PDMIndexer 进行索引
        indexer = PDMIndexer()
        for file_name in os.listdir(pdm_dir):
            if file_name.endswith(".pdm"):
                file_path = os.path.join(pdm_dir, file_name)
                indexer.index_file(file_path)

        # 更新知识源状态
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE knowledge_sources SET status = 'indexed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (source_id,),
        )
        conn.commit()
        conn.close()
        logger.info(f"PDM source '{source_id}' indexed successfully")

    def index_code_source(self, source_id: str, code_dir: str):
        """遍历代码目录，解析并索引所有匹配文件。"""
        from backend.core.code_parser import CodeParser

        if not os.path.exists(code_dir):
            logger.error(f"Code directory not found: {code_dir}")
            return

        parser = CodeParser(source_id)
        extensions = settings.CODE_INDEX_EXTENSIONS
        exclude_dirs = set(settings.CODE_EXCLUDE_DIRS)
        file_count = 0
        chunk_count = 0

        for root, dirs, files in os.walk(code_dir):
            # 原地修改 dirs 列表，跳过排除目录
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for fname in files:
                ext = os.path.splitext(fname)[1]
                if ext not in extensions:
                    continue

                # 跳过 i18n 国际化文件（纯翻译文本，无业务逻辑）
                if "i18n" in fname or "i18n" in root:
                    continue

                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, code_dir)

                # 增量：跳过未变化的文件
                if self._is_file_unchanged(source_id, rel_path, abs_path):
                    continue

                try:
                    chunks = parser.parse_file(abs_path, rel_path)
                    if chunks:
                        self._store_chunks(source_id, chunks)
                        chunk_count += len(chunks)
                    self._update_file_hash(source_id, rel_path, abs_path)
                    file_count += 1
                except Exception as e:
                    logger.error(f"Failed to parse {rel_path}: {e}")

        # 更新知识源状态
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE knowledge_sources SET status = 'indexed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (source_id,),
        )
        conn.commit()
        conn.close()
        logger.info(f"Code source '{source_id}' indexed: {file_count} files, {chunk_count} chunks")

    def reindex_source(self, source_id: str):
        """清除旧数据后全量重建索引。"""
        self._clear_source_data(source_id)
        self.index_source(source_id)

    # ------------------------------------------------------------------
    # 存储
    # ------------------------------------------------------------------

    def _store_chunks(self, source_id: str, chunks: list):
        """批量写入 code_chunks 表 + ChromaDB upsert + cross_references。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        chroma_ids = []
        chroma_docs = []
        chroma_metas = []

        for chunk in chunks:
            metadata_str = json.dumps(chunk.metadata, ensure_ascii=False) if chunk.metadata else "{}"
            cross_refs = chunk.metadata.get("cross_refs", []) if chunk.metadata else []

            # SQLite: code_chunks
            cursor.execute("""
                INSERT OR REPLACE INTO code_chunks
                (chunk_id, source_id, file_path, chunk_type, language, name,
                 qualified_name, content, summary, metadata, line_start, line_end)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk.chunk_id, source_id, chunk.file_path, chunk.chunk_type,
                chunk.language, chunk.name, chunk.qualified_name,
                chunk.content, chunk.summary, metadata_str,
                chunk.line_start, chunk.line_end,
            ))

            # ChromaDB 文档：优先用 qualified_name + summary 做向量匹配
            # 对 Java class/method/field，名称和摘要比原始代码更有语义价值
            doc_parts = [
                f"{chunk.chunk_type}: {chunk.qualified_name}",
                chunk.summary,
                f"file: {chunk.file_path}",
            ]
            # 仅对方法和类追加少量代码内容辅助匹配
            if chunk.chunk_type in ("method", "class", "interface") and chunk.content:
                doc_parts.append(chunk.content[:500])
            doc_text = "\n".join(doc_parts)
            chroma_ids.append(chunk.chunk_id)
            chroma_docs.append(doc_text)
            chroma_metas.append({
                "source_id": source_id,
                "file_path": chunk.file_path,
                "chunk_type": chunk.chunk_type,
                "language": chunk.language,
                "name": chunk.name,
                "qualified_name": chunk.qualified_name,
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
            })

            # cross_references
            for ref in cross_refs:
                cursor.execute("""
                    INSERT OR REPLACE INTO cross_references
                    (ref_id, source_id, from_type, from_id, from_name, to_type, to_key, ref_type, context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ref.get("ref_id", ""),
                    source_id,
                    ref.get("from_type", ""),
                    ref.get("from_id", ""),
                    ref.get("from_name", ""),
                    ref.get("to_type", ""),
                    ref.get("to_key", ""),
                    ref.get("ref_type", ""),
                    ref.get("context", ""),
                ))

        conn.commit()
        conn.close()

        # ChromaDB batch upsert
        if chroma_ids:
            batch_size = 100
            for i in range(0, len(chroma_ids), batch_size):
                end = min(i + batch_size, len(chroma_ids))
                self.code_collection.upsert(
                    ids=chroma_ids[i:end],
                    documents=chroma_docs[i:end],
                    metadatas=chroma_metas[i:end],
                )

    # ------------------------------------------------------------------
    # 增量更新辅助
    # ------------------------------------------------------------------

    def _compute_file_hash(self, file_path: str) -> str:
        """计算文件 MD5 hash。"""
        h = hashlib.md5()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                h.update(block)
        return h.hexdigest()

    def _is_file_unchanged(self, source_id: str, rel_path: str, abs_path: str) -> bool:
        """通过 MD5 比对判断文件是否未变化。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_hash FROM indexed_files WHERE source_id = ? AND rel_path = ?",
            (source_id, rel_path),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return False

        current_hash = self._compute_file_hash(abs_path)
        return row[0] == current_hash

    def _update_file_hash(self, source_id: str, rel_path: str, abs_path: str):
        """更新文件 hash 记录。"""
        file_hash = self._compute_file_hash(abs_path)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO indexed_files (source_id, rel_path, file_hash)
            VALUES (?, ?, ?)
        """, (source_id, rel_path, file_hash))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def _clear_source_data(self, source_id: str):
        """删除某知识源的所有索引数据。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 获取所有 chunk_id 用于清理 ChromaDB
        cursor.execute("SELECT chunk_id FROM code_chunks WHERE source_id = ?", (source_id,))
        chunk_ids = [row[0] for row in cursor.fetchall()]

        # 清理 SQLite 表
        cursor.execute("DELETE FROM code_chunks WHERE source_id = ?", (source_id,))
        cursor.execute("DELETE FROM config_entries WHERE source_id = ?", (source_id,))
        cursor.execute("DELETE FROM cross_references WHERE source_id = ?", (source_id,))
        cursor.execute("DELETE FROM indexed_files WHERE source_id = ?", (source_id,))

        conn.commit()
        conn.close()

        # 清理 ChromaDB
        if chunk_ids:
            batch_size = 100
            for i in range(0, len(chunk_ids), batch_size):
                end = min(i + batch_size, len(chunk_ids))
                self.code_collection.delete(ids=chunk_ids[i:end])

        logger.info(f"Cleared all indexed data for source '{source_id}'")


# 模块级单例
unified_indexer = UnifiedIndexer()
