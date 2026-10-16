# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python = Join-Path $root '.venv\Scripts\python.exe'
$npm = Join-Path $env:ProgramFiles 'nodejs\npm.cmd'
$stateFile = Join-Path $root 'logs\dev-pids.json'
$env:MINERU_CONFIG = Join-Path $backend 'mineru4.yaml'
$env:MINERU_HOME = Join-Path $root 'data\mineru4'
$env:TIANSHU_MODEL_DIR = Join-Path $root 'models'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:TIANSHU_OCR_BACKFILL_ENABLED = 'true'
# 本机开发不运行 RustFS 容器；图片通过带鉴权的 API 文件接口读取。
$env:RUSTFS_ENABLED = 'false'
$env:TIANSHU_LOCAL_FILE_SERVER_ENABLED = 'true'

function Fail([string]$message) {
    Write-Host "`n启动失败：$message" -ForegroundColor Red
    Write-Host '详情日志位于 E:\Program Files\MinerU\logs' -ForegroundColor Yellow
    Read-Host '按回车关闭窗口'
    exit 1
}

Set-Location $root
if (-not (Test-Path $python)) { Fail '项目虚拟环境不存在。请在安装目录运行 .venv 的 Python 环境配置。' }
if (-not (Test-Path (Join-Path $backend '.env'))) { Fail 'backend\.env 不存在，请先完成首次配置。' }
if (-not (Test-Path (Join-Path $frontend 'node_modules\vite\bin\vite.js'))) { Fail '前端依赖不存在，请先在 frontend 目录运行 npm install。' }
if (-not (Test-Path $npm)) { Fail '未找到 Node.js npm；请安装 Node.js 18 或更高版本。' }

# 重复点击快捷方式时，直接打开已经运行的本机服务。
if (Test-Path -LiteralPath $stateFile) {
    try {
        $runningApi = Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 3
        $runningWeb = Invoke-WebRequest 'http://127.0.0.1:3000' -TimeoutSec 3 -UseBasicParsing
        $runningWorker = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
        if ($runningApi.status -eq 'healthy' -and $runningWeb.StatusCode -eq 200 -and $runningWorker) {
            Write-Host '天枢开发版已在运行，正在打开页面。' -ForegroundColor Green
            Start-Process 'http://127.0.0.1:3000' -WindowStyle Hidden
            Read-Host '按回车关闭窗口'
            exit 0
        }
    } catch { }
}

$ports = @(8000, 8001, 3000)
foreach ($port in $ports) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        Fail "端口 $port 已被占用。请先停止已有服务。"
    }
}

$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logs, (Join-Path $root 'data\uploads'), (Join-Path $root 'data\output'), (Join-Path $root 'data\db'), (Join-Path $root 'models') | Out-Null
$backendOut = Join-Path $logs 'backend-dev.out.log'
$backendErr = Join-Path $logs 'backend-dev.err.log'
$frontendOut = Join-Path $logs 'frontend-dev.out.log'
$frontendErr = Join-Path $logs 'frontend-dev.err.log'
Remove-Item $backendOut, $backendErr, $frontendOut, $frontendErr -Force -ErrorAction SilentlyContinue
$env:MINERU_MODEL_SOURCE = 'local'
$env:HF_ENDPOINT = 'https://hf-mirror.com'

Write-Host '正在启动本机开发服务（API、GPU Worker、Scheduler、Vite）...' -ForegroundColor Cyan
$outputDirArg = '"' + (Join-Path $root 'data\output') + '"'
$api = Start-Process -FilePath $python -ArgumentList @('start_all.py', '--output-dir', $outputDirArg, '--accelerator', 'auto') -WorkingDirectory $backend -PassThru -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
Start-Sleep -Seconds 2
if ($api.HasExited) { Fail "后端启动器已退出。请查看 $backendOut 和 $backendErr" }

$viteArgs = 'run dev -- --host 127.0.0.1'
$vite = Start-Process -FilePath $npm -ArgumentList $viteArgs -WorkingDirectory $frontend -PassThru -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr
$state = @{ apiLauncherPid = $api.Id; frontendPid = $vite.Id; startedAt = (Get-Date).ToString('o') }
$state | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding utf8

$deadline = (Get-Date).AddSeconds(45)
$apiReady = $false
$webReady = $false
while ((Get-Date) -lt $deadline) {
    if ($api.HasExited) { break }
    $api.Refresh(); $vite.Refresh()
    if ($vite.HasExited) { break }
    try { $apiReady = (Invoke-WebRequest 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 2).StatusCode -eq 200 } catch { }
    try { $webReady = (Invoke-WebRequest 'http://127.0.0.1:3000' -TimeoutSec 2).StatusCode -eq 200 } catch { }
    if ($apiReady -and $webReady) { break }
    Start-Sleep -Seconds 2
}

if (-not $apiReady -or -not $webReady) {
    Write-Host "服务未能在 45 秒内全部就绪。日志：`n$backendOut`n$backendErr`n$frontendOut`n$frontendErr" -ForegroundColor Red
    if (-not $api.HasExited) { Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue }
    if (-not $vite.HasExited) { Stop-Process -Id $vite.Id -Force -ErrorAction SilentlyContinue }
    Read-Host '按回车关闭窗口'
    exit 1
}

Write-Host '天枢开发版已启动。' -ForegroundColor Green
Write-Host '前端（修改 frontend 源码会热更新）：http://127.0.0.1:3000'
Write-Host 'API 文档：http://127.0.0.1:8000/docs'
Write-Host "日志：$logs"
Start-Process 'http://127.0.0.1:3000'
Read-Host '服务在后台运行；按回车关闭此窗口（停止服务请用“停止天枢开发版”快捷方式）'
