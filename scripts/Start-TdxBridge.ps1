[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$PythonExe = ""
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

if (-not $isWindowsHost) {
    throw "TdxBridge 当前只支持在 Windows 上启动。"
}

function Write-LogInfo {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-LogWarn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-LogError {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-LogSuccess {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-LogStep {
    param([string]$Message)
    Write-Host "▶ $Message" -ForegroundColor White
}

function Write-ConfigSummary {
    param(
        [string]$Server,
        [int]$Port,
        [string]$ProjectRoot,
        [string]$StdoutLog,
        [string]$StderrLog
    )

    Write-LogInfo "服务启动参数汇总："
    Write-LogInfo ("  - 监听: http://{0}:{1}" -f $Server, $Port)
    Write-LogInfo ("  - 项目目录: {0}" -f $ProjectRoot)
    Write-LogInfo ("  - 日志: {0}" -f $StdoutLog)
    Write-LogInfo ("  - 错误日志: {0}" -f $StderrLog)
}

function Get-BridgeConfig {
    param(
        [string]$ConfigPath
    )

    if (-not (Test-Path $ConfigPath)) {
        throw "未找到配置文件：$ConfigPath"
    }

    try {
        return Get-Content $ConfigPath -Raw | ConvertFrom-Json
    } catch {
        throw "配置文件不是合法 JSON：$ConfigPath。请检查逗号、引号和大括号是否完整。"
    }
}

function Test-PlaceholderToken {
    param(
        [string]$Token
    )

    return [string]::IsNullOrWhiteSpace($Token) -or $Token -eq "replace-with-generated-token" -or $Token -eq "auto-generated-token"
}

function Write-ConfigWarnings {
    param(
        [object]$Config
    )

    if (-not $Config.network -or -not $Config.network.allowed_cidrs -or $Config.network.allowed_cidrs.Count -eq 0) {
        Write-LogWarn "当前未配置允许访问网段，服务默认只允许本机 127.0.0.1 访问。"
        Write-LogInfo "建议：先双击 00-右键管理员打开安装-TdxBridge.cmd，填写局域网来源白名单后再重启。"
    }

    if (-not $Config.tdx -or [string]::IsNullOrWhiteSpace([string]$Config.tdx.install_dir)) {
        Write-LogWarn "当前未配置通达信安装目录，局部功能（特别是健康检查/Python 通道）可能失败。"
        Write-LogInfo "建议：先双击 00-右键管理员打开安装-TdxBridge.cmd，或手动填写 config/bridge.json 的 tdx.install_dir。"
    }

    if (Test-PlaceholderToken -Token ([string]$Config.auth.token)) {
        Write-LogWarn "当前 auth.token 仍是占位值。"
        Write-LogInfo "建议：先双击 00-右键管理员打开安装-TdxBridge.cmd 生成随机 token，或手动修改 config/bridge.json。"
    }
}

$runtimeDir = Join-Path $ProjectRoot "runtime"
$logsDir = Join-Path $ProjectRoot "logs"
$configPath = Join-Path $ProjectRoot "config\bridge.json"
$pidFile = Join-Path $runtimeDir "tdxbridge.pid"
$stdoutLog = Join-Path $logsDir "service.stdout.log"
$stderrLog = Join-Path $logsDir "service.stderr.log"

if (-not (Test-Path $runtimeDir)) {
    New-Item -ItemType Directory -Path $runtimeDir | Out-Null
}
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

$config = Get-BridgeConfig -ConfigPath $configPath
Write-ConfigWarnings -Config $config
$serverHost = if ($config.server.host) { [string]$config.server.host } else { "0.0.0.0" }
$serverPort = if ($config.server.port) { [int]$config.server.port } else { 18888 }

if ($serverPort -lt 1 -or $serverPort -gt 65535) {
    throw "配置错误：server.port 必须在 1 到 65535 之间，当前值为 $serverPort。"
}
if ([string]::IsNullOrWhiteSpace($serverHost)) {
    throw "配置错误：server.host 不能为空。"
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    if ($config.python_runtime -and $config.python_runtime.python_executable) {
        $PythonExe = [string]$config.python_runtime.python_executable
    } else {
        $PythonExe = "python"
    }
}

if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
    throw "未找到 Python 可执行文件：$PythonExe。请先安装 Python，或修正 config/bridge.json 中的 python_runtime.python_executable。"
}

if (Test-Path $pidFile) {
    $existingPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($existingPid) {
        $existing = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($existing) {
            Write-LogSuccess "TdxBridge 已经在运行。"
            Write-LogInfo "进程号: $existingPid"
            Write-LogInfo "监听地址: http://127.0.0.1:$serverPort"
            exit 0
        }
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}

$startInfo = @{
    FilePath = $PythonExe
    ArgumentList = @("-m", "uvicorn", "app.main:app", "--host", $serverHost, "--port", "$serverPort")
    WorkingDirectory = $ProjectRoot
    RedirectStandardOutput = $stdoutLog
    RedirectStandardError = $stderrLog
    PassThru = $true
}

if ($isWindowsHost) {
    $startInfo.WindowStyle = "Hidden"
}

$process = Start-Process @startInfo
Write-LogStep ("正在拉起服务（目标: {0}:{1}）" -f $serverHost, $serverPort)
Start-Sleep -Seconds 1
if ($process.HasExited) {
    $stderrText = if (Test-Path $stderrLog) { Get-Content $stderrLog -Tail 20 -ErrorAction SilentlyContinue } else { @() }
    $stdoutText = if (Test-Path $stdoutLog) { Get-Content $stdoutLog -Tail 20 -ErrorAction SilentlyContinue } else { @() }
    if ($stderrText.Count -gt 0) {
        Write-LogError "启动失败，标准错误日志（最近 20 行）："
        Write-Host ($stderrText -join [Environment]::NewLine)
    }
    if ($stdoutText.Count -gt 0) {
        Write-LogWarn "启动失败，标准输出日志（最近 20 行）："
        Write-Host ($stdoutText -join [Environment]::NewLine)
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    throw "TdxBridge 启动进程已退出（退出码=$($process.ExitCode)）。请先检查上方日志。"
}

$process.Id | Set-Content -Path $pidFile -Encoding ascii

Write-LogSuccess ("TdxBridge 已启动，进程号：{0}" -f $process.Id)
Write-ConfigSummary -Server $serverHost -Port $serverPort -ProjectRoot $ProjectRoot -StdoutLog $stdoutLog -StderrLog $stderrLog
Write-LogInfo "若服务无法访问，请优先检查日志并确认端口与防火墙白名单。"
