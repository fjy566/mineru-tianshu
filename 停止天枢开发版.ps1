# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$stateFile = Join-Path $root 'logs\dev-pids.json'
$pids = @()
if (Test-Path $stateFile) {
    try {
        $state = Get-Content -Raw $stateFile | ConvertFrom-Json
        $pids += [int]$state.apiLauncherPid
        $pids += [int]$state.frontendPid
    } catch { }
}

# 通过监听端口补充查找子进程，start_all.py 自身也会派生 API、Worker 与 Scheduler。
foreach ($port in @(8000, 8001, 3000)) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        if ($connection.OwningProcess -gt 0) { $pids += [int]$connection.OwningProcess }
    }
}
# start_all.py 子进程之间使用 PID 作为 ParentProcessId，可通过进程树逐层收集，避免只停止监听端口
# 而把启动器或调度器留在后台。
$processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
$allIds = @($processes | ForEach-Object { [int]$_.ProcessId })
foreach ($processId in @($pids)) {
    $pending = [System.Collections.Generic.Queue[int]]::new()
    $pending.Enqueue([int]$processId)
    while ($pending.Count -gt 0) {
        $parentId = $pending.Dequeue()
        foreach ($child in $processes | Where-Object { [int]$_.ParentProcessId -eq $parentId }) {
            $childId = [int]$child.ProcessId
            if ($allIds -contains $childId -and $pids -notcontains $childId) {
                $pids += $childId
                $pending.Enqueue($childId)
            }
        }
    }
}
$pids = $pids | Where-Object { $_ -gt 0 } | Sort-Object -Unique
foreach ($processId in $pids) {
    & taskkill.exe /PID $processId /T /F 2>$null | Out-Null
}
Remove-Item -LiteralPath $stateFile -Force -ErrorAction SilentlyContinue
Write-Host '天枢开发版服务已停止。' -ForegroundColor Green
Read-Host '按回车关闭窗口'
