# Fork 身份与修改记录

本仓库是 **fjy566/mineru-tianshu**，fork 自 **magicyuan876/mineru-tianshu**。

- 原项目作者：magicyuan876 及 MinerU Tianshu Contributors。
- 原项目地址：<https://github.com/magicyuan876/mineru-tianshu>。
- 本 fork 地址：<https://github.com/fjy566/mineru-tianshu>。
- 本 fork 维护者：fjy566，仅维护增量修改，不改变原作品归属。
- 保留原 `Copyright 2024 MinerU Tianshu Contributors`、原 [LICENSE](LICENSE) 和原 Git 历史；补充 [NOTICE](NOTICE)。
- 第三方依赖、引擎、模型分别保留其许可证，不因 fork 而改为本项目版权。

## 2026-10-16：原生可用性修复

对应提交 `4ded210`，基于原项目 `89f1bcd`。随后正常合并 fork 中已有的上游 `46af54c` 及其前置提交，保留双方历史。

| 范围 | 修改 |
|---|---|
| MinerU 与 OCR | 4.0.12 适配器、通用 RapidOCR 逐页补漏、完整 Markdown、原始页码 |
| 格式与多媒体 | FASTQ 引擎、格式路由、本机旧 Office 转换、音视频解析和结果标准化 |
| API/认证/MCP | 任务操作保护、参数校验、本地 Logo、时间戳、MCP SSE |
| 前端 | 上传/清空、任务列表与详情、预览净化、PDF 定位、登录/退出、设置与 API 文档 |
| 开发环境 | PowerShell 7 启动/停止、Vite 代理、Vue 类型检查、开发依赖与回归测试 |

具体文件与行变更可通过 `git show 4ded210` 查看。真实本机验收范围见 [原生可用性报告](docs/REVIEW_2026-10-16.md)。

## 2026-10-16：解耦和等价性能优化

- 新增 `backend/task_processing/dispatch.py`：转换执行与 Worker 生命周期解耦，能力通过参数传入，模块不加载模型框架。
- 新增 `backend/mineru_pipeline/ocr_geometry.py`：几何与去重算法独立于文件、模型和运行时状态。
- 修改 `ocr_gap_filler.py`：复用同一识别结果的规范化候选，保留逐页及高分辨率复识别。
- 修改 `standard_output_normalizer.py`：优先固定规范路径，仅在缺失时递归查找，保留原输出选择优先级。
- 修改 `mineru4_adapter.py`：复用已读取的中间 JSON 文本，避免写后立即重读。
- 新增前端 `markdownRenderer.ts`：独立 Marked 实例，保留公式、高亮及净化；组件令牌更新复用基础 HTML。
- 新增后端等价性回归、前端 HTML 固定基线和组件回归、可复现微基准与真实 PDF 对比脚本。
- 更新中英文 README、开发文档与性能说明。
- pre-commit 的 Ruff 版本与开发依赖统一为 0.17.0；相应源文件仅做格式统一的改动也保留 fork 标记。

修改过的可注释源文件附有 fork 修改标记；JSON 清单和锁文件不插入无效注释，其变更在 Git 历史中记录。
前端依赖清单增加测试依赖及测试命令，保留原项目名称和依赖许可。原作者 Star/贡献链接仍指向上游。

## v2.2.1-fjy566.1 发布补充

新增 Windows 原生开发包安装脚本、可重复打包工具及发布说明；启动器从 PATH 查找 npm。
fork 的标签发布不自动触发继承的容器构建，手动构建入口仍保留。该联网初始化开发包不捆绑运行时和模型权重，现由 v2.2.1-fjy566.3 取代。

## v2.2.1-fjy566.3 Windows 开发分发包

- 安装脚本通过 winget 自动补齐 Python 3.12、Node.js LTS、FFmpeg 与缺少的 LibreOffice；随后安装后端/前端依赖、构建前端并创建桌面快捷方式。
- 进度界面显示 12 个安装阶段和长任务耗时；MinerU 模型下载带官方 `mineru-kit` 输出及完整性校验，FunASR 模型按服务使用的 ModelScope ID 预下载到当前用户缓存。
- MinerU 固定使用项目配置的 ONNX 小模型与 llama.cpp VLM，不减少解析步骤、推理精度、OCR 分辨率或补漏流程。
- 保留原作者 magicyuan876 与 MinerU Tianshu Contributors 的署名、原许可证及 Git 历史。

## 准确率约束与限制

本轮不修改模型权重、推理精度、解析档位、OCR 分辨率、置信度阈值、页覆盖或补漏策略。
以旧新算法结果相等、HTML 基线及真实 OCR 比较验证本次重构；这不表示任意文档都能达到百分之百识别准确率。
基准仅对应局部后处理，不能推广为完整推理同倍数提速。实验水印、外部服务及其他既有能力边界见验收报告。
