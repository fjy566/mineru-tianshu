"""通过 MinerU 4 的公共解析和渲染接口生成天枢约定的结果文件。"""

import json
from pathlib import Path

from loguru import logger

from .ocr_gap_filler import supplement_uncovered_pdf_text


def do_parse(
    *,
    output_dir,
    pdf_file_names,
    pdf_bytes_list,
    backend="pipeline",
    parse_method="auto",
    server_url=None,
    start_page_id=0,
    end_page_id=None,
    formula_enable=True,
    table_enable=True,
    f_dump_orig_pdf=True,
    **options,
):
    from mineru import ParseResult, parse
    from mineru.config import VlmConfig
    from mineru.parser.writer import FileBasedDataWriter
    from mineru.render import render_content_list_v2, render_markdown, render_structured_content
    from mineru.render.contracts import RenderMode

    if backend == "pipeline":
        tier = "basic"
    elif backend.startswith(("vlm-", "hybrid-")):
        tier = "standard"
    else:
        raise ValueError(f"不支持的 MinerU 解析模式：{backend}")

    if not formula_enable or not table_enable:
        raise ValueError("MinerU 4 不支持单独关闭公式或表格识别，请在高级选项中启用这两项。")

    output_root = Path(output_dir)
    for name, payload in zip(pdf_file_names, pdf_bytes_list, strict=True):
        name = Path(name).name
        source = output_root / "input" / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(payload)

        # Office 在 MinerU 4 中统一走原生 Flash 解析，PDF 的页码参数仍保持前端的零基索引。
        current_tier = "flash" if source.suffix.lower() in {".docx", ".xlsx", ".pptx"} else tier
        page_range = ""
        if source.suffix.lower() == ".pdf" and (start_page_id or end_page_id is not None):
            first = max(0, int(start_page_id)) + 1
            last = str(int(end_page_id) + 1) if end_page_id is not None else "r1"
            page_range = f"{first}-{last}"

        vlm_config = VlmConfig(server_url=server_url) if server_url else None
        logger.info(f"📄 MinerU 4: tier={current_tier}, ocr_mode={parse_method}, pages={page_range or 'all'}")
        result = parse(source, tier=current_tier, ocr_mode=parse_method, page_range=page_range, vlm_config=vlm_config)

        destination = output_root / source.stem / parse_method
        destination.mkdir(parents=True, exist_ok=True)
        result.save(FileBasedDataWriter(str(destination)))
        (destination / "markdown.md").replace(destination / "result.md")
        middle_path = destination / "middle_json.json"
        middle_data = json.loads(middle_path.read_text(encoding="utf-8"))
        audit = None
        if source.suffix.lower() == ".pdf":
            audit = supplement_uncovered_pdf_text(source, middle_data)
            (destination / "ocr_audit.json").write_text(
                json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            middle_path.write_text(json.dumps(middle_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 统一从补录后的中间结果生成 Markdown 和结构化输出，确保页面、图片和文字一致。
        exported = ParseResult.from_json(middle_path.read_text(encoding="utf-8"))
        markdown = render_markdown(exported.middle_json, mode=RenderMode.FULL)
        if audit and audit["status"] in {"partial", "failed"}:
            markdown = (
                "> OCR 补漏未全部完成，部分页面仅保留主解析结果。"
                "请核对原 PDF，详细记录见 ocr_audit.json。\n\n" + markdown
            )
        for filename in ("markdown.md", "result.md"):
            (destination / filename).write_text(markdown, encoding="utf-8")
        (destination / "structured_content.json").write_text(
            json.dumps(render_structured_content(exported.middle_json), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        content_list = render_content_list_v2(exported.middle_json)
        # 按页筛选后仍保留源 PDF 页码，避免预览定位到第一页。
        for page, blocks in zip(exported.middle_json.pages, content_list, strict=True):
            for block in blocks:
                block["page_idx"] = page.page_idx
        (destination / "result_content_list_v2.json").write_text(
            json.dumps(content_list, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        middle_path.replace(destination / "result_middle.json")
        if f_dump_orig_pdf and source.suffix.lower() == ".pdf":
            (destination / "result_origin.pdf").write_bytes(payload)
