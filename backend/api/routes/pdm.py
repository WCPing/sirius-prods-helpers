"""
backend/api/routes/pdm.py

PDM（PowerDesigner 物理数据模型）相关 API 路由。

接口列表：
  GET  /api/pdm/tables               - 列出所有表
  GET  /api/pdm/tables/{table_code}  - 获取表结构详情
  POST /api/pdm/search               - 语义搜索表
  GET  /api/pdm/relationships/{code} - 查询表关联关系
  POST /api/pdm/sql/execute          - 执行 SQL 查询
  GET  /api/pdm/indexer/status       - 查询索引状态
  POST /api/pdm/indexer/reindex      - 重建索引
"""

import os
import sqlite3
import logging
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks

from chromadb import PersistentClient
from chromadb.utils import embedding_functions

from backend.api.models.request import SearchTablesRequest, ExecuteSQLRequest
from backend.api.models.response import (
    ListTablesResponse,
    TableDetailResponse,
    TableDetailInfo,
    TableInfo,
    ColumnInfo,
    SearchTablesResponse,
    SearchResult,
    RelationshipsResponse,
    RelationshipInfo,
    ExecuteSQLResponse,
    IndexStatusResponse,
    ReindexResponse,
)
from backend.core.db_manager import db_manager
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pdm", tags=["PDM 查询"])


def _get_sqlite_conn():
    """获取 SQLite 连接"""
    return sqlite3.connect(settings.SQLITE_DB_PATH)


# ---------------------------------------------------------------
# 列出所有表
# ---------------------------------------------------------------

