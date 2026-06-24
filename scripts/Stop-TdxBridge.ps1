[CmdletBinding()]
param(
    [string]$ProjectRoot = ""
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

$runtimeDir = Join-Path $ProjectRoot "runtime"
$pidFile = Join-Path $runtimeDir "tdxbridge.pid"

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

if (-not (Test-Path $pidFile)) {
    Write-LogInfo "未检测到运行中的 TdxBridge 进程记录。"
    exit 0
}

$processIdText = (Get-Content $pidFile | Select-Object -First 1).Trim()
if (-not $processIdText) {
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    Write-LogWarn "PID 文件为空，已清理。"
    exit 0
}

$process = Get-Process -Id $processIdText -ErrorAction SilentlyContinue
if ($process) {
    Write-LogStep "停止服务进程"
    Write-LogInfo "目标进程：$processIdText"
    Stop-Process -Id $processIdText -Force -ErrorAction SilentlyContinue
    if (Get-Process -Id $processIdText -ErrorAction SilentlyContinue) {
        Write-LogWarn "停止进程命令已下发，但进程仍在运行，请手动确认。"
    } else {
        Write-LogSuccess "已停止 TdxBridge 进程。"
        Remove-Item $pidFile -ErrorAction SilentlyContinue
    }
} else {
    Write-LogWarn "未找到 PID=$processIdText 对应的进程，已清理 PID 文件。"
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}
