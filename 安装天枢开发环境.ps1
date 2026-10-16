#requires -Version 7.6
# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$SkipModels,
    [switch]$SkipShortcuts
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv/Scripts/python.exe'
$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $nodeCommand -or -not $npmCommand) { throw '请先安装 Node.js 22.12 或更高版本，并重新打开 PowerShell 7.6。' }
$nodeVersion = [version](& $nodeCommand.Source -p 'process.versions.node')
if ($nodeVersion -lt [version]'22.12') { throw "Node.js $nodeVersion 版本过低，需要 22.12 或更高版本。" }

$basePython = $null
if (Test-Path -LiteralPath $python) {
    $basePython = $python
} elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $candidate = & py.exe -3.12 -c 'import sys; print(sys.executable)' 2>$null
    if ($LASTEXITCODE -eq 0 -and $candidate) { $basePython = $candidate.Trim() }
}
if (-not $basePython) {
    $candidate = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($candidate) { $basePython = $candidate.Source }
}
if (-not $basePython) { throw '请先安装 Python 3.12（Windows Python Launcher 可用 py -3.12 调用）。' }
$pythonVersion = & $basePython -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
if ($LASTEXITCODE -ne 0 -or $pythonVersion.Trim() -ne '3.12') { throw '此发布包需要 Python 3.12，请安装后重试。' }

if ($CheckOnly) {
    [PSCustomObject]@{
        PowerShell = $PSVersionTable.PSVersion.ToString()
        Python = $pythonVersion.Trim()
        Node = $nodeVersion.ToString()
        Npm = $npmCommand.Source
        ExistingVirtualEnvironment = (Test-Path -LiteralPath $python)
        ExistingConfiguration = (Test-Path -LiteralPath (Join-Path $root 'backend/.env'))
        FFmpeg = [bool](Get-Command ffmpeg.exe -ErrorAction SilentlyContinue)
    }
    return
}

function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "命令执行失败（退出码 $LASTEXITCODE）：$Program" }
}

$env:PYTHONUTF8 = '1'
if (-not (Test-Path -LiteralPath $python)) {
    Invoke-Checked $basePython @('-m', 'venv', (Join-Path $root '.venv'))
}
Invoke-Checked $python @('-m', 'pip', 'install', '-r', (Join-Path $root 'backend/requirements-dev.txt'))
Invoke-Checked $npmCommand.Source @('ci', '--prefix', (Join-Path $root 'frontend'))

$configPath = Join-Path $root 'backend/.env'
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
    Write-Host '保留已有 backend/.env 配置。'
}

New-Item -ItemType Directory -Force -Path (Join-Path $root 'models'), (Join-Path $root 'data/db'), (Join-Path $root 'data/output') | Out-Null
$env:MINERU_CONFIG = Join-Path $root 'backend/mineru4.yaml'
$env:MINERU_HOME = Join-Path $root 'data/mineru4'
$env:TIANSHU_MODEL_DIR = Join-Path $root 'models'
if (-not $SkipModels) {
    $mineruKit = Join-Path $root '.venv/Scripts/mineru-kit.exe'
    Invoke-Checked $mineruKit @('models', 'download', '--tier', 'standard', '--source', 'modelscope')
    Invoke-Checked $mineruKit @('models', 'verify', '--tier', 'standard')
} else {
    Write-Warning '已跳过模型下载；必须已有可用模型后才能转换 PDF。'
}

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
}
if (-not (Get-Command ffmpeg.exe -ErrorAction SilentlyContinue)) {
    Write-Warning '未检测到 FFmpeg：PDF/文档仍可使用，音视频处理需先安装 FFmpeg 并加入 PATH。'
}
Write-Host '开发环境已准备完成。使用桌面快捷方式，或运行 ./启动天枢开发版.ps1。' -ForegroundColor Green
