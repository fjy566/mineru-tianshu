# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$SkipModels,
    [switch]$SkipAudioModels,
    [switch]$SkipOptionalTools,
    [switch]$SkipShortcuts
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$stageCount = 12
$pythonVenv = Join-Path $root '.venv\Scripts\python.exe'
$configPath = Join-Path $root 'backend\.env'
$modelsPath = Join-Path $root 'models'
$dataPath = Join-Path $root 'data'

function Write-InstallProgress([int]$Stage, [string]$Title, [string]$Status) {
    $percent = [int][Math]::Floor((($Stage - 1) / $stageCount) * 100)
    Write-Progress -Id 1 -Activity '天枢开发环境初始化' -Status "阶段 $Stage/$stageCount：$Title — $Status" -PercentComplete $percent
}

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $combined = @($machinePath, $userPath, $env:Path) -join ';'
    $env:Path = (($combined -split ';' | Where-Object { $_ } | Select-Object -Unique) -join ';')
}

function Get-Python312Path {
    $candidates = [System.Collections.Generic.List[string]]::new()
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $launcherResult = & $launcher.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $launcherResult) {
            $candidates.Add($launcherResult.Trim())
        }
    }
    $candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'))
    if ($env:ProgramFiles) { $candidates.Add((Join-Path $env:ProgramFiles 'Python312\python.exe')) }
    $pathPython = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pathPython) { $candidates.Add($pathPython.Source) }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $version = & $candidate -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>$null
        if ($LASTEXITCODE -eq 0 -and $version.Trim() -eq '3.12') { return $candidate }
    }
    return $null
}

function Get-NodeInfo {
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($node) { $candidates.Add($node.Source) }
    if ($env:ProgramFiles) { $candidates.Add((Join-Path $env:ProgramFiles 'nodejs\node.exe')) }
    if ($env:LOCALAPPDATA) { $candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\nodejs\node.exe')) }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $versionText = & $candidate -p 'process.versions.node' 2>$null
        if ($LASTEXITCODE -eq 0) {
            try {
                return [PSCustomObject]@{ Path = $candidate; Version = [version]$versionText.Trim() }
            } catch { }
        }
    }
    return $null
}

function Test-FFmpegInstalled {
    if (Get-Command ffmpeg.exe -ErrorAction SilentlyContinue) { return $true }
    $candidates = @(
        (Join-Path $env:ProgramFiles 'ffmpeg\bin\ffmpeg.exe'),
        (Join-Path $env:ProgramFiles 'ffmpeg\ffmpeg.exe')
    )
    return [bool]($candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1)
}

function Test-OfficeConverterInstalled {
    if (Get-Command soffice.exe -ErrorAction SilentlyContinue) { return $true }
    if (Get-Command winword.exe -ErrorAction SilentlyContinue) { return $true }
    $officeCandidates = @(
        (Join-Path $env:ProgramFiles 'LibreOffice\program\soffice.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft Office\root\Office16\WINWORD.EXE'),
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft Office\root\Office16\WINWORD.EXE')
    )
    return [bool]($officeCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1)
}

function Invoke-NativeProcess {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][int]$Stage,
        [Parameter(Mandatory)][string]$Title,
        [switch]$AllowFailure
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FilePath
    $startInfo.WorkingDirectory = $root
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $false
    foreach ($argument in $Arguments) { [void]$startInfo.ArgumentList.Add([string]$argument) }

    try {
        $process = [System.Diagnostics.Process]::Start($startInfo)
    } catch {
        throw "无法启动 $Title。请确认安装目录可写，并重新打开 PowerShell 7.6 后重试。详细错误：$($_.Exception.Message)"
    }

    $startedAt = Get-Date
    try {
        while (-not $process.WaitForExit(1000)) {
            $elapsed = (Get-Date) - $startedAt
            $wait = $elapsed.ToString('hh\:mm\:ss')
            Write-InstallProgress $Stage $Title "正在运行，已等待 $wait；下载过程会显示在窗口中，请保持窗口打开"
        }
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) {
            if ($AllowFailure) {
                Write-Warning "$Title 未完成（退出码 $($process.ExitCode)）。其余功能仍可使用；重新运行安装脚本会续用已下载的缓存。"
                return $false
            }
            throw "$Title 失败（退出码 $($process.ExitCode)）。请检查上方错误信息后重新运行安装脚本。"
        }
        return $true
    } finally {
        $process.Dispose()
    }
}

