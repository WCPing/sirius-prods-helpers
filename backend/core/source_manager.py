"""
backend/core/source_manager.py

知识源管理器：知识源的注册、同步（Git clone/pull）、删除、列表。
"""

import os
import uuid
import shutil
import sqlite3
import logging
from enum import Enum
from typing import Optional, List, Dict, Any

from backend.config import settings

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    pdm = "pdm"
    git = "git"
    local = "local"


class SourceManager:
    """管理知识源的注册、同步和删除。"""

    def __init__(self):
        self.db_path = settings.SQLITE_DB_PATH
        self.repos_dir = settings.REPOS_DIR
        os.makedirs(self.repos_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------

    def register_source(
        self,
        name: str,
        source_type: str,
        location: str,
        branch: str = "main",
        patterns: str = "",
    ) -> str:
        """注册新知识源，返回生成的 source_id。"""
        source_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO knowledge_sources (id, name, source_type, location, branch, include_patterns, status)
            VALUES (?, ?, ?, ?, ?, ?, 'registered')
        """, (source_id, name, source_type, location, branch, patterns))
        conn.commit()
        conn.close()
        logger.info(f"Registered source '{name}' (type={source_type}, id={source_id})")
        return source_id

    # ------------------------------------------------------------------
    # 同步
    # ------------------------------------------------------------------

    def sync_source(self, source_id: str) -> bool:
        """同步知识源：Git -> clone/pull；Local/PDM -> 验证路径存在。"""
        source = self.get_source(source_id)
        if not source:
            logger.error(f"Source '{source_id}' not found")
            return False

        source_type = source["source_type"]
        location = source["location"]
        branch = source.get("branch", "main")

        if source_type == "git":
            return self._sync_git(source_id, location, branch)
        elif source_type in ("local", "pdm"):
            if os.path.exists(location):
                logger.info(f"Local source '{source_id}' path verified: {location}")
                self._update_status(source_id, "synced")
                return True
            else:
                logger.error(f"Local path does not exist: {location}")
                self._update_status(source_id, "error")
                return False

        logger.warning(f"Unknown source type: {source_type}")
        return False

    def _sync_git(self, source_id: str, repo_url: str, branch: str) -> bool:
        """Git clone 或 pull 到 repos 目录。"""
        try:
            import git
        except ImportError:
            logger.error("gitpython is not installed. Run: uv pip install gitpython")
            return False

        clone_dir = os.path.join(self.repos_dir, source_id)

        try:
            if os.path.exists(clone_dir) and os.path.isdir(os.path.join(clone_dir, ".git")):
                # Pull 更新
                logger.info(f"Pulling updates for source '{source_id}'")
                repo = git.Repo(clone_dir)
                origin = repo.remotes.origin
                origin.pull(branch)
            else:
                # Clone
                logger.info(f"Cloning '{repo_url}' (branch={branch}) into {clone_dir}")
                git.Repo.clone_from(repo_url, clone_dir, branch=branch)

            # 更新知识源 location 为本地克隆路径
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE knowledge_sources SET location = ?, status = 'synced', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (clone_dir, source_id),
            )
            conn.commit()
            conn.close()
            logger.info(f"Git source '{source_id}' synced successfully")
            return True
        except Exception as e:
            logger.error(f"Git sync failed for source '{source_id}': {e}")
            self._update_status(source_id, "error")
            return False

    # ------------------------------------------------------------------
    # 删除
    # ------------------------------------------------------------------

    def remove_source(self, source_id: str) -> bool:
        """删除知识源：清理索引数据 + 删除注册记录 + 清理克隆目录。"""
        from backend.core.unified_indexer import unified_indexer

        source = self.get_source(source_id)
        if not source:
            logger.error(f"Source '{source_id}' not found")
            return False

        # 清理索引数据
        unified_indexer._clear_source_data(source_id)

        # 删除注册记录
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM knowledge_sources WHERE id = ?", (source_id,))
        conn.commit()
        conn.close()

        # 清理克隆目录（仅 Git 类型）
        clone_dir = os.path.join(self.repos_dir, source_id)
        if os.path.exists(clone_dir):
            shutil.rmtree(clone_dir, ignore_errors=True)
            logger.info(f"Removed clone directory: {clone_dir}")

        logger.info(f"Source '{source_id}' removed successfully")
        return True

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_sources(self) -> List[Dict[str, Any]]:
        """列出所有已注册的知识源。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM knowledge_sources ORDER BY created_at DESC")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取知识源详情。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM knowledge_sources WHERE id = ?", (source_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # 自动注册 PDM 知识源
    # ------------------------------------------------------------------

    def ensure_pdm_source_registered(self) -> Optional[str]:
        """首次启动时自动将 PDM_FILES_DIR 注册为 PDM 类型知识源。"""
        pdm_dir = settings.PDM_FILES_DIR
        if not os.path.exists(pdm_dir):
            logger.info(f"PDM directory not found, skipping auto-register: {pdm_dir}")
            return None

        # 检查是否已注册过
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM knowledge_sources WHERE source_type = 'pdm' AND location = ?",
            (pdm_dir,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            logger.info(f"PDM source already registered: {row[0]}")
            return row[0]

        source_id = self.register_source(
            name="Default PDM Files",
            source_type="pdm",
            location=pdm_dir,
        )
        logger.info(f"Auto-registered PDM source: {source_id}")
        return source_id

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _update_status(self, source_id: str, status: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE knowledge_sources SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, source_id),
        )
        conn.commit()
        conn.close()


# 模块级单例
source_manager = SourceManager()
