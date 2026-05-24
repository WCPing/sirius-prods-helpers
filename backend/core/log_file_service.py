"""
backend/core/log_file_service.py

日志/文本文件解析服务。
将用户上传的 .log / .txt 文件内容提取为纯文本，并在必要时截断后拼接到消息中。
"""

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".log", ".txt"}
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_LINES = 2000
MAX_CHARS = 200_000


def validate_log_file(data: str, filename: str) -> Optional[str]:
    """
    校验日志文件数据。

    Returns:
        None 如果通过校验，否则返回错误信息字符串。
    """
    ext = os.path.splitext((filename or "").lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        return f"不支持的日志文件格式: {filename or '[未命名文件]'}，仅支持 .log 和 .txt"

    try:
        raw = base64.b64decode(data)
    except Exception:
        return "无效的 base64 文件数据"

    if len(raw) > MAX_FILE_SIZE:
        size_mb = len(raw) / (1024 * 1024)
        return f"日志文件大小 {size_mb:.1f}MB 超过限制 (最大 5MB)"

    return None


def extract_text_from_base64(data: str, filename: str = "") -> str:
    """
    从 base64 编码的日志/文本文件中提取文字。

    Args:
        data: base64 编码的文件数据
        filename: 文件名（用于日志）

    Returns:
        提取出的文本，如果失败则返回错误提示。
    """
    try:
        raw = base64.b64decode(data)
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()

        if len(lines) > MAX_LINES:
            omitted = len(lines) - MAX_LINES
            lines = lines[-MAX_LINES:]
            text = f"[...已省略前 {omitted} 行，仅保留尾部 {MAX_LINES} 行...]\n" + "\n".join(lines)
            logger.info(f"日志文件已截断 [{filename}]: 仅保留最后 {MAX_LINES} 行")
        else:
            text = "\n".join(lines) if lines else text

        if len(text) > MAX_CHARS:
            omitted_chars = len(text) - MAX_CHARS
            text = f"[...已省略前 {omitted_chars} 个字符，仅保留尾部 {MAX_CHARS} 个字符...]\n" + text[-MAX_CHARS:]
            logger.info(f"日志文件字符数过长 [{filename}]: 仅保留最后 {MAX_CHARS} 个字符")

        logger.info(f"日志文件解析完成 [{filename}]: {len(text)} 字符")
        return text or "[日志文件为空]"

    except Exception as e:
        logger.error(f"日志文件解析失败 [{filename}]: {e}", exc_info=True)
        return f"[日志文件解析失败: {e}]"


def process_log_file(log_file: dict) -> str:
    """
    处理日志文件，返回可拼接的纯文本。

    Args:
        log_file: 日志文件数据，包含 {data, filename, mime_type}

    Returns:
        解析后的文本内容。
    """
    if not log_file:
        return ""

    error = validate_log_file(log_file.get("data", ""), log_file.get("filename", ""))
    if error:
        return error

    return extract_text_from_base64(
        log_file.get("data", ""),
        filename=log_file.get("filename", "log.txt"),
    )
