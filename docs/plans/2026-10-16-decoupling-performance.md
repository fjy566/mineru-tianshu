# Decoupling and performance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 拆分任务调度与转换执行、OCR 几何处理与模型调用、Markdown 渲染与组件状态；减少重复计算和文件扫描，保留转换结果与识别质量。

**Architecture:** 采用小模块与显式依赖传递，保留 Worker 的生命周期和原有引擎入口。优化限定在等价算法、渲染复用和确定输出路径的快速定位；不更换模型，不下调分辨率、置信度或推理精度，不跳过任何页和 OCR 检查。

**Tech Stack:** Python 3.12、MinerU 4、RapidOCR、Vue 3、TypeScript、Vite、pytest。

---

## 方案选择

1. 首选：等价算法和模块边界重构。风险可控，可逐项比较旧新输出；本轮实施。
2. 提高模型推理并发：可能增加显存峰值并争用资源，需要额外硬件压测，暂不全局提高默认值。
3. 跳过 OCR、降低图片尺寸或使用更小模型：可能改变识别结果，不符合准确率约束。

## Task 1: 保存工作区与同步 fork 历史

**Files:** 当前已有本机修复、`README.md`、`LICENSE`。

1. 核对 Git 待提交文件，排除 `.env`、模型、用户输入、输出、日志及本机验收原始数据。
2. 保存已完成的原生部署/转换修复为单独提交，保留原作者历史。
3. 保留上游 remote，将用户 fork 配为推送目标；获取 fork/main，正常合并其新增提交。
4. 记录当前基线实现，核对 LICENSE 和现有署名。

## Task 2: 解耦转换分发

**Files:** `backend/task_processing/dispatch.py`、`backend/litserve_worker.py`、相关 Worker 测试。

1. 将扩展名/引擎路由与旧 Office 中间产物处理提取到独立模块。
2. 使用显式能力参数和服务方法依赖，避免分发模块导入模型框架。
3. 保留异常、回退、参数及清理语义；通过原 Worker 路由回归检查。

## Task 3: OCR 与输出目录开销优化

**Files:** `backend/mineru_pipeline/ocr_geometry.py`、`ocr_gap_filler.py`、`backend/output_normalizer/standard_output_normalizer.py`。

1. 提取纯 OCR 几何和去重函数，与模型/文件处理解耦。
2. 去重按相同规范化文本分桶，保留相同排序、重叠公式与阈值，减少不同文字之间的无效比较。
3. 每个 OCR 结果只转换一次候选坐标，供补漏和图片区域候选共同使用。
4. 优先检查规范结果/主结果固定路径，仅在缺失时扫描目录，保持原选择优先级。
5. 使用旧新输出相等断言和重复基准测量验证，报告适用范围。

## Task 4: 前端渲染解耦

**Files:** `frontend/src/utils/markdownRenderer.ts`、`frontend/src/components/MarkdownViewer.vue`。

1. 使用单独 Marked 实例，避免组件反复挂载修改全局配置。
2. 将语法高亮、公式与净化提取为独立渲染函数。
3. 分离基础 HTML 和鉴权图片链接，令牌变化时复用基础渲染结果。
4. 保留原有 GFM、换行、公式、自动高亮和 DOMPurify 行为。

## Task 5: 验收、版权与推送

**Files:** `README.md`、`README_EN.md`、`FORK_CHANGES.md`、性能说明和测试。

1. 运行现有及新增回归测试、前端类型检查和构建；使用真实合成文档比较转换内容与结构。
2. 写入可重现基准方法、实际结果和限制，区分算法收益与完整模型推理耗时。
3. 中英文 README 顶部标注原作者 magicyuan876、上游链接和 fjy566 fork 身份；保留原 LICENSE 与版权行。
4. 更新变更说明，提交所有审核后的项目源码和文档。
5. 普通 push 到 `https://github.com/fjy566/mineru-tianshu.git`，比较远端与本地提交 SHA 并确认工作区状态。
