@echo off
set "APP_ROOT=%~dp0"
start "" /min "%APP_ROOT%runtime\powershell\pwsh.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%APP_ROOT%启动天枢离线版.ps1"
