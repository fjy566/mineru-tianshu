# 天枢 Windows 离线免安装包 v2.2.1-fjy566.2

本 Release 为 `fjy566/mineru-tianshu` fork 的离线 Windows x64 开发分发包。原项目作者仍为 **magicyuan876 与 MinerU Tianshu Contributors**；本 fork 保留上游许可证、版权信息和 Git 历史。

## 下载与解压

1. 在 GitHub Release 下载全部 `tianshu-v2.2.1-fjy566.2-windows-offline.zip.partNNN` 文件，以及 `JOIN_OFFLINE_PACKAGE.ps1`、`release-manifest.json`。
2. 将这些文件放在同一目录。
3. 用 PowerShell 7 或 Windows PowerShell 5.1 运行：

   ```powershell
   .\JOIN_OFFLINE_PACKAGE.ps1
   ```

脚本逐卷校验大小和 SHA-256，按顺序合并 ZIP，再验证完整 ZIP 的大小和 SHA-256 后解压。默认解压到脚本旁的 `MinerU-Tianshu-v2.2.1-fjy566.2`，并创建桌面启动和停止快捷方式。需要更改位置时使用 `-Destination 'D:\Apps\MinerU'`。下载、合并和解压期间建议预留约 40 GB 空间。

## 首次启动

双击桌面“天枢离线版”。第一次启动会在 `backend/.env` 生成本机管理员账号和强随机密码，并弹窗显示。请妥善保存并登录后修改密码。数据库、输入、输出、日志和模型运行缓存保存在解压目录附近，不会写入发布包。

浏览器地址为 `http://127.0.0.1:3000`，API 文档为 `http://127.0.0.1:8000/docs`。服务默认只监听本机回环地址。修改 `frontend/src` 后 Vite 会自动热更新。用桌面“停止天枢离线版”快捷方式停止服务。

若默认端口被占用，可用命令行启动并指定一组空闲端口：

```powershell
& '.\runtime\powershell\pwsh.exe' -NoProfile -File '.\启动天枢离线版.ps1' -ApiPort 18000 -WorkerPort 18001 -FrontendPort 13000 -McpPort 18002
```

## 内容和平台要求

- Windows x64；包内提供 CPython 3.12.10、Node.js 25.2.1、PowerShell 7.6.5、Vite 前端依赖和 LGPL 构建的 FFmpeg/FFprobe。
- 包含 MinerU 4.0.12 的 ONNX 小模型、MinerU2.5-Pro-2605-1.2B GGUF 和音频处理使用的五个 ModelScope 模型。
- 首次启动不需要下载 Python/Node 依赖或解析模型；本地 GPU 加速需要已安装的兼容 NVIDIA 驱动。无兼容 GPU 时使用 CPU 推理。
- 旧 `.doc`/`.ppt` 格式转换需要本机安装 Microsoft Office；Office 不随包分发。
- 旧的 `PDF-Extract-Kit-1.0` 已由当前 MinerU4 使用的模型取代，因此没有包含其 15GB 权重。水印检测权重的模型卡规定研究/教育用途并禁止用于移除受版权保护内容的水印；该权重不随包分发。相应功能若未配置本地模型，不属于此离线包的可用能力。
- 本机安装过程、用户数据库、上传/输出文件、`backend/.env` 和其他凭据均不进入 ZIP。

## 来源和验证

Release 清单记录源代码提交、压缩包、每个分卷的字节数与 SHA-256。下载完成后，合并脚本会重新计算并比较所有校验值。ZIP 构建器在发布前验证每个条目 CRC、目标路径、必需运行文件和禁止的本机数据路径。

离线第三方许可和模型来源见 [THIRD_PARTY_LICENSES_OFFLINE.md](THIRD_PARTY_LICENSES_OFFLINE.md)。上游 Docker 镜像发布信息保留在原项目 changelog 中；本 fork 的 Windows 离线包不使用 Docker。
