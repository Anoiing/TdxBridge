[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$PythonExe = "",
    [string]$BaseUrl = "",
    [string]$Token = ""
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

function Write-LogInfo {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-LogWarn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

if (-not $isWindowsHost) {
    throw "TdxBridge 当前只支持在 Windows 上运行这个调试入口。"
}

function Read-BridgeConfig {
    param(
        [string]$ConfigPath
    )

    if (-not (Test-Path $ConfigPath)) {
        return $null
    }

    try {
        return Get-Content $ConfigPath -Raw | ConvertFrom-Json
    } catch {
        throw "配置文件不是合法 JSON：$ConfigPath"
    }
}

function Test-PlaceholderToken {
    param(
        [string]$Value
    )

    return [string]::IsNullOrWhiteSpace($Value) -or $Value -eq "replace-with-generated-token" -or $Value -eq "auto-generated-token"
}

$configPath = Join-Path $ProjectRoot "config\bridge.json"
$config = Read-BridgeConfig -ConfigPath $configPath

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    if ($config -and $config.python_runtime -and $config.python_runtime.python_executable) {
        $PythonExe = [string]$config.python_runtime.python_executable
    } else {
        $PythonExe = "python"
    }
}

if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
    throw "未找到 Python 可执行文件：$PythonExe。"
}

$defaultPort = 18888
if ($config -and $config.server -and $config.server.port) {
    $defaultPort = [int]$config.server.port
}
$defaultBaseUrl = "http://127.0.0.1:$defaultPort"

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    $BaseUrl = Read-Host "请输入服务地址（直接回车使用默认值：$defaultBaseUrl）"
    if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
        $BaseUrl = $defaultBaseUrl
    }
}

$defaultToken = ""
if ($config -and $config.auth -and -not (Test-PlaceholderToken -Value ([string]$config.auth.token))) {
    $defaultToken = [string]$config.auth.token
}

if ([string]::IsNullOrWhiteSpace($Token)) {
    if ($defaultToken) {
        $maskedToken = if ($defaultToken.Length -gt 8) { $defaultToken.Substring(0, 4) + "..." + $defaultToken.Substring($defaultToken.Length - 4) } else { $defaultToken }
        Write-LogInfo "已从配置文件读取 Token：$maskedToken"
        $rawToken = Read-Host "直接回车使用这个 Token，或手动输入新的 Token"
        if ([string]::IsNullOrWhiteSpace($rawToken)) {
            $Token = $defaultToken
        } else {
            $Token = $rawToken
        }
    } else {
        while ([string]::IsNullOrWhiteSpace($Token)) {
            $Token = Read-Host "请输入 Bearer Token"
        }
    }
}

Write-Host ""
Write-LogInfo "TdxBridge 全接口调试即将开始。"
Write-LogWarn "说明：读接口会做真实联调；高副作用接口只做安全验证，不触发真实交易或写入。"
Write-LogInfo "服务地址：$BaseUrl"

& $PythonExe (Join-Path $ProjectRoot "scripts\debug_all_endpoints.py") `
    --project-root $ProjectRoot `
    --base-url $BaseUrl `
    --token $Token
