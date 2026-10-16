# 天枢原生开发版 v2.2.1-fjy566.3

本版本为 [fjy566/mineru-tianshu](https://github.com/fjy566/mineru-tianshu) fork 的 Windows 原生开发分发包。原项目作者仍为 **magicyuan876 及 MinerU Tianshu Contributors**；本 fork 保留原项目署名、许可证和 Git 历史。

## 下载内容

- `tianshu-v2.2.1-fjy566.3-windows-native-dev.zip`：项目源码、已构建前端、安装/启动/停止脚本、文档、LICENSE、NOTICE 和逐文件 SHA-256 清单。
- `RELEASE_NOTES.md`、`release-manifest.json`、`SHA256SUMS`：发布说明、源代码和文件校验信息。
- GitHub 自动生成的 Source code：标签对应的纯源码，不含前端构建产物。

本开发包约 4 MB，**不会预装运行时、虚拟环境、前端依赖或模型权重**。安装器联网后将它们装到本机，`frontend/src` 保持可编辑且支持 Vite 热更新。部署使用 Windows 原生 Python/Node.js，不使用 Docker。

## 安装

1. 下载并解压 ZIP 到准备长期使用的目录，例如 `E:\Program Files\MinerU`。
2. 在该目录打开 PowerShell 7.6，先查看环境：

   ```powershell
   & '.\安装天枢开发环境.ps1' -CheckOnly
   ```

3. 开始自动初始化：

   ```powershell
   & '.\安装天枢开发环境.ps1'
   ```

如果系统还没有 PowerShell 7.6，可从系统自带的 Windows PowerShell 运行第 3 步；安装器会通过 winget 安装 PowerShell 7.6，并在新版本中接续安装。`-CheckOnly` 只做检查，不会安装缺少的 PowerShell。

需要 Windows x64 和可联网的 Windows Package Manager（winget）。若从 PowerShell 5.1 或旧版 7.x 启动，安装器先通过 winget 安装/升级 PowerShell 7.6，再由 7.6 继续执行；若尚未安装 Python 3.12、Node.js LTS、FFmpeg 或 Office 转换器，也会调用 winget 安装。随后创建 Python 虚拟环境，安装后端依赖，安装 npm 锁定依赖并构建前端，再下载和验证 MinerU Standard 模型及 FunASR 音频模型。MinerU 模型使用 ONNX 小模型和 llama.cpp VLM；音频模型进入当前 Windows 用户的 ModelScope 缓存。

脚本显示 12 阶段进度条，并保留 pip、npm、winget 与模型工具自己的下载输出；较大下载会显示当前阶段和已等待时间，不猜测未公开的下载百分比。首次依赖及模型下载可能耗时较长；建议安装目录所在磁盘至少留出 25 GB 可用空间。

成功后桌面会出现“启动天枢开发版”和“停止天枢开发版”。启动地址为 <http://127.0.0.1:3000>，API 文档为 <http://127.0.0.1:8000/docs>。首次安装生成管理员 `admin` 账号和随机密码；密码只写入本机 `backend/.env` 并显示在安装终端。已有 `backend/.env` 时保留原配置。

## 模型与可选能力

- MinerU Standard：下载并校验 ONNX 小模型和 llama.cpp VLM 权重，支持 PDF 文档解析。
- 音频：预下载 SenseVoice、VAD、Paraformer、标点预测和 CAM++ 说话人模型；完整模型处理能力仍取决于本机资源。
- FFmpeg：用于音频/视频处理；脚本在缺少时尝试通过 winget 安装。
- LibreOffice：仅在未检测到 Microsoft Office/LibreOffice 时尝试安装，供旧版 DOC/PPT 转换。
- NVIDIA 驱动与 CUDA 不由安装器改动；无兼容 GPU 时按 CPU 路径运行。
- 实验性水印去除模型受其模型卡用途限制，因此安装器不会自动下载。LaMa 修复权重仍由功能在需要时加载。

可选参数：`-SkipModels` 跳过 MinerU 模型；`-SkipAudioModels` 跳过音频模型；`-SkipOptionalTools` 跳过 FFmpeg/LibreOffice 安装；`-SkipShortcuts` 不创建桌面快捷方式。跳过模型会使对应功能在模型准备完成前不可用。

如果下载中断，关闭窗口后重新运行同一安装脚本；已完成的依赖与下载缓存会复用。默认模型源为 ModelScope；后端依赖使用 pip 配置的包索引。

## 版权与验证边界

原项目地址：<https://github.com/magicyuan876/mineru-tianshu>。本 fork 地址：<https://github.com/fjy566/mineru-tianshu>。原项目 LICENSE、NOTICE、作者署名与历史均保留；第三方依赖及模型继续适用各自许可证。

此为联网初始化的开发分发包，不是免安装或离线包。系统级安装、PyPI 下载、npm 下载和模型下载受本机网络、Windows 权限、系统策略和硬件影响。安装器无法自动安装 NVIDIA 驱动，也不会改写现有 `.env`、用户文件或转换结果。
