# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
"""比较重构前后纯处理结果与开销，不改变模型或识别参数。"""

import argparse
import importlib.util
import json
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from loguru import logger
from mineru_pipeline.ocr_geometry import _deduplicate_lines
from output_normalizer.standard_output_normalizer import StandardOutputNormalizer


def load_baseline(ref, relative, module_name, scratch):
    code = subprocess.check_output(["git", "show", f"{ref}:{relative}"], cwd=ROOT)
    path = scratch / (module_name.rsplit(".", 1)[-1] + ".py")
    path.write_bytes(code)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compare(label, old, new, repeats):
    expected = old()
    assert new() == expected, label + " output changed"
    old_times, new_times = [], []
    for _ in range(repeats):
        for call, timings in ((old, old_times), (new, new_times)):
            start = time.perf_counter()
            result = call()
            timings.append(time.perf_counter() - start)
            assert result == expected, label + " output changed during measurement"
    old_median, new_median = statistics.median(old_times), statistics.median(new_times)
    return {
        "case": label,
        "equal_output": True,
        "repeats": repeats,
        "baseline_median_ms": old_median * 1000,
        "optimized_median_ms": new_median * 1000,
        "speedup": old_median / new_median,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="4ded210")
    parser.add_argument("--output", type=Path, default=ROOT / "work/perf-20261016/benchmark.json")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    assert args.repeats >= 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scratch_root = args.output.parent.resolve()
    logger.disable("output_normalizer")
    with tempfile.TemporaryDirectory(prefix="equivalence-", dir=scratch_root) as directory:
        scratch = Path(directory).resolve()
        assert scratch.is_relative_to(scratch_root) and scratch != scratch_root
        old_ocr = load_baseline(args.baseline, "backend/mineru_pipeline/ocr_gap_filler.py", "baseline_ocr", scratch)
        old_normalizer = load_baseline(
            args.baseline,
            "backend/output_normalizer/standard_output_normalizer.py",
            "output_normalizer.baseline_standard",
            scratch,
        ).StandardOutputNormalizer()
        normalizer = StandardOutputNormalizer()
        rng = random.Random(1016)
        results = []
        for label, families in (("ocr_1500_unique_texts", 1500), ("ocr_1500_repeated_texts_50_families", 50)):
            lines = [
                {
                    "text": f"文字 {index % families} + 单位 mm",
                    "score": rng.choice([0.7, 0.9, 0.95]),
                    "bbox": (0, index / 1500, 0.5, index / 1500 + 0.0004),
                }
                for index in range(1500)
            ]
            results.append(
                compare(
                    label, lambda: old_ocr._deduplicate_lines(lines), lambda: _deduplicate_lines(lines), args.repeats
                )
            )
        output_dir = scratch / "output"
        output_dir.mkdir()
        (output_dir / "result.md").write_text("# 完整结果\n", encoding="utf-8")
        (output_dir / "result.json").write_text('{"complete": true}', encoding="utf-8")
        for group in range(20):
            nested = output_dir / str(group)
            nested.mkdir()
            for index in range(100):
                (nested / f"aux-{index}.json").write_text("{}", encoding="utf-8")

        def normalize_pair(instance):
            return (
                instance._normalize_markdown(output_dir).read_bytes(),
                instance._normalize_json(output_dir).read_bytes(),
            )

        results.append(
            compare(
                "canonical_outputs_with_2000_aux_files",
                lambda: normalize_pair(old_normalizer),
                lambda: normalize_pair(normalizer),
                args.repeats,
            )
        )
    record = {
        "baseline": args.baseline,
        "python": sys.version.split()[0],
        "scope": "postprocessing microbenchmarks, not total inference speed",
        "results": results,
    }
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
