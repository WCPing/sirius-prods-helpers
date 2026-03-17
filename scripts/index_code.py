"""
scripts/index_code.py

手动执行代码索引脚本。

用法：
    # 激活虚拟环境后，在项目根目录执行
    python scripts/index_code.py

    # 指定自定义路径（覆盖 .env 中的 LOCAL_CODE_DIR）
    python scripts/index_code.py --path /your/java/project/path

    # 重建索引（清除旧数据后全量重建）
    python scripts/index_code.py --reindex

    # 查看已注册的知识源
    python scripts/index_code.py --list
"""

import os
import sys
import argparse
import time

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="代码知识源索引工具")
    parser.add_argument("--path", help="Java 项目路径（默认读取 .env 中的 LOCAL_CODE_DIR）")
    parser.add_argument("--name", default="pc90-product", help="知识源名称（默认: pc90-product）")
    parser.add_argument("--reindex", action="store_true", help="清除旧数据后全量重建")
    parser.add_argument("--list", action="store_true", help="列出所有已注册的知识源")
    args = parser.parse_args()

    from backend.core.source_manager import source_manager
    from backend.core.unified_indexer import unified_indexer

    # --list: 列出知识源
    if args.list:
        sources = source_manager.list_sources()
        if not sources:
            print("暂无已注册的知识源。")
            return
        print(f"{'ID':<38} {'名称':<20} {'类型':<8} {'状态':<10} {'路径'}")
        print("-" * 120)
        for s in sources:
            print(f"{s['id']:<38} {s['name']:<20} {s['source_type']:<8} {s['status']:<10} {s['location']}")
        return

    # 确定路径
    code_dir = args.path or os.getenv("LOCAL_CODE_DIR", "")
    if not code_dir:
        print("错误：请通过 --path 参数或 .env 中的 LOCAL_CODE_DIR 指定 Java 项目路径")
        sys.exit(1)

    if not os.path.isdir(code_dir):
        print(f"错误：路径不存在 → {code_dir}")
        sys.exit(1)

    print(f"项目路径: {code_dir}")
    print(f"知识源名称: {args.name}")

    # 检查是否已注册
    existing_sources = source_manager.list_sources()
    source_id = None
    for s in existing_sources:
        if s["location"] == code_dir and s["source_type"] == "local":
            source_id = s["id"]
            print(f"发现已注册的知识源: {source_id}")
            break

    # 未注册则新注册
    if not source_id:
        source_id = source_manager.register_source(
            name=args.name,
            source_type="local",
            location=code_dir,
        )
        print(f"已注册新知识源: {source_id}")

    # 执行索引
    start = time.time()
    if args.reindex:
        print("正在清除旧数据并全量重建索引...")
        unified_indexer.reindex_source(source_id)
    else:
        print("正在执行增量索引（仅处理变化的文件）...")
        unified_indexer.index_source(source_id)

    elapsed = time.time() - start
    print(f"\n索引完成！耗时: {elapsed:.1f} 秒")

    # 输出统计
    import sqlite3
    from backend.config import settings
    conn = sqlite3.connect(settings.SQLITE_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM code_chunks WHERE source_id = ?", (source_id,))
    chunk_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cross_references WHERE source_id = ?", (source_id,))
    ref_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM indexed_files WHERE source_id = ?", (source_id,))
    file_count = cursor.fetchone()[0]

    conn.close()

    print(f"索引文件数: {file_count}")
    print(f"代码片段数: {chunk_count}")
    print(f"跨层引用数: {ref_count}")


if __name__ == "__main__":
    main()
