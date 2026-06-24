[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [switch]$KeepConfig,
    [switch]$KeepLogs
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [string]$ProjectRoot
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $scriptDir
}
$ProjectRoot = $ProjectRoot.Trim().Trim('"')
if ($ProjectRoot) {
    $ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
    if ($ProjectRoot.Length -gt 3) {
        $ProjectRoot = $ProjectRoot.TrimEnd('\', '/')
    }
}
$isWindowsHost = $env:OS -eq "Windows_NT"

$taskName = "TdxBridge"
$configPath = Join-Path $ProjectRoot "config\bridge.json"
$configDir = Join-Path $ProjectRoot "config"
$logsDir = Join-Path $ProjectRoot "logs"
$runtimeDir = Join-Path $ProjectRoot "runtime"

function Write-LogInfo {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-LogWarn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-LogSuccess {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-LogStep {
    param([string]$Message)
    Write-Host "▶ $Message" -ForegroundColor White
}

Write-LogStep "停止服务并清理进程记录"
try {
    & (Join-Path $ProjectRoot "scripts\Stop-TdxBridge.ps1") -ProjectRoot $ProjectRoot
} catch {
    Write-LogWarn ("停止服务失败（继续执行卸载）：{0}" -f $_.Exception.Message)
}

if ($isWindowsHost) {
    Write-LogInfo ("移除计划任务：{0}" -f $taskName)
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

    try {
        if (Test-Path $configPath) {
            $config = Get-Content $configPath -Raw | ConvertFrom-Json
            $port = if ($config.server.port) { [int]$config.server.port } else { 18888 }
            $ruleName = "TdxBridge-$port"
            Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Out-Null
        }
    } catch {
    }
}

Write-LogStep "清理安装目录"
if (-not $KeepConfig -and (Test-Path $configDir)) {
    Write-LogWarn ("删除配置目录：{0}" -f $configDir)
    Remove-Item $configDir -Recurse -Force
} else {
    Write-LogInfo ("保留配置目录：{0}" -f $configDir)
}

if (-not $KeepLogs -and (Test-Path $logsDir)) {
    Write-LogWarn ("删除日志目录：{0}" -f $logsDir)
    Remove-Item $logsDir -Recurse -Force
} else {
    Write-LogInfo ("保留日志目录：{0}" -f $logsDir)
}

if (Test-Path $runtimeDir) {
    Write-LogWarn ("删除运行时目录：{0}" -f $runtimeDir)
    Remove-Item $runtimeDir -Recurse -Force
} else {
    Write-LogInfo ("运行时目录不存在，无需清理：{0}" -f $runtimeDir)
}

Write-LogSuccess "TdxBridge 卸载完成。"
if ($isWindowsHost) {
    Write-LogInfo "计划任务：$taskName 已移除（若已不存在则跳过）。"
}
if ($KeepConfig) {
    Write-LogInfo "配置目录已保留：$configDir"
} else {
    Write-LogWarn "配置目录已清理：$configDir"
}
if ($KeepLogs) {
    Write-LogInfo "日志目录已保留：$logsDir"
} else {
    Write-LogWarn "日志目录已清理：$logsDir"
}
if (Test-Path $runtimeDir) {
    Write-LogWarn "运行时目录仍存在，请确认是否有外部进程持有权限。"
} else {
    Write-LogSuccess "运行时目录已清理：$runtimeDir"
}
