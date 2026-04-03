"""
backend/core/ocr_service.py

OCR 图片文字识别服务。
使用 RapidOCR 对用户上传的图片进行文字提取，将识别结果作为纯文本拼接到消息中。
"""

import base64
import io
import logging
from typing import List, Optional

from PIL import Image

logger = logging.getLogger(__name__)

# 支持的图片 MIME 类型
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpg",
    "image/jpeg",
    "image/gif",
    "image/bmp",
    "image/webp",
}

# 单张图片最大 5MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024

# 单条消息最多 5 张图片
MAX_IMAGES_PER_MESSAGE = 5

# 懒加载 RapidOCR 引擎（单例）
_ocr_engine = None


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
        logger.info("RapidOCR 引擎已初始化")
    return _ocr_engine


def validate_image(data: str, mime_type: str) -> Optional[str]:
    """
    校验图片数据。

    Returns:
        None 如果通过校验，否则返回错误信息字符串。
    """
    if mime_type not in ALLOWED_MIME_TYPES:
        return f"不支持的图片格式: {mime_type}，支持: PNG, JPG, GIF, BMP, WEBP"

    try:
        raw = base64.b64decode(data)
    except Exception:
        return "无效的 base64 图片数据"

    if len(raw) > MAX_IMAGE_SIZE:
        size_mb = len(raw) / (1024 * 1024)
        return f"图片大小 {size_mb:.1f}MB 超过限制 (最大 5MB)"

    return None


def extract_text_from_base64(data: str, filename: str = "") -> str:
    """
    从 base64 编码的图片中提取文字。

    Args:
        data: base64 编码的图片数据（不含 data:image/... 前缀）
        filename: 文件名（用于日志）

    Returns:
        识别出的文字，如果识别失败则返回错误提示。
    """
    try:
        raw = base64.b64decode(data)
        image = Image.open(io.BytesIO(raw))

        # RapidOCR 接受 numpy array
        import numpy as np
        img_array = np.array(image.convert("RGB"))

        engine = _get_ocr_engine()
        result, _ = engine(img_array)

        if not result:
            return "[未识别到文字内容]"

        # result 格式: [[box, text, score], ...]
        lines = [item[1] for item in result]
        text = "\n".join(lines)
        logger.info(f"OCR 识别完成 [{filename}]: {len(lines)} 行文字")
        return text

    except Exception as e:
        logger.error(f"OCR 识别失败 [{filename}]: {e}", exc_info=True)
        return f"[图片识别失败: {e}]"


def process_images(images: List[dict]) -> str:
    """
    处理多张图片，返回拼接的 OCR 识别文字。

    Args:
        images: 图片列表，每项包含 {data, filename, mime_type}

    Returns:
        拼接后的 OCR 文字。如果全部失败则返回相应提示。
    """
    if not images:
        return ""

    if len(images) > MAX_IMAGES_PER_MESSAGE:
        images = images[:MAX_IMAGES_PER_MESSAGE]
        logger.warning(f"图片数量超过限制，仅处理前 {MAX_IMAGES_PER_MESSAGE} 张")

    results = []
    for i, img in enumerate(images):
        # 校验
        error = validate_image(img.get("data", ""), img.get("mime_type", ""))
        if error:
            results.append(f"图片{i + 1} ({img.get('filename', '未知')}): {error}")
            continue

        # OCR 识别
        text = extract_text_from_base64(
            img["data"],
            filename=img.get("filename", f"image_{i + 1}"),
        )
        if len(images) > 1:
            results.append(f"--- 图片{i + 1} ({img.get('filename', '')}) ---\n{text}")
        else:
            results.append(text)

    return "\n\n".join(results)
