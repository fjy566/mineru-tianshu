# 天枢原生开发版 v2.2.1-fjy566.1

本版本为 [fjy566/mineru-tianshu](https://github.com/fjy566/mineru-tianshu) 的 fork 发布。
原作者为 **magicyuan876 及 MinerU Tianshu Contributors**；原项目、许可证、署名与 Git 历史均保留。

## 下载内容

- `tianshu-v2.2.1-fjy566.1-windows-native-dev.zip`：完整项目源码、已构建的前端 `frontend/dist`、原生安装/启动/停止脚本、文档、LICENSE、NOTICE 和逐文件 SHA-256 清单。
- `SHA256SUMS`：发布附件的 SHA-256 校验值。
- `RELEASE_NOTES.md`：本说明。
- GitHub 自动生成的 Source code：对应标签的纯源码，不含前端构建产物。

**这是需要联网初始化的 Windows 原生开发包，不是离线免安装包。**
压缩包不含 Python/Node/PowerShell 运行时、虚拟环境、node_modules 或模型权重；不含用户文件、转换结果、账号、密钥、数据库和日志。

## 首次使用

1. 安装 Windows x64 的 Python 3.12、Node.js 22.12+ 和 PowerShell 7.6。
2. 将 ZIP 完整解压到固定目录，例如 `E:\Program Files\MinerU`。升级已有目录时先停止服务并备份，保留原 `.env`、模型和数据。
3. 在解压目录打开 PowerShell 7.6，执行：

   ```powershell
   & './安装天枢开发环境.ps1' -CheckOnly
   & './安装天枢开发环境.ps1'
   ```

   安装脚本创建/复用 `.venv`，安装开发依赖与前端依赖，下载并验证 Standard 模型，创建桌面快捷方式。
   首次生成随机管理员密码和 JWT 密钥；已有 `backend/.env` 时保留配置。
   管理员密码显示在安装终端，也保存在本机 `backend/.env` 的 `TIANSHU_ADMIN_PASSWORD` 中。

4. 点击桌面“启动天枢开发版”，访问 <http://127.0.0.1:3000>。停止使用“停止天枢开发版”。
5. 修改 `frontend/src` 自动热更新；后端修改后重启服务。

可选参数：`-SkipModels` 仅用于已有完整模型的环境，`-SkipShortcuts` 跳过快捷方式创建。
首次下载模型和依赖可能需要较长时间及较多磁盘空间；音频相关模型还可能在首次使用时下载。
音视频需要 FFmpeg 加入 PATH；旧 DOC/PPT 转换需要 Microsoft Office 或 LibreOffice。
GPU 加速取决于驱动和 PyTorch 安装，本包不保证在未配置 CUDA 的电脑上启用 GPU。

## 主要改动

- MinerU 4.0.12、RapidOCR 3.10.0 通用逐页补漏和完整 Markdown。
- PDF 页码定位、FASTQ/Office 路由、音视频输出、任务管理、登录退出、Logo 本地上传及 MCP SSE 修复。
- Worker 转换分发、OCR 几何处理、前端 Markdown 渲染解耦。
- 等价优化重复坐标转换、OCR 去重、结果文件定位和前端 HTML 复用，保留模型、分辨率、阈值、精度及补漏步骤。

## 验证与限制

本机通过 245 项后端测试、10 项前端测试及前端构建；重启后 24 项真实格式转换通过。
4 个 PDF 场景、7 页的旧新 Markdown、结构化结果、坐标和审计相等；模拟漏检时双方均补录 7 行。
局部性能数据和复现方法见 [性能报告](https://github.com/fjy566/mineru-tianshu/blob/v2.2.1-fjy566.1/docs/PERFORMANCE_2026-10-16.md)。

安装脚本和发布包另做语法、前置条件、文件清单与校验检查；未在全新 Windows 电脑上重装所有依赖和模型。
自动图片水印去除仍为实验能力，OCR 对任意模糊、手写或复杂表格的准确率没有百分之百保证；未配置的外部服务未做完整正向联调。

原项目：<https://github.com/magicyuan876/mineru-tianshu>。许可证见压缩包中的 LICENSE 和 NOTICE。
