# Windows 本机开发：MinerU 4

本机部署已从 MinerU 3.4.5 升级为官方稳定版 **4.0.12**。
发布说明：https://github.com/opendatalab/MinerU/releases/tag/mineru-4.0.12-released

## 启动与开发

使用桌面“启动天枢开发版”和“停止天枢开发版”快捷方式。
它们调用默认 PowerShell 7.6，运行项目 `.venv` 中的 Python 和 Vite 开发服务器。
前端地址为 `http://127.0.0.1:3000`，修改 `frontend/src` 会热更新。
后端改动需要重启服务，API 文档位于 `http://127.0.0.1:8000/docs`。

启动器设置 `MINERU_CONFIG=backend/mineru4.yaml`，`MINERU_HOME=data/mineru4`。
`TIANSHU_MODEL_DIR` 指向项目 `models` 目录。
MinerU 4 使用 YAML 配置，不再读取旧的 `~/mineru.json`。
本机开发启动时关闭 RustFS 上传，解析图片留在任务输出目录，由带鉴权的 API 文件接口提供给前端预览；生产环境的 RustFS 失败保护不变。

PDF 主解析完成后，会用 RapidOCR 3.10.0（ONNX Runtime CPU）检查各页，并将置信度不低于 0.55、且落在 MinerU 未覆盖区域的文字补入页结构。若普通分辨率 OCR 在图片块上发现文字候选（包括不含数字的中文和英文），会仅对该页进行高分辨率复识别，并限制补录范围到原候选附近。Markdown、Content List V2 和结构化 JSON 都从补录后的中间结果生成，补录块按页坐标插入。设置 `TIANSHU_OCR_BACKFILL_ENABLED=false` 可关闭此步骤。

## 接口和模型

| 天枢选项 | MinerU 4 对应档位 | 本机模型 |
|---|---|---|
| Pipeline / 文档自动模式 | Basic | MinerU-4_models_onnx |
| VLM / Hybrid | Standard | ONNX 小模型 + MinerU2.5-Pro-2605-1.2B-GGUF |
| DOCX / PPTX | Flash 原生解析 | DocVortex |
| XLSX / XLS | 天枢现有 Excel 路由 | MarkItDown |

调用层使用公开的 `mineru.parse`、`ParseResult.save` 和 `render_content_list_v2`。
继续提供 Markdown、Content List V2、图片资源与源 PDF，供天枢前端预览。
指定页码仍接受前端的零基索引，调用层转换为 MinerU 4 的一基页范围。

新版公开解析接口不提供独立关闭公式或表格识别的选项；对应前端开关已固定开启，
旧版保存的关闭值会在加载配置时恢复为开启，扫描件预设也已更新。
旧的布局/文本边框 PDF 导出参数不再生成诊断 PDF；前端继续使用原始 PDF 和结构化坐标预览。

需要重新下载模型时，在项目目录用 PowerShell 7 运行：

```powershell
$env:MINERU_CONFIG = "$PWD\backend\mineru4.yaml"
$env:TIANSHU_MODEL_DIR = "$PWD\models"
& '.\.venv\Scripts\mineru-kit.exe' models download --tier standard --source modelscope
& '.\.venv\Scripts\mineru-kit.exe' models verify --tier standard
```

## 升级验证与回退资料

已验证包含原生文字和扫描页的 PDF、指定单页的 Standard/VLM 解析、DOCX 表格，
并通过前端代理提交任务、等待 Worker 完成、读取 Markdown/JSON 与 PDF 预览路径。
依赖检查和前端构建通过。

升级前的依赖清单位于 `work/mineru4/requirements-before.txt`。
原 MinerU 3.4.5 与 mineru-vl-utils 1.2.1 的 wheel 位于 `work/mineru4/rollback`，
替换前的核心包目录另存于 `work/mineru4/rollback-packages`。
旧 `PDF-Extract-Kit-1.0` 权重保留在模型目录中。
回退需要同时恢复旧调用层和依赖，不能只安装旧 wheel 后继续使用 MinerU 4 适配器。

## 通用 PDF 补漏与故障记录

RapidOCR 已作为项目依赖和正式解析步骤默认启用，不依赖测试文件名或路径。
补漏只新增文字，不对原解析结果做体检报告专用替换，不改写代码缩进或原始单位。
同位置同文 OCR 候选去重；已有图片标题、脚注和表格区域受保护。
每页渲染限制为最长边 4000 像素、约 1200 万像素，逐页异常不会丢弃其他页结果。
每个 PDF 解析目录生成 `ocr_audit.json`，包含状态、页码、补录文字、坐标、置信度与失败原因；
同一记录保存在 `result_middle.json` 的 `extensions.tian_shu_ocr_backfill`。
`partial` 或 `failed` 表示补漏未完全成功，不能视为已经核验完整。
Markdown 的两份文件从同一份补录结果生成。修改后需重启后端，新上传的文件自动应用。

OCR 无法保证模糊扫描、手写、复杂多栏或公式百分之百正确；补漏文字也不等于完整重建表格。
原图和原 PDF 继续保留，重要内容可依据审计坐标核对。

## 2026-10-16 可用性修复

- 桌面“启动天枢开发版”“天枢 MinerU 开发版”“停止天枢开发版”均使用本机 PowerShell 7.6.5。重复启动时检测已运行服务并打开页面。
- 构建会先执行 `vue-tsc --noEmit`，检查 Vue 模板中的事件处理函数和类型。
- PDF 完整导出保留页眉、页脚；选择部分页后，双向定位仍使用原 PDF 页码。Markdown 预览经过 DOMPurify 清理。
- FASTQ 等生物格式、文本、表格、EPUB、音视频根据真实格式路由，即使使用通用 Pipeline 预设也不会送入 PDF 解析器。
- Windows 安装了 Microsoft Office 时，旧版 DOC/PPT 可通过独立 COM 进程转换；缺少 LibreOffice 时使用此本机路径。宏被禁用，超时会中止转换进程。
- 本机关闭 RustFS 时，Logo 上传可保存到本地 `data/db/system-assets`；上传后仍需点击“保存设置”才会应用。
- 原生文字水印可在高级设置填写关键词；用户批注会保留。自动图片水印检测为实验功能，不能保证检测成功；当前图像修复使用 OpenCV，未安装 LaMa。
- SenseVoice 普通转写会分离内部语言/情绪标签与正文，读取真实文件时长，并使用模型返回的词和时间戳配对。原始模型文本保存在 JSON 的 `raw_transcript` 中。
- 登录后返回原请求页面；退出登录先清除认证状态，再进入登录页。

本轮详细修复、按钮验收范围和限制见 [审查与测试报告](REVIEW_2026-10-16.md)。
