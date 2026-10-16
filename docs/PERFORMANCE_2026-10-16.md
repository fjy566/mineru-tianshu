# 解耦、性能与结果等价性

本文件记录 fjy566 fork 的 2026-10-16 增量修改。原项目作者、许可证与历史见 [FORK_CHANGES.md](../FORK_CHANGES.md)。

## 模块边界

| 模块 | 职责 | 依赖边界 |
|---|---|---|
| `backend/litserve_worker.py` | 队列、解密、拆分、水印前处理、任务状态、通知、合并 | 调用分发模块，不在生命周期代码中展开所有引擎分支 |
| `backend/task_processing/dispatch.py` | 根据格式和显式能力选择引擎，清理旧 Office 中间产物 | 通过 Protocol/能力对象接收服务，不导入模型框架 |
| `backend/mineru_pipeline/ocr_geometry.py` | 坐标、候选规范化、覆盖率与同文去重 | 仅标准库，无模型或文件系统依赖 |
| `backend/mineru_pipeline/ocr_gap_filler.py` | 逐页渲染、RapidOCR 调用、补漏、异常与审计 | 复用纯几何模块；推理锁和逐页失败保护保留 |
| `frontend/src/utils/markdownRenderer.ts` | Markdown、自动高亮、公式、净化 | 独立 Marked 实例，无认证状态依赖 |
| `MarkdownViewer.vue` | 加载/错误状态、显示、图片鉴权链接 | 内容计算与令牌计算分离，令牌更新不重新解析正文 |

## 优化及不变量

1. **OCR 去重按规范化文本分桶。** 旧算法将每条候选与所有已保留候选比较，且重复执行正则处理。新算法只比较文本相同的候选；排序、空白/casefold 规则、双向重叠公式与 0.5 阈值不变。相同文本的最坏情况仍可能为平方复杂度，不宣称所有输入都是线性。
2. **复用候选坐标。** 同一普通分辨率 OCR 结果只执行一次文本/坐标/置信度规范化，供页面补漏和图片候选共同使用；空候选列表也直接复用。高分辨率识别仍执行原策略。
3. **先检查标准输出。** 已有 `result.md/result.json` 或主 `content.md/content.json` 时直接采用原优先级，无需先遍历辅助目录。其他目录形态仍走原递归选择规则。
4. **复用中间 JSON 文本。** 写入补漏结果后直接使用内存中的同一 JSON 文本构造 ParseResult，避免立即再读同一文件。
5. **前端独立解析器。** 组件挂载不重复修改全局 marked；鉴权令牌变化时只更新图片 URL，保留已净化 HTML。

模型版本、权重、推理档位与精度、OCR 分辨率、置信度阈值、逐页检查及补漏均保持不变。没有引入结果抽样、跨文档内容缓存或跳页。

## 局部基准

基线：`4ded210`（本 fork 原生可用性修复完成时）。Python 3.12.3，Windows 本机；每项先核验结果相等，再顺序重复 5 次，报告中位数。

| 后处理样本 | 旧实现 | 新实现 | 局部比值 |
|---|---:|---:|---:|
| 1500 条不同文本的 OCR 去重 | 2006.646 ms | 2.009 ms | 999.0 倍 |
| 1500 条候选、50 类重复文本 | 1986.531 ms | 23.854 ms | 83.3 倍 |
| 已有规范结果、2000 个辅助文件的定位与读取 | 23.237 ms | 0.271 ms | 85.7 倍 |

这些是特定数据集的**局部后处理**结果。普通页面候选少时，收益会较小；文档整体耗时还取决于模型推理、OCR、文件系统、硬件与输入版式，不能据此宣称完整解析有相同比例的加速。
测量期间没有比较新旧整个模型推理速度，因此不提供没有证据的端到端提速百分比。

原始数值：[benchmark JSON](benchmarks/2026-10-16-processing.json)。重跑：

```powershell
& '.venv/Scripts/python.exe' scripts/benchmark_equivalent_processing.py --baseline 4ded210
```

脚本需要完整 Git 历史包含基线提交；浅克隆请先获取该历史。计时数据写入忽略的 `work/perf-20261016/`。

## 质量与功能验证

- 后端：**245 项测试通过**，无失败或跳过；新增随机 Unicode/坐标/同分排序去重等价检查，候选复用检查和无递归扫描检查；原 Worker 路由测试继续通过。
- 前端：**10 项测试通过**。8 个固定 HTML 基线从重构前组件生成，覆盖中文、列表、表格、代码、四种公式语法、HTML、图片与危险输入；另外验证不修改全局 marked，以及令牌更新不重新渲染正文。
- Vue 类型检查与 Vite 生产构建通过；后端 Ruff 检查通过。
- 重启部署后的真实 API 复测：24 项格式转换全部完成并包含预期文字，覆盖旧/新 Office、PDF 全文/选页/密码、PNG/BMP/TIFF/WebP、文本/电子书、生物格式、ZIP、WAV、MP4。临时任务已清理，原有用户任务保持不变。
- 真实模型：原生、扫描、混合 PDF，以及人工删除一页主解析版面以模拟漏检的 PDF，共 4 个场景、7 页。
- 对每个场景，先完成同一次 MinerU 主解析，再将相同中间结果分别交给旧新实现，调用实际 RapidOCR。中间 JSON、完整 Markdown、Content List、结构化内容和 OCR 审计均相等；模拟漏检场景旧新均补录 **7 行**。

该比较隔离了模型自身可能存在的非确定性，验证本次后处理变化；它不是对所有文档准确率的绝对保证。扫描模糊、手写、复杂表格等原有识别能力边界仍然存在。
真实 PDF 对比摘要：[equivalence JSON](benchmarks/2026-10-16-pdf-equivalence.json)。重跑：

```powershell
& '.venv/Scripts/python.exe' scripts/check_pdf_processing_equivalence.py --baseline 4ded210
& '.venv/Scripts/python.exe' -m pytest backend/tests -q
Push-Location frontend
npm ci
npm test
npm run build
Pop-Location
```

测试样本由脚本生成；公开证据不包含用户文档、账号、密钥、数据库、模型权重或本机日志。

## 后续优化边界

本轮没有盲目提高模型并发。多 Worker、线程数和 GPU 并发需要按显存和负载另行测量，过度并发可能降低吞吐并导致内存不足。以后可以在相同质量门禁下继续优化，不能用降低识别质量替代性能工程。