function Invoke-WinGetPackage([string]$PackageId, [string]$Action, [int]$Stage, [string]$FriendlyName) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "无法自动安装 $FriendlyName：未检测到 Windows 包管理器 winget。请通过 Microsoft Store 安装应用安装程序后，重新运行本脚本（https://aka.ms/getwinget）。"
    }
    $arguments = @($Action, '--id', $PackageId, '--exact', '--source', 'winget', '--accept-source-agreements', '--accept-package-agreements', '--silent')
    if ($Action -eq 'upgrade') { $arguments += '--include-unknown' }
    Invoke-NativeProcess -FilePath $winget.Source -Arguments $arguments -Stage $Stage -Title "安装 $FriendlyName" | Out-Null
    Refresh-ProcessPath
}

function Show-Preflight {
    $pythonFound = Get-Python312Path
    $nodeFound = Get-NodeInfo
    $driveRoot = [IO.Path]::GetPathRoot($root)
    $freeGB = [Math]::Round(([IO.DriveInfo]::new($driveRoot)).AvailableFreeSpace / 1GB, 1)
    [PSCustomObject]@{
        PowerShell = $PSVersionTable.PSVersion.ToString()
        Python312 = if ($pythonFound) { $pythonFound } else { '缺失（可由 winget 自动安装）' }
        Node = if ($nodeFound) { "$($nodeFound.Version) — $($nodeFound.Path)" } else { '缺失（可由 winget 自动安装）' }
        Winget = [bool](Get-Command winget.exe -ErrorAction SilentlyContinue)
        FFmpeg = Test-FFmpegInstalled
        OfficeConverter = Test-OfficeConverterInstalled
        VirtualEnvironment = Test-Path -LiteralPath $pythonVenv
        MinerUModels = (Test-Path -LiteralPath (Join-Path $modelsPath 'MinerU-4_models_onnx')) -and (Test-Path -LiteralPath (Join-Path $modelsPath 'MinerU2.5-Pro-2605-1.2B-GGUF'))
        FreeDiskGB = $freeGB
        DesktopShortcuts = -not $SkipShortcuts
    } | Format-List
    if ($freeGB -lt 25) {
        Write-Warning '可用空间少于 25 GB。后端依赖、前端依赖和模型需要较多空间，请先释放磁盘空间。'
    }
}

