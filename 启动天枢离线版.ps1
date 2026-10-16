# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
param(
    [int]$ApiPort = 8000,
    [int]$WorkerPort = 8001,
    [int]$FrontendPort = 3000,
    [int]$McpPort = 8002,
    [switch]$NoBrowser,
    [switch]$SkipDesktopShortcuts
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$runtime = Join-Path $root 'runtime'
$python = Join-Path $runtime 'python\python.exe'
$node = Join-Path $runtime 'node\node.exe'
$pwsh = Join-Path $runtime 'powershell\pwsh.exe'
$vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'
$stateFile = Join-Path $root 'data\runtime\offline-pids.json'
$envFile = Join-Path $backend '.env'
$createdCredentials = $false

function Show-Error([string]$message) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($message, '天枢离线版启动失败', 'OK', 'Error') | Out-Null
    } catch { Write-Host $message -ForegroundColor Red }
}

function New-RandomHex([int]$byteCount) {
    $bytes = [byte[]]::new($byteCount)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToHexString($bytes).ToLowerInvariant()
}

function Test-ListeningPort([int]$port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Set-DesktopShortcuts {
    if ($SkipDesktopShortcuts) { return }
    $desktop = [Environment]::GetFolderPath('Desktop')
    if (-not $desktop -or -not (Test-Path -LiteralPath $desktop)) { return }
    try {
        $shell = New-Object -ComObject WScript.Shell
        $entries = @(
            @{ Name = '天枢离线版.lnk'; Script = (Join-Path $root '启动天枢离线版.ps1') },
            @{ Name = '停止天枢离线版.lnk'; Script = (Join-Path $root '停止天枢离线版.ps1') }
        )
        $portArgs = if ($ApiPort -ne 8000 -or $WorkerPort -ne 8001 -or $FrontendPort -ne 3000 -or $McpPort -ne 8002) {
            " -ApiPort $ApiPort -WorkerPort $WorkerPort -FrontendPort $FrontendPort -McpPort $McpPort"
        } else { '' }
        foreach ($entry in $entries) {
            $link = $shell.CreateShortcut((Join-Path $desktop $entry.Name))
            $link.TargetPath = $pwsh
            $arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + $entry.Script + '"'
            if ($entry.Name -eq '天枢离线版.lnk') { $arguments += $portArgs }
            $link.Arguments = $arguments
            $link.WorkingDirectory = $root
            $link.WindowStyle = 7
            $link.IconLocation = "$pwsh,0"
            $link.Save()
        }
    } catch {
        Write-Warning "无法创建桌面快捷方式：$($_.Exception.Message)"
    }
}

try {
    foreach ($required in @($python, $node, $pwsh, $vite, (Join-Path $backend 'start_all.py'), (Join-Path $root 'models\MinerU-4_models_onnx'), (Join-Path $root 'models\MinerU2.5-Pro-2605-1.2B-GGUF'))) {
        if (-not (Test-Path -LiteralPath $required)) { throw "离线包文件缺失：$required" }
    }

    if (-not (Test-Path -LiteralPath $envFile)) {
        $password = New-RandomHex 24
        $jwtSecret = New-RandomHex 48
        @(
            '# First-run local settings. Keep this file private.'
            'TIANSHU_ADMIN_USERNAME=admin'
            "TIANSHU_ADMIN_PASSWORD=$password"
            "JWT_SECRET_KEY=$jwtSecret"
            'SSO_ENABLED=false'
            'REDIS_QUEUE_ENABLED=false'
            'RUSTFS_ENABLED=false'
            'SCHEDULER_ENABLED=true'
        ) | Set-Content -LiteralPath $envFile -Encoding utf8
        $createdCredentials = $true
    } else {
        $password = $null
    }

    # Keep all mutable state beside the portable folder so it remains relocatable.
    $data = Join-Path $root 'data'
    $output = Join-Path $data 'output'
    $uploads = Join-Path $root 'input'
    $database = Join-Path $data 'db\mineru_tianshu.db'
    $logs = Join-Path $root 'logs'
    New-Item -ItemType Directory -Force -Path $logs, (Join-Path $data 'db'), (Join-Path $data 'runtime'), (Join-Path $data 'mineru4'), $output, $uploads | Out-Null

    $env:PYTHONNOUSERSITE = '1'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:MINERU_CONFIG = Join-Path $backend 'mineru4.yaml'
    $env:MINERU_HOME = Join-Path $data 'mineru4'
    $env:TIANSHU_MODEL_DIR = Join-Path $root 'models'
    $env:MINERU_MODEL_SOURCE = 'local'
    $env:MODELSCOPE_CACHE = Join-Path $root 'models\modelscope_cache'
    $env:HF_HOME = Join-Path $root 'models\huggingface_cache'
    $env:HUGGINGFACE_HUB_CACHE = Join-Path $root 'models\huggingface_cache\hub'
    $env:TORCH_HOME = Join-Path $root 'models\torch_cache'
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    $env:TIANSHU_API_HOST = '127.0.0.1'
    $env:TIANSHU_WORKER_HOST = '127.0.0.1'
    $env:TIANSHU_API_PROXY_TARGET = "http://127.0.0.1:$ApiPort"
    $env:TIANSHU_OCR_BACKFILL_ENABLED = 'true'
    $env:RUSTFS_ENABLED = 'false'
    $env:TIANSHU_LOCAL_FILE_SERVER_ENABLED = 'true'
    $env:DATABASE_PATH = $database
    $env:UPLOAD_PATH = $uploads
    $env:OUTPUT_PATH = $output
    $env:API_PORT = "$ApiPort"
    $env:WORKER_PORT = "$WorkerPort"
    $env:MCP_PORT = "$McpPort"
    $env:MAX_CONCURRENT_TASKS = '1'
    $env:WORKERS_PER_DEVICE = '1'
    $env:PATH = (Join-Path $runtime 'python') + ';' + (Join-Path $runtime 'ffmpeg') + ';' + (Join-Path $runtime 'node') + ';' + $env:PATH

    Set-DesktopShortcuts

    if (Test-Path -LiteralPath $stateFile) {
        try {
            $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
            $healthy = (Invoke-WebRequest "http://127.0.0.1:$($state.apiPort)/api/v1/health" -TimeoutSec 4).StatusCode -eq 200
            $webOk = (Invoke-WebRequest "http://127.0.0.1:$($state.frontendPort)" -TimeoutSec 4).StatusCode -eq 200
            if ($healthy -and $webOk) {
                if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$($state.frontendPort)" }
                return
            }
        } catch { }
        & (Join-Path $root '停止天枢离线版.ps1') -Quiet
        Remove-Item -LiteralPath $stateFile -Force -ErrorAction SilentlyContinue
    }

    foreach ($port in @($ApiPort, $WorkerPort, $FrontendPort)) {
        if (Test-ListeningPort $port) { throw "端口 $port 已被占用，请更换离线版端口或先停止占用该端口的服务。" }
    }

    $backendOut = Join-Path $logs 'offline-backend.out.log'
    $backendErr = Join-Path $logs 'offline-backend.err.log'
    $frontendOut = Join-Path $logs 'offline-frontend.out.log'
    $frontendErr = Join-Path $logs 'offline-frontend.err.log'
    $backendArgs = '"start_all.py" --output-dir "' + $output + '" --api-port ' + $ApiPort + ' --worker-port ' + $WorkerPort + ' --accelerator auto --workers-per-device 1 --devices auto'
    $api = Start-Process -FilePath $python -ArgumentList $backendArgs -WorkingDirectory $backend -PassThru -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
    $viteArgs = '"' + $vite + '" --host 127.0.0.1 --port ' + $FrontendPort + ' --strictPort'
    $web = Start-Process -FilePath $node -ArgumentList $viteArgs -WorkingDirectory $frontend -PassThru -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr
    @{ apiLauncherPid = $api.Id; frontendPid = $web.Id; apiPort = $ApiPort; workerPort = $WorkerPort; frontendPort = $FrontendPort; startedAt = (Get-Date).ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding utf8

    $deadline = (Get-Date).AddMinutes(3)
    $apiReady = $false
    $webReady = $false
    $workerReady = $false
    while ((Get-Date) -lt $deadline) {
        $api.Refresh(); $web.Refresh()
        if ($api.HasExited -or $web.HasExited) { break }
        try { $apiReady = (Invoke-WebRequest "http://127.0.0.1:$ApiPort/api/v1/health" -TimeoutSec 2).StatusCode -eq 200 } catch { }
        try { $webReady = (Invoke-WebRequest "http://127.0.0.1:$FrontendPort" -TimeoutSec 2).StatusCode -eq 200 } catch { }
        $workerReady = Test-ListeningPort $WorkerPort
        if ($apiReady -and $webReady -and $workerReady) { break }
        Start-Sleep -Seconds 2
    }
    if (-not $apiReady -or -not $webReady -or -not $workerReady) {
        & (Join-Path $root '停止天枢离线版.ps1') -Quiet
        throw "服务在 3 分钟内未全部就绪。日志位于：$logs"
    }

    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$FrontendPort" }
    if ($createdCredentials) {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show("本机管理员账号已生成：`n用户名：admin`n密码：$password`n`n密码保存在 $envFile。请登录后修改密码并妥善保管。", '天枢离线版首次启动', 'OK', 'Information') | Out-Null
    }
} catch {
    Show-Error ("$($_.Exception.Message)`n`n请查看安装目录 logs 文件夹中的启动日志。")
    exit 1
}
