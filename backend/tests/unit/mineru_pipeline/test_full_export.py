"""实际 MinerU 4 中间数据导出：页眉不应导致空文档。"""

import json
from mineru import ParseResult
from mineru.render import render_markdown
from mineru.render.contracts import RenderMode


def test_full_export_retains_header_text():
    data = {
        "metadata": {"file_suffix": "pdf", "producer": {"name": "mineru", "version": "4.0.12"}},
        "schema": "docvortex.middle",
        "schema_version": "2.0",
        "is_full_document": True,
        "pages": [
            {
                "page_idx": 0,
                "blocks": [
                    {
                        "type": "header",
                        "index": 0,
                        "bbox": [0.1, 0.1, 0.5, 0.15],
                        "content": [{"type": "text", "content": "ONLY_CONTENT_IN_HEADER"}],
                    }
                ],
            }
        ],
    }
    parsed = ParseResult.from_json(json.dumps(data))
    assert "ONLY" in render_markdown(parsed.middle_json, mode=RenderMode.FULL)
