# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
import unittest

from mineru_pipeline.ocr_gap_filler import (
    _covered_bboxes,
    _covered_ratio,
    _extract_image_footnotes,
    _insert_by_page_position,
    _normalized_ocr_lines,
    _clean_ocr_text,
    _deduplicate_lines,
    _valid_bbox,
    _image_text_candidates,
    _render_page,
    supplement_uncovered_pdf_text,
)


class OcrGapFillerTests(unittest.TestCase):
    def test_ocr_does_not_guess_domain_specific_words_or_units(self):
        text = "滤皮 10mmmV 100HzHZ 2023/8/1618:55:05"
        self.assertEqual(_clean_ocr_text(text), text)

    def test_deduplication_does_not_merge_different_math_symbols(self):
        lines = [{"text": text, "bbox": (0, 0, 0.3, 0.1), "score": 0.9} for text in ("a+b", "a-b")]
        self.assertEqual(len(_deduplicate_lines(lines)), 2)

    def test_engine_failure_is_audited_and_document_closed(self):
        from unittest.mock import patch, Mock

        doc = Mock()
        with (
            patch("pymupdf.open", return_value=doc),
            patch("mineru_pipeline.ocr_gap_filler._get_engine", side_effect=ImportError("missing")),
        ):
            data = {"pages": []}
            audit = supplement_uncovered_pdf_text("unused.pdf", data)
        self.assertEqual(audit["status"], "failed")
        self.assertEqual(data["extensions"]["tian_shu_ocr_backfill"]["error"], "ImportError")
        doc.close.assert_called_once()

    def test_nonfinite_boxes_are_rejected(self):
        self.assertIsNone(_valid_bbox([0, 0, float("nan"), 1]))
        self.assertIsNone(_valid_bbox([0, 0, float("inf"), 1]))

    def test_deduplication_preserves_repeated_text_at_other_positions(self):
        lines = [
            {"text": "heading", "bbox": (0, 0, 0.3, 0.1), "score": 0.8},
            {"text": "heading", "bbox": (0, 0, 0.3, 0.1), "score": 0.9},
            {"text": "heading", "bbox": (0, 0.5, 0.3, 0.6), "score": 0.9},
        ]
        self.assertEqual(len(_deduplicate_lines(lines)), 2)

    def test_image_candidates_do_not_require_digits(self):
        class Result:
            boxes = [[[10, 10], [90, 10], [90, 20], [10, 20]]]
            txts = ["普通图片文字"]
            scores = [0.95]

        self.assertEqual(len(_image_text_candidates(Result(), 100, 100, [(0, 0, 1, 1)])), 1)

    def test_large_page_render_is_bounded(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        page = Mock(rect=SimpleNamespace(width=100000, height=100000))
        _render_page(page, 3.5)
        matrix = page.get_pixmap.call_args.kwargs["matrix"]
        self.assertLessEqual((100000 * matrix.a) ** 2, 12000001)

    def test_page_failure_preserves_original_and_continues(self):
        import tempfile
        import pymupdf
        from pathlib import Path
        from unittest.mock import patch, Mock
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "test.pdf"
            with pymupdf.open() as doc:
                doc.new_page()
                doc.new_page()
                doc.save(source)
            original = "def x():\n    return 1  # 滤皮"
            data = {
                "pages": [
                    {"page_idx": 0, "blocks": [{"type": "text", "content": original}]},
                    {"page_idx": 1, "blocks": []},
                ]
            }
            engine = Mock(side_effect=[RuntimeError("injected failure"), SimpleNamespace(boxes=[], txts=[], scores=[])])
            with patch("mineru_pipeline.ocr_gap_filler._get_engine", return_value=engine):
                audit = supplement_uncovered_pdf_text(source, data)
            self.assertEqual(audit["status"], "partial")
            self.assertEqual(audit["page_results"][1]["status"], "completed")
            self.assertEqual(data["pages"][0]["blocks"][0]["content"], original)

    def test_image_text_candidate_is_kept_only_after_spatially_matched_refinement(self):
        class Result:
            boxes = [
                [[50, 20], [90, 20], [90, 24], [50, 24]],
            ]
            txts = ["纸速25mm/s灵敏度:10mmmV滤皮100HzHZ"]
            scores = [0.95]

        covered = [(0.4, 0.1, 0.95, 0.5)]
        candidate_box = (0.5, 0.2, 0.9, 0.24)

        self.assertEqual(_normalized_ocr_lines(Result(), 100, 100, covered, []), [])
        refined = _normalized_ocr_lines(
            Result(), 100, 100, covered, [], allowed_overlaps=[candidate_box], minimum_score=0.8
        )

        self.assertEqual(len(refined), 1)
        self.assertEqual(refined[0]["text"], "纸速25mm/s灵敏度:10mmmV滤皮100HzHZ")

    def test_nested_footnotes_count_as_existing_page_content(self):
        blocks = [
            {
                "type": "image",
                "bbox": [0.2, 0.2, 0.7, 0.4],
                "footnotes": [{"bbox": [0.2, 0.5, 0.8, 0.55], "content": "already parsed"}],
            }
        ]

        covered = _covered_bboxes(blocks)

        self.assertEqual(len(covered), 2)
        self.assertGreaterEqual(_covered_ratio((0.3, 0.51, 0.6, 0.54), covered), 0.45)

    def test_image_footnotes_can_be_reflowed_as_page_text(self):
        blocks = [
            {
                "index": 2,
                "type": "image",
                "bbox": [0.2, 0.2, 0.7, 0.4],
                "content": [
                    {"type": "image_body", "index": 2},
                    {
                        "type": "image_footnote",
                        "index": 3,
                        "bbox": [0.2, 0.5, 0.6, 0.55],
                        "content": [{"type": "text", "content": "page text"}],
                    },
                ],
            }
        ]

        extracted = _extract_image_footnotes(blocks)

        self.assertEqual(extracted[0]["type"], "text")
        self.assertEqual(extracted[0]["content"][0]["content"], "page text")
        self.assertEqual([item["type"] for item in blocks[0]["content"]], ["image_body"])

    def test_inserted_blocks_keep_unique_increasing_indices(self):
        blocks = [
            {"index": 0, "type": "text", "bbox": [0.1, 0.1, 0.5, 0.2]},
            {"index": 1, "type": "text", "bbox": [0.1, 0.5, 0.5, 0.6]},
        ]
        additions = [
            {"type": "text", "bbox": [0.1, 0.3, 0.5, 0.35], "content": [{"type": "text", "content": "middle"}]}
        ]

        _insert_by_page_position(blocks, additions)

        self.assertEqual([block["index"] for block in blocks], [0, 1, 2])
        self.assertEqual(blocks[1]["content"][0]["content"], "middle")

    def test_insertions_skip_nested_footnote_indices_and_shift_later_blocks(self):
        blocks = [
            {"index": index, "type": "text", "bbox": [0.1, index / 100, 0.5, (index + 1) / 100]} for index in range(7)
        ]
        blocks.append(
            {
                "index": 7,
                "type": "image",
                "bbox": [0.1, 0.2, 0.5, 0.3],
                "content": [
                    {"type": "image_body", "index": 7},
                    {"type": "image_footnote", "index": 8},
                    {"type": "image_footnote", "index": 9},
                ],
            }
        )
        blocks.extend(
            [
                {"index": 10, "type": "text", "bbox": [0.1, 0.6, 0.5, 0.7]},
                {"index": 11, "type": "text", "bbox": [0.1, 0.8, 0.5, 0.9]},
            ]
        )
        additions = [
            {"type": "text", "bbox": [0.1, y, 0.5, y + 0.01], "content": [{"type": "text", "content": str(y)}]}
            for y in (0.4, 0.45, 0.5)
        ]

        _insert_by_page_position(blocks, additions)

        indices = [block["index"] for block in blocks]
        self.assertEqual(indices, sorted(indices))
        self.assertEqual(len(indices), len(set(indices)))
        self.assertEqual([block["index"] for block in blocks[8:11]], [10, 11, 12])
        self.assertEqual(blocks[7]["content"][0]["index"], 7)
        self.assertEqual(blocks[11]["index"], 13)


if __name__ == "__main__":
    unittest.main()