if ($PSVersionTable.PSVersion -lt [version]'7.6') {
    if ($CheckOnly) {
        Write-Host "当前 PowerShell 版本为 $($PSVersionTable.PSVersion)。正式安装使用 PowerShell 7.6；运行安装脚本时会尝试通过 winget 自动安装并切换到 PowerShell 7.6。" -ForegroundColor Yellow
        return
    }

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw '正式安装需要 PowerShell 7.6。请先通过 Microsoft Store 安装应用安装程序（winget），再重新运行本脚本。'
    }
    $existingPwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
    if ($existingPwsh) {
        Write-Host "检测到 PowerShell $($PSVersionTable.PSVersion)，正在通过 winget 更新到 7.6 或更高版本……" -ForegroundColor Cyan
        & $winget.Source upgrade --id Microsoft.PowerShell --exact --source winget --accept-source-agreements --accept-package-agreements --silent --include-unknown
    } else {
        Write-Host '正在通过 winget 安装 PowerShell 7.6……' -ForegroundColor Cyan
        & $winget.Source install --id Microsoft.PowerShell --exact --source winget --accept-source-agreements --accept-package-agreements --silent
    }
    if ($LASTEXITCODE -ne 0) {
        throw "PowerShell 7.6 安装/更新失败（退出码 $LASTEXITCODE）。请手动安装 PowerShell 7.6 后重新运行此脚本。"
    }

    Refresh-ProcessPath
    $pwshCandidates = [System.Collections.Generic.List[string]]::new()
    $resolvedPwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
    if ($resolvedPwsh) { $pwshCandidates.Add($resolvedPwsh.Source) }
    if ($env:ProgramFiles) { $pwshCandidates.Add((Join-Path $env:ProgramFiles 'PowerShell\7\pwsh.exe')) }
    if ($env:LOCALAPPDATA) { $pwshCandidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\PowerShell\7\pwsh.exe')) }
    $pwshPath = $null
    foreach ($candidate in ($pwshCandidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $versionText = & $candidate -NoLogo -NoProfile -Command '$PSVersionTable.PSVersion.ToString()' 2>$null
        if ($LASTEXITCODE -eq 0 -and $versionText) {
            try {
                $candidateVersion = [version]($versionText.Trim())
                if ($candidateVersion -ge [version]'7.6') {
                    $pwshPath = $candidate
                    break
                }
            } catch { }
        }
    }
    if (-not $pwshPath) { throw 'PowerShell 7.6 安装后未找到 pwsh.exe。请重新打开终端后再次运行安装脚本。' }

    $childArguments = @('-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
    foreach ($switchName in @('SkipModels', 'SkipAudioModels', 'SkipOptionalTools', 'SkipShortcuts')) {
        if ((Get-Variable -Name $switchName -ValueOnly).IsPresent) { $childArguments += "-$switchName" }
    }
    $child = Start-Process -FilePath $pwshPath -ArgumentList $childArguments -WorkingDirectory $root -NoNewWindow -Wait -PassThru
    if ($child.ExitCode -ne 0) { throw "PowerShell 7.6 安装流程未完成（退出码 $($child.ExitCode)）。请修复报错后重新运行安装脚本。" }
    return
}

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:MINERU_CONFIG = Join-Path $root 'backend\mineru4.yaml'
$env:MINERU_HOME = Join-Path $dataPath 'mineru4'
$env:TIANSHU_MODEL_DIR = $modelsPath

if ($CheckOnly) {
    Show-Preflight
    return
}

try {
    Write-InstallProgress 1 '环境检查' '确认 Windows x64、PowerShell、网络和磁盘空间'
    if (-not [Environment]::Is64BitOperatingSystem) { throw '此开发包需要 64 位 Windows。' }
    $wingetAvailable = [bool](Get-Command winget.exe -ErrorAction SilentlyContinue)
    $needsOptionalTools = -not $SkipOptionalTools -and ((-not (Test-FFmpegInstalled)) -or (-not (Test-OfficeConverterInstalled)))
    if (-not $wingetAvailable -and ((-not (Get-Python312Path)) -or (-not (Get-NodeInfo)) -or $needsOptionalTools)) {
        throw '当前缺少 winget，且至少一项系统依赖需要自动安装。请先通过 Microsoft Store 安装应用安装程序，然后重新运行此脚本。'
    }

    Write-InstallProgress 2 'Python 3.12' '检查已安装版本'
    $basePython = Get-Python312Path
    if (-not $basePython) {
        Invoke-WinGetPackage 'Python.Python.3.12' 'install' 2 'Python 3.12'
        $basePython = Get-Python312Path
    }
    if (-not $basePython) { throw 'Python 3.12 安装后仍未找到解释器。请关闭并重新打开 PowerShell 7.6，再运行安装脚本。' }
    Write-Host "✓ Python 3.12：$basePython" -ForegroundColor Green

    Write-InstallProgress 3 'Node.js' '检查满足前端构建要求的 LTS 版本（22.12 或更高）'
    $nodeInfo = Get-NodeInfo
    if (-not $nodeInfo) {
        Invoke-WinGetPackage 'OpenJS.NodeJS.LTS' 'install' 3 'Node.js LTS'
        $nodeInfo = Get-NodeInfo
    } elseif ($nodeInfo.Version -lt [version]'22.12') {
        Invoke-WinGetPackage 'OpenJS.NodeJS.LTS' 'upgrade' 3 'Node.js LTS'
        $nodeInfo = Get-NodeInfo
    }
    if (-not $nodeInfo -or $nodeInfo.Version -lt [version]'22.12') {
        throw 'Node.js 22.12 或更高版本未就绪。请重新打开 PowerShell 7.6 后运行安装脚本。'
    }
    $node = $nodeInfo.Path
    $npmCli = Join-Path (Split-Path -Parent $node) 'node_modules\npm\bin\npm-cli.js'
    if (-not (Test-Path -LiteralPath $npmCli -PathType Leaf)) { throw "找不到 npm CLI：$npmCli。请修复 Node.js LTS 安装后重试。" }
    Write-Host "✓ Node.js $($nodeInfo.Version) 和 npm 已就绪。" -ForegroundColor Green

    Write-InstallProgress 4 '可选系统工具' '安装 FFmpeg 与旧版 Office 文件转换器'
    if (-not $SkipOptionalTools) {
        if (-not (Test-FFmpegInstalled)) {
            Invoke-WinGetPackage 'Gyan.FFmpeg.Shared' 'install' 4 'FFmpeg（音视频解析）'
        } else {
            Write-Host '✓ 已检测到 FFmpeg。' -ForegroundColor Green
        }
        if (-not (Test-OfficeConverterInstalled)) {
            Invoke-WinGetPackage 'TheDocumentFoundation.LibreOffice' 'install' 4 'LibreOffice（旧版 DOC/PPT 转换）'
        } else {
            Write-Host '✓ 已检测到 Microsoft Office 或 LibreOffice。' -ForegroundColor Green
        }
        Refresh-ProcessPath
    } else {
        Write-Host '已跳过可选系统工具。音视频需要 FFmpeg；旧版 DOC/PPT 需要 Office 或 LibreOffice。' -ForegroundColor Yellow
    }

    Write-InstallProgress 5 'Python 虚拟环境' '创建或复用项目 .venv'
    if (-not (Test-Path -LiteralPath $pythonVenv -PathType Leaf)) {
        Invoke-NativeProcess -FilePath $basePython -Arguments @('-m', 'venv', (Join-Path $root '.venv')) -Stage 5 -Title '创建 Python 虚拟环境' | Out-Null
    }

    Write-InstallProgress 6 '后端依赖' '安装 MinerU、RapidOCR、FastAPI、音频引擎及开发依赖'
    Invoke-NativeProcess -FilePath $pythonVenv -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip') -Stage 6 -Title '升级 pip' | Out-Null
    Invoke-NativeProcess -FilePath $pythonVenv -Arguments @('-m', 'pip', 'install', '-r', (Join-Path $root 'backend\requirements-dev.txt')) -Stage 6 -Title '安装 Python 后端依赖' | Out-Null

    Write-InstallProgress 7 '前端依赖' '安装锁定版本并构建可直接启动的开发界面'
    Invoke-NativeProcess -FilePath $node -Arguments @($npmCli, 'ci', '--prefix', (Join-Path $root 'frontend')) -Stage 7 -Title '安装前端 npm 依赖' | Out-Null
    Invoke-NativeProcess -FilePath $node -Arguments @($npmCli, 'run', 'build', '--prefix', (Join-Path $root 'frontend')) -Stage 7 -Title '构建前端资源' | Out-Null

    Write-InstallProgress 8 'MinerU 文档模型' '下载标准档位（ONNX + VLM），首次下载时间取决于网络'
    if (-not $SkipModels) {
        $mineruKit = Join-Path $root '.venv\Scripts\mineru-kit.exe'
        if (-not (Test-Path -LiteralPath $mineruKit -PathType Leaf)) { throw 'MinerU 安装后未找到 mineru-kit.exe。' }
        $modelOptions = @('--tier', 'standard', '--small-backend', 'onnx', '--vlm-engine', 'llama-cpp', '--source', 'modelscope')
        Invoke-NativeProcess -FilePath $mineruKit -Arguments (@('models', 'download') + $modelOptions) -Stage 8 -Title '下载 MinerU 标准模型' | Out-Null
    } else {
        Write-Warning '已跳过 MinerU 模型下载；PDF 转换需要模型就绪。'
    }

    Write-InstallProgress 9 '验证 MinerU 模型' '确认模型文件完整'
    if (-not $SkipModels) {
        $mineruKit = Join-Path $root '.venv\Scripts\mineru-kit.exe'
        Invoke-NativeProcess -FilePath $mineruKit -Arguments (@('models', 'verify') + $modelOptions) -Stage 9 -Title '验证 MinerU 模型' | Out-Null
    }

    Write-InstallProgress 10 '音频模型' '预下载 SenseVoice、VAD、Paraformer、标点和说话人模型'
    if (-not $SkipAudioModels) {
        $audioModelScript = Join-Path $root 'scripts\download_audio_models.py'
        $audioDownloadSucceeded = Invoke-NativeProcess -FilePath $pythonVenv -Arguments @($audioModelScript) -Stage 10 -Title '预下载音频模型' -AllowFailure
        if (-not $audioDownloadSucceeded) {
            Write-Warning '音频模型未全部准备完成。文档/PDF 仍可使用；音频首次处理时可能需要联网下载。'
        }
    } else {
        Write-Host '已跳过音频模型。首次使用音频功能时，FunASR 会按需联网下载。' -ForegroundColor Yellow
    }

    Write-InstallProgress 11 '本机配置' '创建数据目录和首次管理员账号'
    New-Item -ItemType Directory -Force -Path $modelsPath, (Join-Path $dataPath 'db'), (Join-Path $dataPath 'output'), (Join-Path $dataPath 'uploads'), (Join-Path $dataPath 'mineru4'), (Join-Path $root 'logs') | Out-Null
    if (-not (Test-Path -LiteralPath $configPath)) {
        $adminPassword = [Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(16))
        $jwtSecret = [Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
        @"
# Generated locally; do not upload this file.
TIANSHU_ADMIN_USERNAME=admin
TIANSHU_ADMIN_PASSWORD=$adminPassword
JWT_SECRET_KEY=$jwtSecret
DATABASE_PATH=../data/db/mineru_tianshu.db
UPLOAD_PATH=../input
OUTPUT_PATH=../data/output
API_PORT=8000
WORKERS_PER_DEVICE=1
MAX_CONCURRENT_TASKS=1
REDIS_QUEUE_ENABLED=false
RUSTFS_ENABLED=false
TIANSHU_LOCAL_FILE_SERVER_ENABLED=true
SSO_ENABLED=false
MCP_PORT=8002
"@ | Set-Content -LiteralPath $configPath -Encoding utf8
        Write-Host "首次管理员账号：admin；密码：$adminPassword" -ForegroundColor Yellow
        Write-Host '密码同时保存在本机 backend/.env 的 TIANSHU_ADMIN_PASSWORD 中。'
    } else {
        Write-Host '保留已有 backend/.env 配置。' -ForegroundColor Green
    }

    Write-InstallProgress 12 '桌面快捷方式' '创建启动和停止入口'
    if (-not $SkipShortcuts) {
        $pwsh = (Get-Process -Id $PID).Path
        $desktop = [Environment]::GetFolderPath('Desktop')
        $shortcutShell = New-Object -ComObject WScript.Shell
        foreach ($entry in @(
            @{ Name = '启动天枢开发版'; File = '启动天枢开发版.ps1' },
            @{ Name = '天枢 MinerU 开发版'; File = '启动天枢开发版.ps1' },
            @{ Name = '停止天枢开发版'; File = '停止天枢开发版.ps1' }
        )) {
            $shortcut = $shortcutShell.CreateShortcut((Join-Path $desktop ($entry.Name + '.lnk')))
            $shortcut.TargetPath = $pwsh
            $shortcut.Arguments = '-NoExit -NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $root $entry.File) + '"'
            $shortcut.WorkingDirectory = $root
            $shortcut.Save()
        }
    } else {
        Write-Host '已跳过桌面快捷方式。' -ForegroundColor Yellow
    }

    Write-Progress -Id 1 -Activity '天枢开发环境初始化' -Completed
    Write-Host "`n安装完成。前端源码位于 frontend/src，启动后可热更新。" -ForegroundColor Green
    Write-Host '桌面快捷方式：启动天枢开发版 / 停止天枢开发版。'
    Write-Host '访问地址：http://127.0.0.1:3000；API 文档：http://127.0.0.1:8000/docs'
    if (-not (Test-FFmpegInstalled)) { Write-Warning '未检测到 FFmpeg；音视频解析不可用。' }
    if (-not (Test-OfficeConverterInstalled)) { Write-Warning '未检测到 Office/LibreOffice；旧版 DOC/PPT 转换不可用。' }
} catch {
    Write-Progress -Id 1 -Activity '天枢开发环境初始化' -Completed
    Write-Host "`n安装未完成：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host '已完成的依赖和模型会保留。修复网络或前置条件后，在项目目录重新运行此脚本即可续装。' -ForegroundColor Yellow
    throw
}
