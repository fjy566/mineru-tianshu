"""补录 MinerU PDF 解析结果中未被任何版面块覆盖的 OCR 文字。"""

from __future__ import annotations

import os
import math
import copy
import re
import threading
from pathlib import Path
from typing import Any

from loguru import logger


_ENGINE: Any | None = None
_ENGINE_LOCK = threading.Lock()
_MIN_TEXT_SCORE = 0.55
_MAX_COVERED_LINE_RATIO = 0.45
_HIGH_RES_MIN_TEXT_SCORE = 0.80


def _enabled() -> bool:
    return os.getenv("TIANSHU_OCR_BACKFILL_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _get_engine():
    global _ENGINE
    if _ENGINE is None:
        with _ENGINE_LOCK:
            if _ENGINE is None:
                from rapidocr import RapidOCR

                # Higher page renders are used only for text candidates that
                # overlap an image block. Allow them through without downscaling.
                _ENGINE = RapidOCR(params={"Global.max_side_len": 4000})
    return _ENGINE


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


def _overlap_ratio(
    bbox: tuple[float, float, float, float], other: tuple[float, float, float, float]
) -> float:
    x0, y0, x1, y1 = bbox
    area = (x1 - x0) * (y1 - y0)
    if area <= 0:
        return 0.0
    ox0, oy0, ox1, oy1 = other
    intersection = max(0.0, min(x1, ox1) - max(x0, ox0)) * max(
        0.0, min(y1, oy1) - max(y0, oy0)
    )
    return intersection / area


def _existing_texts(blocks: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "content" and isinstance(child, str):
                    texts.append(child)
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(blocks)
    return texts


def _normalized_ocr_lines(
    result: Any,
    width: int,
    height: int,
    covered: list[tuple[float, float, float, float]],
    existing_texts: list[str],
    allowed_overlaps: list[tuple[float, float, float, float]] | None = None,
    minimum_score: float = _MIN_TEXT_SCORE,
):
    lines = []
    for candidate in _line_bboxes(result, width, height):
        bbox = candidate["bbox"]
        if candidate["score"] < minimum_score:
            continue
        overlaps_candidate = any(
            _overlap_ratio(bbox, other) >= 0.25 for other in (allowed_overlaps or [])
        )
        if (
            _covered_ratio(bbox, covered) >= _MAX_COVERED_LINE_RATIO
            and not overlaps_candidate
        ):
            continue
        lines.append(candidate)
    return lines


def _image_text_candidates(
    result: Any,
    width: int,
    height: int,
    image_boxes: list[tuple[float, float, float, float]],
) -> list[tuple[float, float, float, float]]:
    candidates = []
    for item in _line_bboxes(result, width, height):
        bbox = item["bbox"]
        normalized = _normalized_text(item["text"])
        if (
            item["score"] >= _MIN_TEXT_SCORE
            and len(normalized) >= 2
            and any(_covered_ratio(bbox, [image_box]) >= _MAX_COVERED_LINE_RATIO for image_box in image_boxes)
        ):
            candidates.append(bbox)
    return candidates


def _group_lines_into_rows(lines: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Join OCR cells on the same visual row while retaining reading order."""
    rows: list[list[dict[str, Any]]] = []
    for line in sorted(lines, key=lambda item: ((item["bbox"][1] + item["bbox"][3]) / 2, item["bbox"][0])):
        center_y = (line["bbox"][1] + line["bbox"][3]) / 2
        if rows:
            row_center = sum((item["bbox"][1] + item["bbox"][3]) / 2 for item in rows[-1]) / len(rows[-1])
            if abs(center_y - row_center) <= 0.35 * min(
                line["bbox"][3] - line["bbox"][1],
                min(item["bbox"][3] - item["bbox"][1] for item in rows[-1]),
            ):
                rows[-1].append(line)
                continue
        rows.append([line])
    return rows


def _make_text_block(row: list[dict[str, Any]]) -> dict[str, Any]:
    row.sort(key=lambda item: item["bbox"][0])
    x0 = min(item["bbox"][0] for item in row)
    y0 = min(item["bbox"][1] for item in row)
    x1 = max(item["bbox"][2] for item in row)
    y1 = max(item["bbox"][3] for item in row)
    text = " | ".join(item["text"] for item in row)
    return {
        "type": "text",
        "bbox": [round(x0, 5), round(y0, 5), round(x1, 5), round(y1, 5)],
        "content": [{"type": "text", "content": text}],
    }


def _extract_image_footnotes(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Move page text misclassified as an image footnote into the page text flow."""
    extracted: list[dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "image":
            continue
        content = block.get("content")
        if not isinstance(content, list):
            continue
        retained = []
        for child in content:
            if isinstance(child, dict) and child.get("type") == "image_footnote":
                bbox = _valid_bbox(child.get("bbox"))
                child_content = child.get("content")
                if bbox and isinstance(child_content, list) and child_content:
                    extracted.append({"type": "text", "bbox": list(bbox), "content": child_content})
                    continue
            retained.append(child)
        block["content"] = retained
    return extracted


def _collect_indices(value: Any) -> set[int]:
    indices: set[int] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            index = item.get("index")
            if isinstance(index, int):
                indices.add(index)
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return indices


def _shift_indices(value: Any, threshold: int, amount: int) -> None:
    if isinstance(value, dict):
        index = value.get("index")
        if isinstance(index, int) and index >= threshold:
            value["index"] = index + amount
        for child in value.values():
            _shift_indices(child, threshold, amount)
    elif isinstance(value, list):
        for child in value:
            _shift_indices(child, threshold, amount)


def _insert_by_page_position(blocks: list[dict[str, Any]], new_blocks: list[dict[str, Any]]) -> None:
    for new_block in sorted(new_blocks, key=lambda item: (item["bbox"][1], item["bbox"][0])):
        new_y = new_block["bbox"][1]
        insert_at = len(blocks)
        for index, block in enumerate(blocks):
            bbox = _valid_bbox(block.get("bbox")) if isinstance(block, dict) else None
            if bbox and bbox[1] > new_y:
                insert_at = index
                break
        previous_index = int(blocks[insert_at - 1].get("index", insert_at - 1)) if insert_at else -1
        occupied_before = _collect_indices(blocks[:insert_at])
        new_index = previous_index + 1
        while new_index in occupied_before:
            new_index += 1
        if insert_at < len(blocks):
            next_index = int(blocks[insert_at].get("index", insert_at))
            if new_index >= next_index:
                shift = new_index - next_index + 1
                for following in blocks[insert_at:]:
                    _shift_indices(following, next_index, shift)
        new_block["index"] = new_index
        blocks.insert(insert_at, new_block)


def _deduplicate_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """仅合并同一位置的同文候选，保留其他位置的重复标题。"""
    kept = []
    for line in sorted(lines, key=lambda item: item["score"], reverse=True):
        if any(
            re.sub(r"\s+", "", line["text"]).casefold() == re.sub(r"\s+", "", old["text"]).casefold()
            and min(_overlap_ratio(line["bbox"], old["bbox"]),
                    _overlap_ratio(old["bbox"], line["bbox"])) >= 0.5
            for old in kept
        ):
            continue
        kept.append(line)
    return kept


def _render_page(page, scale):
    """限制单页栅格尺寸，防止工程图等超大页面耗尽内存。"""
    import pymupdf as fitz
    width, height = page.rect.width, page.rect.height
    if width <= 0 or height <= 0:
        raise ValueError("PDF 页面尺寸无效")
    scale = min(scale, 4000 / max(width, height), math.sqrt(12_000_000 / (width * height)))
    return page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)


def _text_coverage(blocks):
    """图片本身不表示其文字已提取；图片标题和脚注仍属于已有文字。"""
    boxes = []
    def visit(value):
        if isinstance(value, dict):
            bbox = _valid_bbox(value.get("bbox"))
            if bbox and value.get("type") not in {"image", "image_body"}:
                boxes.append(bbox)
            for key, child in value.items():
                if key != "bbox":
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(blocks)
    return boxes


def supplement_uncovered_pdf_text(pdf_path: Path, middle_data: dict[str, Any]) -> dict[str, Any]:
    """逐页补漏；失败保留原解析，并在所有输出的审计记录中明确标记。"""
    audit = {"enabled": _enabled(), "engine": "RapidOCR", "pages": [], "added_rows": 0,
             "page_results": [], "status": "disabled"}
    middle_data.setdefault("extensions", {})["tian_shu_ocr_backfill"] = audit
    if not audit["enabled"]:
        return audit
    document = None
    try:
        import pymupdf as fitz
        import numpy as np
        document = fitz.open(str(pdf_path))
        engine = _get_engine()
        audit["status"] = "completed"
        for original in middle_data.get("pages", []):
            record = {"page_idx": original.get("page_idx") if isinstance(original, dict) else None,
                      "status": "failed", "added_rows": 0}
            audit["page_results"].append(record)
            try:
                # 在副本上工作，失败时不留下部分修改。
                page_data = copy.deepcopy(original)
                page_idx = int(page_data["page_idx"])
                if not 0 <= page_idx < len(document):
                    raise ValueError("PDF 页码超出源文件范围")
                blocks = page_data.setdefault("blocks", [])
                if not isinstance(blocks, list):
                    raise ValueError("页面块格式无效")
                page = document[page_idx]
                pixmap = _render_page(page, 2.2)
                image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
                with _ENGINE_LOCK:
                    result = engine(image)
                covered = _covered_bboxes(blocks)
                text_covered = _text_coverage(blocks)
                image_boxes = [bbox for block in blocks if isinstance(block, dict)
                               and block.get("type") == "image"
                               and (bbox := _valid_bbox(block.get("bbox"))) is not None]
                lines = _normalized_ocr_lines(result, pixmap.width, pixmap.height, covered, [])
                image_candidates = [bbox for bbox in _image_text_candidates(
                    result, pixmap.width, pixmap.height, image_boxes
                ) if _covered_ratio(bbox, text_covered) < _MAX_COVERED_LINE_RATIO]
                if image_candidates:
                    try:
                        high_pixmap = _render_page(page, 3.5)
                        high_image = np.frombuffer(high_pixmap.samples, dtype=np.uint8).reshape(
                            high_pixmap.height, high_pixmap.width, 3)
                        with _ENGINE_LOCK:
                            high_result = engine(high_image)
                        high_lines = _normalized_ocr_lines(
                            high_result, high_pixmap.width, high_pixmap.height, text_covered, [],
                            minimum_score=_HIGH_RES_MIN_TEXT_SCORE)
                        # 复识别只补图片候选区域，避免再次加入普通分辨率的页外文字。
                        lines.extend(line for line in high_lines if any(
                            _overlap_ratio(line["bbox"], bbox) >= 0.5 for bbox in image_candidates))
                    except Exception as exc:
                        record["warning"] = "high_resolution_failed: " + type(exc).__name__
                        audit["status"] = "partial"
                        logger.warning(f"第 {page_idx + 1} 页高分辨率补录失败：{exc}")
                lines = _deduplicate_lines(lines)
                ocr_blocks = [_make_text_block(row) for row in _group_lines_into_rows(lines)]
                _insert_by_page_position(blocks, ocr_blocks)
                original.update(page_data)
                record.update(status="completed", added_rows=len(ocr_blocks),
                              lines=[{"text": line["text"], "bbox": list(line["bbox"]),
                                      "score": line["score"]} for line in lines])
                if ocr_blocks:
                    audit["pages"].append(page_idx + 1)
                    audit["added_rows"] += len(ocr_blocks)
                logger.info(f"第 {page_idx + 1} 页 OCR 检查完成，补录 {len(ocr_blocks)} 行")
            except Exception as exc:
                record["error"] = type(exc).__name__
                audit["status"] = "partial"
                logger.warning(f"第 {record['page_idx']} 页补录失败，保留原结果：{exc}")
    except Exception as exc:
        audit.update(status="failed", error=type(exc).__name__)
        logger.warning(f"本机 OCR 补录不可用，保留 MinerU 原结果：{exc}")
    finally:
        if document is not None:
            document.close()
    return audit
