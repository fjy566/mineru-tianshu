# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
import random
import re
from types import SimpleNamespace

from mineru_pipeline.ocr_geometry import _deduplicate_lines, _overlap_ratio
from mineru_pipeline import ocr_gap_filler


def reference_deduplicate(lines):
    kept = []
    for line in sorted(lines, key=lambda item: item["score"], reverse=True):
        if any(
            re.sub(r"\s+", "", line["text"]).casefold() == re.sub(r"\s+", "", old["text"]).casefold()
            and min(_overlap_ratio(line["bbox"], old["bbox"]), _overlap_ratio(old["bbox"], line["bbox"])) >= 0.5
            for old in kept
        ):
            continue
        kept.append(line)
    return kept


def test_bucketed_deduplication_matches_reference_on_unicode_geometry_and_tied_scores():
    randomizer = random.Random(1016)
    texts = ["a+b", "a-b", "姓名", "A B", "ab", "AB", "重复标题", "ＳＳ", "ß", "ss", "\t "]
    for _ in range(100):
        lines = []
        for _ in range(randomizer.randrange(1, 80)):
            x, y = randomizer.randrange(6) / 10, randomizer.randrange(6) / 10
            lines.append(
                {
                    "text": randomizer.choice(texts),
                    "score": randomizer.choice([0.55, 0.8, 0.95]),
                    "bbox": (x, y, x + 0.3, y + 0.1),
                }
            )
        assert _deduplicate_lines(lines) == reference_deduplicate(lines)


def test_precomputed_candidates_preserve_ocr_and_image_selection(monkeypatch):
    result = SimpleNamespace(boxes=[[[10, 10], [90, 10], [90, 20], [10, 20]]], txts=["完整文字"], scores=[0.95])
    boxes = [(0, 0, 1, 1)]
    expected_lines = ocr_gap_filler._normalized_ocr_lines(result, 100, 100, [], [])
    expected_images = ocr_gap_filler._image_text_candidates(result, 100, 100, boxes)
    candidates = ocr_gap_filler._line_bboxes(result, 100, 100)
    monkeypatch.setattr(
        ocr_gap_filler, "_line_bboxes", lambda *_: (_ for _ in ()).throw(AssertionError("duplicate conversion"))
    )
    assert ocr_gap_filler._normalized_ocr_lines(result, 100, 100, [], [], candidates=candidates) == expected_lines
    assert ocr_gap_filler._image_text_candidates(result, 100, 100, boxes, candidates=candidates) == expected_images


def test_empty_precomputed_candidates_do_not_fall_back_to_duplicate_work(monkeypatch):
    monkeypatch.setattr(
        ocr_gap_filler, "_line_bboxes", lambda *_: (_ for _ in ()).throw(AssertionError("duplicate conversion"))
    )
    assert ocr_gap_filler._normalized_ocr_lines(None, 100, 100, [], [], candidates=[]) == []
    assert ocr_gap_filler._image_text_candidates(None, 100, 100, [], candidates=[]) == []
