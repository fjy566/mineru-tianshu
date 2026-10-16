#!/usr/bin/env python3
# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
"""Pre-download the ModelScope assets used by Tianshu's FunASR engines."""

from __future__ import annotations

import sys
from pathlib import Path


MODELS = (
    ("iic/SenseVoiceSmall", "SenseVoice multilingual speech recognition"),
    ("iic/speech_fsmn_vad_zh-cn-16k-common-pytorch", "FunASR VAD"),
    ("iic/punc_ct-transformer_cn-en-common-vocab471067-large", "FunASR punctuation"),
    ("iic/speech_campplus_sv_zh-cn_16k-common", "CAM++ speaker embeddings"),
    (
        "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        "Paraformer speech recognition and speaker diarization",
    ),
)


def main() -> int:
    try:
        from modelscope import snapshot_download
    except ImportError as error:
        print("ModelScope is missing. Install backend/requirements.txt first.", file=sys.stderr)
        print(str(error), file=sys.stderr)
        return 1

    failures: list[tuple[str, str]] = []
    for index, (model_id, description) in enumerate(MODELS, start=1):
        print(f"\n[{index}/{len(MODELS)}] {description}: {model_id}", flush=True)
        try:
            # Use ModelScope's normal per-user cache. FunASR resolves these same
            # model IDs and aliases from that cache when audio jobs are started.
            model_path = Path(snapshot_download(model_id=model_id)).resolve()
            if not model_path.is_dir() or not any(model_path.iterdir()):
                raise RuntimeError(f"Downloaded model directory is empty: {model_path}")
            print(f"Ready: {model_path}", flush=True)
        except Exception as error:  # keep downloading the remaining optional audio models
            failures.append((model_id, str(error)))
            print(f"FAILED: {model_id}: {error}", file=sys.stderr, flush=True)

    if failures:
        print("\nAudio model download finished with failures:", file=sys.stderr)
        for model_id, error in failures:
            print(f"- {model_id}: {error}", file=sys.stderr)
        return 1

    print(f"\nAll {len(MODELS)} audio models are cached and ready.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
