"""
backend/api/routes/knowledge.py

知识源管理 API 路由。

接口列表：
  POST   /api/knowledge-sources              - 注册知识源
  GET    /api/knowledge-sources              - 列出所有知识源
  GET    /api/knowledge-sources/{id}         - 知识源详情
  DELETE /api/knowledge-sources/{id}         - 删除知识源
  POST   /api/knowledge-sources/{id}/index   - 触发索引
  POST   /api/knowledge-sources/{id}/sync    - 同步代码
  GET    /api/knowledge-sources/{id}/stats   - 索引统计
"""

import sqlite3
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks

from backend.api.models.request import RegisterSourceRequest
from backend.api.models.response import (
    BaseResponse,
    SourceInfo,
    SourceListResponse,
    SourceDetailResponse,
    SourceStatsResponse,
)
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-sources", tags=["知识源管理"])


def _source_dict_to_info(source: dict) -> SourceInfo:
    """将 source_manager 返回的 dict 转换为 SourceInfo。"""
    return SourceInfo(
        id=source["id"],
        name=source["name"],
        source_type=source["source_type"],
        location=source["location"],
        branch=source.get("branch", "main"),
        include_patterns=source.get("include_patterns", ""),
        status=source.get("status", "registered"),
        created_at=str(source.get("created_at", "")),
        updated_at=str(source.get("updated_at", "")),
    )


# ---------------------------------------------------------------
# POST /api/knowledge-sources — 注册知识源
# ---------------------------------------------------------------

@router.post(
    "",
    response_model=SourceDetailResponse,
    summary="注册知识源",
    description="注册一个新的知识源（PDM、Git 仓库或本地目录）。",
)
def register_source(body: RegisterSourceRequest):
    try:
        from backend.core.source_manager import source_manager

        source_id = source_manager.register_source(
            name=body.name,
            source_type=body.source_type,
            location=body.location,
            branch=body.branch,
            patterns=body.include_patterns,
        )
        source = source_manager.get_source(source_id)
        if not source:
            raise HTTPException(status_code=500, detail="注册失败")

        return SourceDetailResponse(
            success=True,
            message="知识源已注册",
            data=_source_dict_to_info(source),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"register_source error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# GET /api/knowledge-sources — 列出所有知识源
# ---------------------------------------------------------------

@router.get(
    "",
    response_model=SourceListResponse,
    summary="列出所有知识源",
    description="返回所有已注册的知识源列表。",
)
def list_sources():
    try:
        from backend.core.source_manager import source_manager

        sources = source_manager.list_sources()
        data = [_source_dict_to_info(s) for s in sources]
        return SourceListResponse(
            success=True,
            message="获取成功",
            data=data,
            total=len(data),
        )
    except Exception as e:
        logger.error(f"list_sources error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# GET /api/knowledge-sources/{source_id} — 知识源详情
# ---------------------------------------------------------------

@router.get(
    "/{source_id}",
    response_model=SourceDetailResponse,
    summary="知识源详情",
    description="根据 ID 获取知识源详细信息。",
)
def get_source(source_id: str):
    try:
        from backend.core.source_manager import source_manager

        source = source_manager.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail=f"知识源 '{source_id}' 不存在")

        return SourceDetailResponse(
            success=True,
            message="获取成功",
            data=_source_dict_to_info(source),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_source error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# DELETE /api/knowledge-sources/{source_id} — 删除知识源
# ---------------------------------------------------------------

@router.delete(
    "/{source_id}",
    response_model=BaseResponse,
    summary="删除知识源",
    description="删除知识源及其所有索引数据。",
)
def delete_source(source_id: str):
    try:
        from backend.core.source_manager import source_manager

        source = source_manager.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail=f"知识源 '{source_id}' 不存在")

        success = source_manager.remove_source(source_id)
        if not success:
            raise HTTPException(status_code=500, detail="删除失败")

        return BaseResponse(success=True, message=f"知识源 '{source['name']}' 已删除")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_source error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# POST /api/knowledge-sources/{source_id}/index — 触发索引
# ---------------------------------------------------------------

def _run_index(source_id: str):
    """后台索引任务。"""
    try:
        from backend.core.unified_indexer import unified_indexer
        unified_indexer.reindex_source(source_id)
        logger.info(f"Background indexing completed for source '{source_id}'")
    except Exception as e:
        logger.error(f"Background indexing failed for source '{source_id}': {e}")


@router.post(
    "/{source_id}/index",
    response_model=BaseResponse,
    summary="触发索引",
    description="后台触发知识源的全量重建索引。",
)
def trigger_index(source_id: str, background_tasks: BackgroundTasks):
    try:
        from backend.core.source_manager import source_manager

        source = source_manager.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail=f"知识源 '{source_id}' 不存在")

        background_tasks.add_task(_run_index, source_id)
        return BaseResponse(success=True, message="索引任务已提交，正在后台执行")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"trigger_index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# POST /api/knowledge-sources/{source_id}/sync — 同步代码
# ---------------------------------------------------------------

@router.post(
    "/{source_id}/sync",
    response_model=BaseResponse,
    summary="同步代码",
    description="同步知识源代码（Git pull 或验证本地路径）。",
)
def sync_source(source_id: str):
    try:
        from backend.core.source_manager import source_manager

        source = source_manager.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail=f"知识源 '{source_id}' 不存在")

        success = source_manager.sync_source(source_id)
        if not success:
            raise HTTPException(status_code=500, detail="同步失败")

        return BaseResponse(success=True, message="同步成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"sync_source error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# GET /api/knowledge-sources/{source_id}/stats — 索引统计
# ---------------------------------------------------------------

@router.get(
    "/{source_id}/stats",
    response_model=SourceStatsResponse,
    summary="索引统计",
    description="获取知识源的索引统计信息。",
)
def get_source_stats(source_id: str):
    try:
        from backend.core.source_manager import source_manager

        source = source_manager.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail=f"知识源 '{source_id}' 不存在")

        db_path = settings.SQLITE_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM code_chunks WHERE source_id = ?", (source_id,))
        code_chunks = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM config_entries WHERE source_id = ?", (source_id,))
        config_entries = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM cross_references WHERE source_id = ?", (source_id,))
        cross_references = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM indexed_files WHERE source_id = ?", (source_id,))
        indexed_files = cursor.fetchone()[0]

        conn.close()

        return SourceStatsResponse(
            success=True,
            message="获取成功",
            source_id=source_id,
            code_chunks=code_chunks,
            config_entries=config_entries,
            cross_references=cross_references,
            indexed_files=indexed_files,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_source_stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
