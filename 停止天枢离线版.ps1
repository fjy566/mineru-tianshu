# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
param([switch]$Quiet)
$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$stateFile = Join-Path $root 'data\runtime\offline-pids.json'
$state = $null
if (Test-Path -LiteralPath $stateFile) { try { $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json } catch { } }
$processes = @(Get-CimInstance Win32_Process)
$ids = [System.Collections.Generic.HashSet[int]]::new()
if ($state) {
    foreach ($candidate in @($state.apiLauncherPid, $state.frontendPid)) {
        if (-not $candidate) { continue }
        $process = $processes | Where-Object { [int]$_.ProcessId -eq [int]$candidate } | Select-Object -First 1
        if ($process -and (($process.ExecutablePath -like "$root\runtime\*") -or ($process.CommandLine -like "*$root*"))) { [void]$ids.Add([int]$candidate) }
    }
    foreach ($port in @($state.apiPort, $state.workerPort, $state.frontendPort)) {
        if (-not $port) { continue }
        foreach ($connection in (Get-NetTCPConnection -LocalPort ([int]$port) -State Listen)) {
            $listener = $processes | Where-Object { [int]$_.ProcessId -eq [int]$connection.OwningProcess } | Select-Object -First 1
            if ($listener -and (($listener.ExecutablePath -like "$root\runtime\*") -or ($listener.CommandLine -like "*$root*"))) { [void]$ids.Add([int]$connection.OwningProcess) }
        }
    }
}

$pending = [System.Collections.Generic.Queue[int]]::new()
foreach ($id in $ids) { $pending.Enqueue($id) }
while ($pending.Count -gt 0) {
    $parent = $pending.Dequeue()
    foreach ($child in ($processes | Where-Object { [int]$_.ParentProcessId -eq $parent })) {
        $childId = [int]$child.ProcessId
        if ($childId -gt 0 -and $ids.Add($childId)) { $pending.Enqueue($childId) }
    }
}
foreach ($id in $ids) { & taskkill.exe /PID $id /T /F *> $null }
Remove-Item -LiteralPath $stateFile -Force
if (-not $Quiet) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show('天枢离线版服务已停止。', '天枢离线版', 'OK', 'Information') | Out-Null
    } catch { Write-Host '天枢离线版服务已停止。' }
}
