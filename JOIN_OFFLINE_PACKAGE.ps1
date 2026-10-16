# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
param(
    [string]$Destination = (Join-Path $PSScriptRoot 'MinerU-Tianshu-v2.2.1-fjy566.2'),
    [switch]$KeepArchive,
    [switch]$SkipDesktopShortcuts
)

$ErrorActionPreference = 'Stop'
$manifestPath = Join-Path $PSScriptRoot 'release-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw '同目录缺少 release-manifest.json。' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$archive = $manifest.archive
$parts = @($archive.parts)
if ($parts.Count -lt 1) { throw '发布清单没有分卷记录。' }
if ($archive.name -notmatch '^tianshu-v[0-9A-Za-z.+-]+-windows-offline\.zip$') { throw '发布清单中的 ZIP 文件名无效。' }
if ($archive.sha256 -notmatch '^[0-9a-f]{64}$' -or [long]$archive.bytes -le 0) { throw '发布清单中的 ZIP 校验字段无效。' }
foreach ($part in $parts) {
    if ($part.name -notmatch ('^' + [regex]::Escape($archive.name) + '\.part\d{3}$')) { throw "发布清单中的分卷文件名无效：$($part.name)" }
    if ($part.sha256 -notmatch '^[0-9a-f]{64}$' -or [long]$part.bytes -le 0) { throw "发布清单中的分卷校验字段无效：$($part.name)" }
}
$zipPath = Join-Path $PSScriptRoot $archive.name
if (Test-Path -LiteralPath $Destination) {
    if (@(Get-ChildItem -LiteralPath $Destination -Force).Count -gt 0) { throw "目标目录不为空：$Destination" }
} else {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
}

foreach ($part in $parts) {
    $partPath = Join-Path $PSScriptRoot $part.name
    if (-not (Test-Path -LiteralPath $partPath)) { throw "缺少分卷：$($part.name)" }
    $item = Get-Item -LiteralPath $partPath
    if ($item.Length -ne [long]$part.bytes) { throw "分卷大小错误：$($part.name)" }
    $actual = (Get-FileHash -LiteralPath $partPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $part.sha256) { throw "分卷 SHA-256 校验失败：$($part.name)" }
    Write-Host "校验通过：$($part.name)" -ForegroundColor Green
}

$output = [System.IO.File]::Open($zipPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try {
    $buffer = [byte[]]::new(4MB)
    foreach ($part in $parts) {
        $input = [System.IO.File]::OpenRead((Join-Path $PSScriptRoot $part.name))
        try { while (($read = $input.Read($buffer, 0, $buffer.Length)) -gt 0) { $output.Write($buffer, 0, $read) } }
        finally { $input.Dispose() }
    }
} finally { $output.Dispose() }

$zipItem = Get-Item -LiteralPath $zipPath
if ($zipItem.Length -ne [long]$archive.bytes) { throw '合并后的 ZIP 大小与发布清单不符。' }
$zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($zipHash -ne $archive.sha256) { throw '合并后的 ZIP SHA-256 校验失败。' }
Write-Host '分卷合并和 ZIP 校验通过，正在解压；大文件可能需要数分钟。' -ForegroundColor Cyan
Expand-Archive -LiteralPath $zipPath -DestinationPath $Destination -Force

$appRoot = (Resolve-Path -LiteralPath $Destination).Path
$pwsh = Join-Path $appRoot 'runtime\powershell\pwsh.exe'
$start = Join-Path $appRoot '启动天枢离线版.ps1'
$stop = Join-Path $appRoot '停止天枢离线版.ps1'
if (-not (Test-Path -LiteralPath $start) -or -not (Test-Path -LiteralPath $pwsh)) { throw '解压结果缺少离线启动运行时。' }

if (-not $SkipDesktopShortcuts) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    if ($desktop -and (Test-Path -LiteralPath $desktop)) {
        $shell = New-Object -ComObject WScript.Shell
        foreach ($entry in @(@{ Name = '天枢离线版.lnk'; Script = $start }, @{ Name = '停止天枢离线版.lnk'; Script = $stop })) {
            $link = $shell.CreateShortcut((Join-Path $desktop $entry.Name))
            $link.TargetPath = $pwsh
            $link.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + $entry.Script + '"'
            $link.WorkingDirectory = $appRoot
            $link.WindowStyle = 7
            $link.IconLocation = "$pwsh,0"
            $link.Save()
        }
    }
}

if (-not $KeepArchive) { Remove-Item -LiteralPath $zipPath -Force }
Write-Host "离线包已解压到：$appRoot" -ForegroundColor Green
if (-not $SkipDesktopShortcuts) { Write-Host '桌面快捷方式：天枢离线版 / 停止天枢离线版' -ForegroundColor Green }
Write-Host '首次启动会生成管理员账号，并弹窗显示密码。' -ForegroundColor Yellow
