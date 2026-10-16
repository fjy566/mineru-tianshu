# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
"""同一 MinerU 中间结果分别走旧新补漏，逐字比较 Markdown 和结构。"""

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path

from benchmark_equivalent_processing import ROOT, load_baseline


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def create_samples(scratch):
    import pymupdf

    source = scratch / "native.pdf"
    with pymupdf.open() as document:
        for index in range(2):
            page = document.new_page()
            page.insert_text((40, 40), "Repeated header", fontsize=12)
            page.insert_text((40, 100), f"QA_COMPLETE_PAGE_{index + 1}", fontsize=16)
            page.insert_text((40, 150), "完整中文：数量 12，单位 mm，范围 3.1-8.0。", fontname="china-s", fontsize=14)
            for row, text in enumerate(["项目 | 数值 | 单位", "长度 | 12.5 | mm", "温度 | 36.8 | C"]):
                page.insert_text((40, 220 + row * 35), text, fontname="china-s", fontsize=13)
            page.insert_text((40, 790), "Repeated footer", fontsize=11)
        document.save(source)
    scanned = scratch / "scanned.pdf"
    mixed = scratch / "mixed.pdf"
    forced_gap = scratch / "forced-gap.pdf"
    forced_gap.write_bytes(source.read_bytes())
    with pymupdf.open(source) as original:
        pixels = original[1].get_pixmap(matrix=pymupdf.Matrix(2.2, 2.2)).tobytes("png")
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_image(page.rect, stream=pixels)
            document.save(scanned)
        with pymupdf.open() as document:
            document.insert_pdf(original, from_page=0, to_page=0)
            page = document.new_page()
            page.insert_image(page.rect, stream=pixels)
            document.save(mixed)
    return [source, scanned, mixed, forced_gap]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="4ded210")
    parser.add_argument("--output", type=Path, default=ROOT / "work/perf-20261016/pdf-equivalence.json")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for name, value in {
        "MINERU_CONFIG": ROOT / "backend/mineru4.yaml",
        "MINERU_HOME": ROOT / "data/mineru4",
        "TIANSHU_MODEL_DIR": ROOT / "models",
    }.items():
        os.environ.setdefault(name, str(value))
    os.environ["TIANSHU_OCR_BACKFILL_ENABLED"] = "true"
    from mineru import ParseResult, parse
    from mineru.parser.writer import FileBasedDataWriter
    from mineru.render import render_markdown, render_content_list_v2, render_structured_content
    from mineru.render.contracts import RenderMode
    from mineru_pipeline import ocr_gap_filler as current

    records = []
    scratch_root = args.output.parent.resolve()
    with tempfile.TemporaryDirectory(prefix="real-pdf-", dir=scratch_root) as directory:
        scratch = Path(directory).resolve()
        assert scratch.is_relative_to(scratch_root) and scratch != scratch_root
        old = load_baseline(args.baseline, "backend/mineru_pipeline/ocr_gap_filler.py", "baseline_pdf_ocr", scratch)
        engine = current._get_engine()
        old._get_engine = lambda: engine
        for source in create_samples(scratch):
            output = scratch / source.stem
            output.mkdir()
            result = parse(source, tier="basic", ocr_mode="auto")
            result.save(FileBasedDataWriter(str(output)))
            base = json.loads((output / "middle_json.json").read_text(encoding="utf-8"))
            if source.name == "forced-gap.pdf":
                # 模拟主解析漏掉一页版面，验证真实 OCR 补录而非仅验证空增量。
                base["pages"][0]["blocks"] = []
            outputs = []
            for module in (old, current):
                middle = copy.deepcopy(base)
                audit = module.supplement_uncovered_pdf_text(source, middle)
                assert audit["status"] == "completed", audit
                parsed = ParseResult.from_json(json.dumps(middle, ensure_ascii=False))
                outputs.append(
                    {
                        "middle": middle,
                        "markdown": render_markdown(parsed.middle_json, mode=RenderMode.FULL),
                        "content_list": render_content_list_v2(parsed.middle_json),
                        "structured": render_structured_content(parsed.middle_json),
                        "audit": audit,
                    }
                )
            assert outputs[0] == outputs[1], f"Content or geometry changed: {source.name}"
            if source.name == "forced-gap.pdf":
                assert outputs[1]["audit"]["added_rows"] > 0
            record = {
                "sample": source.name,
                "equal_middle": True,
                "equal_markdown": True,
                "equal_content_list": True,
                "equal_structured": True,
                "equal_audit": True,
                "pages": len(base["pages"]),
                "added_rows": outputs[1]["audit"]["added_rows"],
                "sha256": digest(outputs[1]),
            }
            records.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
    args.output.write_text(
        json.dumps(
            {
                "baseline": args.baseline,
                "scope": "same MinerU inference, actual RapidOCR before/after",
                "results": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
