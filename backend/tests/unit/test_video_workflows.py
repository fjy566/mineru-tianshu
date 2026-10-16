# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
"""音视频回归：真实依赖之间的结构、白底画面与无音轨场景。"""

import json
from types import SimpleNamespace
import cv2
import numpy as np
import pytest
from video_engines.video_engine import VideoProcessingEngine
from video_engines.keyframe_extractor import KeyframeExtractor, KeyFrame


def test_white_slide_with_text_is_not_discarded(tmp_path):
    image = np.full((700, 1000, 3), 255, dtype=np.uint8)
    cv2.putText(image, "Readable white slide", (60, 120), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    path = tmp_path / "slide.png"
    cv2.imwrite(str(path), image)
    assert KeyframeExtractor()._filter_quality([KeyFrame(0, 0, str(path))])


def test_subsecond_video_has_a_sample_frame(tmp_path):
    path = tmp_path / "short.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (100, 100))
    assert writer.isOpened()
    writer.write(np.zeros((100, 100, 3), dtype=np.uint8))
    writer.release()
    assert KeyframeExtractor()._detect_scenes(str(path)) == [(0.0, 0)]


@pytest.mark.parametrize("has_audio", [True, False])
def test_video_persists_source_even_when_audio_result_has_no_source(tmp_path, mocker, has_audio):
    engine = object.__new__(VideoProcessingEngine)
    audio = tmp_path / "source.wav"
    audio.write_bytes(b"audio")
    mocker.patch.object(engine, "extract_audio", return_value=str(audio))
    model = mocker.Mock()
    model.parse.return_value = {"markdown": "# Audio\n\nHello", "json_data": {"segments": [], "metadata": {}}}
    mocker.patch.object(engine, "_load_audio_engine", return_value=model)
    mocker.patch(
        "video_engines.video_engine.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout=json.dumps({"streams": [{"index": 0}] if has_audio else []})),
    )
    mocker.patch(
        "video_engines.keyframe_extractor.VideoOCREngine.process",
        return_value={
            "success": True,
            "total_keyframes": 1,
            "keyframes": [{"ocr_text": "VISIBLE_SLIDE"}],
            "markdown": "# Frames\n\nVISIBLE_SLIDE",
            "markdown_file": "frames.md",
            "json_file": "frames.json",
        },
    )
    result = engine.parse(str(tmp_path / "source.mp4"), str(tmp_path / "out"), enable_keyframe_ocr=True)
    saved = json.loads((tmp_path / "out/content.json").read_text(encoding="utf-8"))
    assert saved["source"]["file_type"] == "video"
    assert saved["keyframe_ocr"]["enabled"] is True
    assert "VISIBLE_SLIDE" in result["markdown"]
    if not has_audio:
        model.parse.assert_not_called()
