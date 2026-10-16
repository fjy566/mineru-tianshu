# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
"""不依赖模型与文件系统的 OCR 坐标、文本候选和去重算法。"""

import math
import re
from typing import Any


def _valid_bbox(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x0, y0, x1, y1 = (float(part) for part in value)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def _covered_bboxes(blocks: list[dict[str, Any]]) -> list[tuple[float, float, float, float]]:
    """Collect all block and nested caption/footnote boxes in normalized page units."""
    boxes: list[tuple[float, float, float, float]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            bbox = _valid_bbox(value.get("bbox"))
            if bbox:
                boxes.append(bbox)
            for key, child in value.items():
                if key != "bbox":
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(blocks)
    return boxes


def _covered_ratio(bbox: tuple[float, float, float, float], covered: list[tuple[float, float, float, float]]) -> float:
    x0, y0, x1, y1 = bbox
    area = (x1 - x0) * (y1 - y0)
    if area <= 0:
        return 1.0
    max_intersection = 0.0
    for bx0, by0, bx1, by1 in covered:
        width = max(0.0, min(x1, bx1) - max(x0, bx0))
        height = max(0.0, min(y1, by1) - max(y0, by0))
        max_intersection = max(max_intersection, width * height)
    return max_intersection / area


def _normalized_text(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).lower()


def _clean_ocr_text(text: str) -> str:
    """仅清理新增 OCR 行的首尾空白，不猜测或改写原文。"""
    return text.strip()


def _line_bboxes(result: Any, width: int, height: int) -> list[dict[str, Any]]:
    """Return valid OCR candidates with normalized geometry and confidence."""
    boxes = getattr(result, "boxes", None)
    texts = getattr(result, "txts", None)
    scores = getattr(result, "scores", None)
    if boxes is None or texts is None or scores is None:
        return []

    candidates = []
    for polygon, text, score in zip(boxes, texts, scores):
        text = _clean_ocr_text(str(text))
        if not text:
            continue
        try:
            score = float(score)
            points = [(float(point[0]), float(point[1])) for point in polygon]
        except (TypeError, ValueError, IndexError):
            continue
        if not points or not math.isfinite(score) or not all(math.isfinite(v) for point in points for v in point):
            continue
        bbox = (
            max(0.0, min(x for x, _ in points) / width),
            max(0.0, min(y for _, y in points) / height),
            min(1.0, max(x for x, _ in points) / width),
            min(1.0, max(y for _, y in points) / height),
        )
        if _valid_bbox(bbox) is None:
            continue
        candidates.append({"text": text, "bbox": bbox, "score": score})
    return candidates


def _overlap_ratio(bbox: tuple[float, float, float, float], other: tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = bbox
    area = (x1 - x0) * (y1 - y0)
    if area <= 0:
        return 0.0
    ox0, oy0, ox1, oy1 = other
    intersection = max(0.0, min(x1, ox1) - max(x0, ox0)) * max(0.0, min(y1, oy1) - max(y0, oy0))
    return intersection / area


def _deduplicate_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """仅合并同一位置的同文候选，保留其他位置的重复标题。"""
    kept = []
    by_text: dict[str, list[dict[str, Any]]] = {}
    for line in sorted(lines, key=lambda item: item["score"], reverse=True):
        key = re.sub(r"\s+", "", line["text"]).casefold()
        same_text = by_text.setdefault(key, [])
        if any(
            min(_overlap_ratio(line["bbox"], old["bbox"]), _overlap_ratio(old["bbox"], line["bbox"])) >= 0.5
            for old in same_text
        ):
            continue
        kept.append(line)
        same_text.append(line)
    return kept