@router.get(
    "/tables",
    response_model=ListTablesResponse,
    summary="列出所有表",
    description="返回 PDM 元数据库中所有已索引的数据表列表。",
)
def list_tables():
    try:
        conn = _get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT code, name, comment FROM tables ORDER BY code")
        rows = cursor.fetchall()
        conn.close()

        tables = [
            TableInfo(
                code=row[0] or "",
                name=row[1] or "",
                comment=row[2] or "",
            )
            for row in rows
        ]
        return ListTablesResponse(
            success=True,
            message="获取成功",
            data=tables,
            total=len(tables),
        )
    except Exception as e:
        logger.error(f"list_tables error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 获取表结构详情
# ---------------------------------------------------------------

@router.get(
    "/tables/{table_code}",
    response_model=TableDetailResponse,
    summary="获取表结构详情",
    description="根据表的 CODE 获取其详细结构，包括所有字段的名称、类型、注释等。",
)
def get_table_schema(table_code: str):
    try:
        conn = _get_sqlite_conn()
        cursor = conn.cursor()

        # 查询表基本信息
        cursor.execute(
            "SELECT id, name, comment FROM tables WHERE code = ?",
            (table_code,),
        )
        table_row = cursor.fetchone()
        if not table_row:
            conn.close()
            raise HTTPException(
                status_code=404,
                detail=f"表 '{table_code}' 不存在",
            )

        table_id, table_name, table_comment = table_row

        # 查询字段列表
        cursor.execute(
            """
            SELECT name, code, data_type, length, mandatory, comment
            FROM columns WHERE table_id = ?
            ORDER BY rowid
            """,
            (table_id,),
        )
        col_rows = cursor.fetchall()
        conn.close()

        columns = [
            ColumnInfo(
                name=r[0] or "",
                code=r[1] or "",
                data_type=r[2] or "",
                length=r[3] or "",
                mandatory=bool(r[4]),
                comment=r[5] or "",
            )
            for r in col_rows
        ]

        detail = TableDetailInfo(
            code=table_code,
            name=table_name or "",
            comment=table_comment or "",
            columns=columns,
        )
        return TableDetailResponse(success=True, message="获取成功", data=detail)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_table_schema error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 语义搜索表
# ---------------------------------------------------------------

@router.post(
    "/search",
    response_model=SearchTablesResponse,
    summary="语义搜索表",
    description="基于向量语义相似度搜索相关数据表，支持中英文自然语言查询。",
)
def search_tables(body: SearchTablesRequest):
    try:
        embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()
        client = PersistentClient(path=settings.CHROMA_DB_PATH)
        collection = client.get_collection(
            name="pdm_metadata", embedding_function=embedding_fn
        )

        results = collection.query(
            query_texts=[body.query],
            n_results=body.n_results,
            where={"type": "table"},
        )

        search_results = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                search_results.append(
                    SearchResult(
                        code=meta.get("code", ""),
                        name=meta.get("name", ""),
                        document=doc,
                        score=round(1 - dist, 4),  # 转为相似度得分
                    )
                )

        return SearchTablesResponse(
            success=True,
            message="搜索成功",
            data=search_results,
            query=body.query,
        )
    except Exception as e:
        logger.error(f"search_tables error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 查询表关系
# ---------------------------------------------------------------

@router.get(
    "/relationships/{table_code}",
    response_model=RelationshipsResponse,
    summary="查询表关联关系",
    description="根据表的 CODE 查询其所有外键关联关系（父表和子表）。",
)
def get_relationships(table_code: str):
    try:
        conn = _get_sqlite_conn()
        cursor = conn.cursor()

        # 获取表 ID
        cursor.execute("SELECT id FROM tables WHERE code = ?", (table_code,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(
                status_code=404,
                detail=f"表 '{table_code}' 不存在",
            )

        table_id = row[0]

        cursor.execute(
            """
            SELECT r.name, pt.code AS parent, ct.code AS child
            FROM references_rels r
            JOIN tables pt ON r.parent_table_id = pt.id
            JOIN tables ct ON r.child_table_id = ct.id
            WHERE r.parent_table_id = ? OR r.child_table_id = ?
            """,
            (table_id, table_id),
        )
        rels = cursor.fetchall()
        conn.close()

        relationships = [
            RelationshipInfo(
                name=r[0] or "",
                parent_table=r[1] or "",
                child_table=r[2] or "",
                direction="Parent" if r[1] == table_code else "Child",
            )
            for r in rels
        ]

        return RelationshipsResponse(
            success=True,
            message="查询成功",
            data=relationships,
            table_code=table_code,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_relationships error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 执行 SQL 查询
# ---------------------------------------------------------------

@router.post(
    "/sql/execute",
    response_model=ExecuteSQLResponse,
    summary="执行 SQL 查询",
    description="在指定数据库（MySQL 或 Oracle）上执行 SQL 查询，返回结果集。",
)
def execute_sql(body: ExecuteSQLRequest):
    try:
        result = db_manager.execute_query(body.db_type, body.sql)

        if isinstance(result, str) and result.startswith("Error"):
            raise HTTPException(status_code=400, detail=result)

        if isinstance(result, list):
            return ExecuteSQLResponse(
                success=True,
                message="执行成功",
                data=result,
                db_type=body.db_type,
                row_count=len(result),
            )
        else:
            return ExecuteSQLResponse(
                success=True,
                message=str(result),
                data=None,
                db_type=body.db_type,
                row_count=0,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"execute_sql error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 索引状态
# ---------------------------------------------------------------

@router.get(
    "/indexer/status",
    response_model=IndexStatusResponse,
    summary="查询索引状态",
    description="返回当前已索引的 PDM 文件列表及表、字段的统计数量。",
)
def get_index_status():
    try:
        conn = _get_sqlite_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT file_name FROM pdm_files ORDER BY last_indexed DESC")
        files = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT COUNT(*) FROM tables")
        total_tables = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM columns")
        total_columns = cursor.fetchone()[0]

        conn.close()

        return IndexStatusResponse(
            success=True,
            message="查询成功",
            indexed_files=files,
            total_tables=total_tables,
            total_columns=total_columns,
        )
    except Exception as e:
        logger.error(f"get_index_status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# 重建索引
# ---------------------------------------------------------------

@router.post(
    "/indexer/reindex",
    response_model=ReindexResponse,
    summary="重建索引",
    description="扫描 files/ 目录下所有 PDM 文件并重新索引，更新 SQLite 和向量库。",
)
def reindex(background_tasks: BackgroundTasks):
    try:
        from backend.core.indexer import PDMIndexer

        pdm_dir = settings.PDM_FILES_DIR
        if not os.path.exists(pdm_dir):
            raise HTTPException(
                status_code=404,
                detail=f"PDM 文件目录不存在: {pdm_dir}",
            )

        pdm_files = [f for f in os.listdir(pdm_dir) if f.endswith(".pdm")]
        if not pdm_files:
            return ReindexResponse(
                success=True,
                message="PDM 目录中暂无 .pdm 文件",
                indexed_count=0,
            )

        def _do_reindex():
            indexer = PDMIndexer()
            indexer.index_all()

        background_tasks.add_task(_do_reindex)

        return ReindexResponse(
            success=True,
            message=f"已在后台启动索引任务，共 {len(pdm_files)} 个文件待处理",
            indexed_count=len(pdm_files),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
