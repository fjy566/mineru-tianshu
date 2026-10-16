# 离线包第三方许可与来源

本包保留原项目 `magicyuan876/mineru-tianshu`、MinerU Tianshu Contributors 的版权及 [LICENSE](../LICENSE)。本 fork 的新增和修改记录见 [FORK_CHANGES.md](../FORK_CHANGES.md)。该文件不改变原作者或第三方作品的归属。

## 运行时与依赖

| 组件 | 版本/来源 | 许可与随包文件 |
|---|---|---|
| CPython | 3.12.10 Windows embeddable | Python Software Foundation License；`runtime/python/LICENSE.txt`。官方版本：[Python 3.12.10](https://www.python.org/downloads/release/python-31210/)。 |
| Python packages | 与本机验证环境相同的 `site-packages` | 每个发行包的版权和许可文件随其 `.dist-info` 元数据保留；包清单见 `runtime/python/THIRD_PARTY_PACKAGES.txt`。 |
| Node.js | 25.2.1 Windows x64 `node.exe` | MIT；`runtime/node/LICENSE`。来源：[Node.js v25.2.1](https://github.com/nodejs/node/tree/v25.2.1)。 |
| PowerShell | 7.6.5 portable runtime | MIT；`runtime/powershell/LICENSE.txt` 与 `ThirdPartyNotices.txt`。来源：[PowerShell](https://github.com/PowerShell/PowerShell)。 |
| FFmpeg / FFprobe | `n9.0.2-28-g669f5ab083`，LGPL 3+ 配置 | FFmpeg LGPL；`runtime/ffmpeg/LICENSE.txt`。包内附匹配的 FFmpeg 源码归档 `runtime/ffmpeg/source/ffmpeg-669f5ab083-source.tar.gz`。构建不启用 GPL/nonfree 编码器。来源：[FFmpeg](https://ffmpeg.org/) 和 [BtbN Windows 构建](https://github.com/BtbN/FFmpeg-Builds)。 |

## 模型

- **MinerU 4 ONNX**：来自 [OpenDataLab/MinerU-4_models_onnx](https://huggingface.co/opendatalab/MinerU-4_models_onnx)，本机模型卡标注 Apache License 2.0。模型卡列出 PP-DocLayoutV2、PP-OCRv6、PP-OCRv4 seal、PP-FormulaNet 等组件，并说明各来源模型的原始许可证和归属继续适用。模型卡及具体模型来源信息随包保留。
- **MinerU2.5-Pro-2605-1.2B GGUF**：基础模型由 OpenDataLab 发布，模型卡标记 Apache-2.0：[官方模型卡](https://huggingface.co/opendatalab/MinerU2.5-Pro-2605-1.2B)。随包 Q8_0 量化文件来自仓库配置 `jinzhenj/MinerU2.5-Pro-2605-1.2B-GGUF`；量化仓库没有随本机缓存提供独立许可证文件，因此保留其原始来源标识及基础模型归属，不宣称量化产物作者身份属于本 fork。
- **语音模型**：随包保留 ModelScope 缓存中的模型卡/README、配置和来源文件；卡片均标注 Apache License 2.0。包括 `iic/SenseVoiceSmall`、`iic/punc_ct-transformer_cn-en-common-vocab471067-large`、`iic/speech_campplus_sv_zh-cn_16k-common`、`iic/speech_fsmn_vad_zh-cn-16k-common-pytorch` 和 `iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch`。例如 [iic/SenseVoiceSmall](https://www.modelscope.cn/models/iic/SenseVoiceSmall)。
- **未包含的权重**：旧 `PDF-Extract-Kit-1.0` 不被当前 MinerU4 配置使用；水印模型 [corzent/yolo11x_watermark_detection](https://huggingface.co/corzent/yolo11x_watermark_detection) 的卡片写明仅供研究和教育，并禁止用于移除受版权保护内容的水印，因此没有重新分发该权重。

## 其他第三方代码

Vue、Vite 及其前端依赖和后端 Python 依赖的原始许可文件随包保留在 `frontend/node_modules` 与 Python `.dist-info` 目录中。使用或再分发时请遵守各自目录内的版权和许可证文本。此清单是随包来源索引，不把第三方组件整体重新许可为本 fork 的作品。
