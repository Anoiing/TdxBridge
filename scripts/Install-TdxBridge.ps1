[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$PythonExe = "python",
    [switch]$SkipDependencyInstall,
    [bool]$GenerateAgentFiles = $true
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
$script:StepIndex = 0
$script:InstallerTempDir = $null

[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [Console]::OutputEncoding

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

function Write-Step {
    param(
        [string]$Title
    )

    $script:StepIndex += 1
    Write-Host ""
    Write-Host ("========== 步骤 {0} ==========" -f $script:StepIndex) -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Cyan
}

function Write-Detail {
    param(
        [string]$Message
    )

    Write-LogInfo $Message
}

function Write-Utf8NoBomFile {
    param(
        [string]$Path,
        [string]$Content
    )

    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }

    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Get-DefaultBridgeConfigJson {
    return @"
{
  "server": {
    "host": "0.0.0.0",
    "port": 18888
  },
  "local_rpc": {
    "base_url": "http://127.0.0.1:17709/",
    "timeout_sec": 15
  },
  "auth": {
    "token": "replace-with-generated-token",
    "allow_anonymous_health": true,
    "allow_anonymous_capabilities": false
  },
  "network": {
    "allowed_cidrs": []
  },
  "tdx": {
    "install_dir": ""
  },
  "python_runtime": {
    "mode": "subprocess-per-call",
    "timeout_sec": 20,
    "python_executable": "python"
  },
  "risk_control": {
    "enable_trading": false,
    "enable_block_push": false,
    "enable_warn_send": false,
    "enable_backtest_send": false
  },
  "logging": {
    "level": "INFO",
    "retain_days": 14
  }
}
"@
}

function Ensure-BridgeConfigFile {
    param(
        [string]$ConfigDir,
        [string]$ConfigPath,
        [string]$ExampleConfigPath
    )

    if (-not (Test-Path $ConfigDir)) {
        New-Item -ItemType Directory -Path $ConfigDir | Out-Null
        Write-Detail "已补建配置目录：$ConfigDir"
    }

    if (Test-Path $ConfigPath) {
        return
    }

    if (Test-Path $ExampleConfigPath) {
        Copy-Item $ExampleConfigPath $ConfigPath
        Write-Detail "已从示例配置初始化 bridge.json"
        return
    }

    Write-Utf8NoBomFile -Path $ConfigPath -Content (Get-DefaultBridgeConfigJson)
    Write-Detail "未找到示例配置，已自动生成默认 bridge.json"
}

function New-InstallerTempWorkspace {
    param(
        [string]$ProjectRoot
    )

    $runtimeDir = Join-Path $ProjectRoot "runtime"
    if (-not (Test-Path $runtimeDir)) {
        New-Item -ItemType Directory -Path $runtimeDir | Out-Null
    }

    $tempDir = Join-Path $runtimeDir "install-temp"
    if (Test-Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $tempDir "pip-cache") | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $tempDir "home") | Out-Null
    return $tempDir
}

function Remove-InstallerTempWorkspace {
    param(
        [string]$TempDir
    )

    if ([string]::IsNullOrWhiteSpace($TempDir)) {
        return
    }

    if (Test-Path $TempDir) {
        Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-WithInstallerTempEnv {
    param(
        [string]$TempDir,
        [scriptblock]$ScriptBlock
    )

    $envNames = @(
        "TEMP",
        "TMP",
        "TMPDIR",
        "PIP_CACHE_DIR",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_STATE_HOME",
        "HOME"
    )
    $backup = @{}
    foreach ($name in $envNames) {
        $backup[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    }

    $homeDir = Join-Path $TempDir "home"
    [Environment]::SetEnvironmentVariable("TEMP", $TempDir, "Process")
    [Environment]::SetEnvironmentVariable("TMP", $TempDir, "Process")
    [Environment]::SetEnvironmentVariable("TMPDIR", $TempDir, "Process")
    [Environment]::SetEnvironmentVariable("PIP_CACHE_DIR", (Join-Path $TempDir "pip-cache"), "Process")
    [Environment]::SetEnvironmentVariable("XDG_CACHE_HOME", $TempDir, "Process")
    [Environment]::SetEnvironmentVariable("XDG_CONFIG_HOME", $homeDir, "Process")
    [Environment]::SetEnvironmentVariable("XDG_STATE_HOME", $TempDir, "Process")
    [Environment]::SetEnvironmentVariable("HOME", $homeDir, "Process")

    try {
        & $ScriptBlock
    } finally {
        foreach ($name in $envNames) {
            [Environment]::SetEnvironmentVariable($name, $backup[$name], "Process")
        }
    }
}

function Assert-WindowsHost {
    if (-not $isWindowsHost) {
        throw "TdxBridge 当前只支持在 Windows 上安装和运行。"
    }
}

function Get-DetectedTdxInstallDir {
    param(
        [string]$ProjectRoot,
        [string]$PythonExe
    )

    $helperScript = Join-Path $ProjectRoot "app\install_runtime.py"
    $raw = Invoke-WithInstallerTempEnv -TempDir $script:InstallerTempDir -ScriptBlock {
        & $PythonExe $helperScript detect_tdx 2>$null
    }
    if (-not $raw) {
        return $null
    }

    try {
        return ($raw | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Test-TdxInstallDir {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }

    if (-not (Test-Path $Path -PathType Container)) {
        return $false
    }

    $tdxw = Join-Path $Path "TdxW.exe"
    $tqcenter = Join-Path $Path "PYPlugins\user\tqcenter.py"
    $tpyth = Join-Path $Path "PYPlugins\TPyth.dll"
    $tpythClient = Join-Path $Path "PYPlugins\TPythClient.dll"

    return (Test-Path $tdxw) -or (Test-Path $tqcenter) -or (Test-Path $tpyth) -or (Test-Path $tpythClient)
}

function Resolve-TdxInstallDir {
    param(
        [string]$ProjectRoot,
        [string]$PythonExe
    )

    $detectedInfo = Get-DetectedTdxInstallDir -ProjectRoot $ProjectRoot -PythonExe $PythonExe
    if ($detectedInfo -and $detectedInfo.detected) {
        Write-LogSuccess ("已自动探测到通达信目录：{0}" -f $detectedInfo.detected)
        return [string]$detectedInfo.detected
    }

    Write-LogWarn "未自动探测到通达信安装目录。"
    Write-LogInfo "已尝试以下常见目录："

    if ($detectedInfo -and $detectedInfo.candidates) {
        foreach ($candidate in $detectedInfo.candidates) {
            Write-Detail (" - {0}" -f $candidate)
        }
    } else {
        Write-Detail " - 当前 TdxBridge 目录的父级目录"
        Write-Detail " - 当前 TdxBridge 目录的同级目录"
        Write-Detail " - 各盘符根目录下的 \\new_tdx64 和 \\tdx64"
        Write-Detail " - 各盘符下的 \\Program Files\\new_tdx64 和 \\Program Files\\tdx64"
        Write-Detail " - 各盘符下的 \\Program Files (x86)\\new_tdx64 和 \\Program Files (x86)\\tdx64"
    }

    while ($true) {
        $manualPath = Read-Host "请输入通达信安装目录"
        if (Test-TdxInstallDir -Path $manualPath) {
            return $manualPath
        }
        Write-LogWarn "输入的目录无效，目录必须存在，并至少包含 TdxW.exe 或 PYPlugins 相关文件。"
    }
}

function New-RandomToken {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $token = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    return $token
}

function Get-LanIPv4Address {
    if (-not $isWindowsHost) {
        return "127.0.0.1"
    }

    if (Get-Command Get-NetIPAddress -ErrorAction SilentlyContinue) {
        $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object {
                $_.IPAddress -and
                $_.IPAddress -ne "127.0.0.1" -and
                $_.IPAddress -notlike "169.254.*"
            } |
            Sort-Object -Property InterfaceMetric, SkipAsSource |
            Select-Object -First 1 -ExpandProperty IPAddress
        if ($ip) {
            return $ip
        }
    }

    try {
        $hostEntry = [System.Net.Dns]::GetHostEntry([System.Net.Dns]::GetHostName())
        $fallbackIp = $hostEntry.AddressList |
            Where-Object { $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and $_.IPAddressToString -ne "127.0.0.1" } |
            Select-Object -First 1
        if ($fallbackIp) {
            return $fallbackIp.IPAddressToString
        }
    } catch {
    }

    return "127.0.0.1"
}

function Get-DefaultCidrSuggestion {
    $lanIp = Get-LanIPv4Address
    if ($lanIp -match '^(\d+)\.(\d+)\.(\d+)\.\d+$') {
        return "$($matches[1]).$($matches[2]).$($matches[3]).0/24"
    }
    return "192.168.1.0/24"
}

function Test-CidrValue {
    param(
        [string]$Value,
        [string]$PythonExe
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }

    $helperScript = Join-Path $ProjectRoot "app\install_runtime.py"
    Invoke-WithInstallerTempEnv -TempDir $script:InstallerTempDir -ScriptBlock {
        & $PythonExe $helperScript validate_cidr $Value 2>$null | Out-Null
    }
    return $LASTEXITCODE -eq 0
}

function Get-RuntimeDependencyStatus {
    param(
        [string]$ProjectRoot,
        [string]$PythonExe
    )

    $helperScript = Join-Path $ProjectRoot "app\install_runtime.py"
    $raw = Invoke-WithInstallerTempEnv -TempDir $script:InstallerTempDir -ScriptBlock {
        & $PythonExe $helperScript check_runtime_deps 2>$null
    }
    if (-not $raw) {
        return $null
    }

    try {
        return ($raw | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Invoke-PipInstallDirectPackage {
    param(
        [string]$PythonExe,
        [string]$Requirement
    )

    if ([string]::IsNullOrWhiteSpace($Requirement)) {
        throw "缺少 requirement 参数。"
    }

    $proxyEnvNames = @(
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "PIP_INDEX_URL",
        "PIP_EXTRA_INDEX_URL",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
        "PIP_PROXY",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE"
    )
    $backup = @{}

    foreach ($name in $proxyEnvNames) {
        $value = [Environment]::GetEnvironmentVariable($name, "Process")
        if ($null -ne $value) {
            $backup[$name] = $value
        }
        [Environment]::SetEnvironmentVariable($name, $null, "Process")
    }

    try {
        Write-Detail "本次安装强制直连官方 PyPI，不使用本机代理配置"
        Invoke-WithInstallerTempEnv -TempDir $script:InstallerTempDir -ScriptBlock {
            & $PythonExe -m pip install `
                --isolated `
                --disable-pip-version-check `
                --index-url "https://pypi.org/simple" `
                --trusted-host "pypi.org" `
                --trusted-host "files.pythonhosted.org" `
                --proxy "" `
                --retries 1 `
                --timeout 15 `
                --no-cache-dir `
                $Requirement
        }
        if ($LASTEXITCODE -ne 0) {
            throw "pip 返回退出码 $LASTEXITCODE"
        }
    } finally {
        foreach ($name in $proxyEnvNames) {
            [Environment]::SetEnvironmentVariable($name, $null, "Process")
        }
        foreach ($entry in $backup.GetEnumerator()) {
            [Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, "Process")
        }
    }
}

function Resolve-AllowedCidrs {
    param(
        [string]$PythonExe
    )

    $suggestion = Get-DefaultCidrSuggestion
    Write-LogInfo "请设置允许访问 TdxBridge 的局域网来源网段。"
    Write-Detail "默认值会使用当前设备所在局域网段。"
    Write-Detail "多个网段可用英文逗号分隔。"
    Write-Detail ("默认值：{0}" -f $suggestion)
    Write-Detail ("示例：{0}" -f $suggestion)

    while ($true) {
        $rawInput = Read-Host "请输入允许访问网段（直接回车使用默认值）"
        if ([string]::IsNullOrWhiteSpace($rawInput)) {
            $rawInput = $suggestion
            Write-LogInfo "未填写，已使用默认值。"
        }

        $cidrs = @(
            $rawInput -split "," |
                ForEach-Object { $_.Trim() } |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        )

        if (-not $cidrs -or $cidrs.Count -eq 0) {
            Write-LogWarn "至少需要填写一个 CIDR 网段。"
            continue
        }

        $invalid = @()
        foreach ($cidr in $cidrs) {
            if (-not (Test-CidrValue -Value $cidr -PythonExe $PythonExe)) {
                $invalid += $cidr
            }
        }

        if ($invalid.Count -eq 0) {
            return $cidrs
        }

        Write-LogWarn ("以下 CIDR 格式不合法：{0}" -f ($invalid -join ', '))
    }
}

function Ensure-FirewallRule {
    param(
        [int]$Port,
        [string[]]$AllowedCidrs
    )

    if (-not $isWindowsHost) {
        return @{
            ok = $false
            ruleName = "TdxBridge-$Port"
            message = "当前不是 Windows，已跳过防火墙规则配置。"
        }
    }

    if (-not (Get-Command Get-NetFirewallRule -ErrorAction SilentlyContinue)) {
        return @{
            ok = $false
            ruleName = "TdxBridge-$Port"
            message = "当前系统不可用防火墙命令，已跳过自动配置防火墙规则。"
        }
    }

    $ruleName = "TdxBridge-$Port"
    try {
        $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
        if ($existingRule) {
            Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Out-Null
        }

        New-NetFirewallRule `
            -DisplayName $ruleName `
            -Direction Inbound `
            -Action Allow `
            -Protocol TCP `
            -Profile Private `
            -LocalPort $Port `
            -RemoteAddress $AllowedCidrs | Out-Null
        return @{
            ok = $true
            ruleName = $ruleName
            message = "已成功配置 Windows 防火墙入站规则。"
        }
    } catch {
        return @{
            ok = $false
            ruleName = $ruleName
            message = "防火墙规则配置失败：$($_.Exception.Message)"
        }
    }
}

function Ensure-ObjectProperty {
    param(
        [object]$Target,
        [string]$Name,
        [object]$Value
    )

    if (-not $Target.PSObject.Properties[$Name]) {
        $Target | Add-Member -MemberType NoteProperty -Name $Name -Value $Value
    }
}

function Test-TdxClientRunning {
    $process = Get-Process -Name "TdxW" -ErrorAction SilentlyContinue | Select-Object -First 1
    return $null -ne $process
}

function Ensure-TdxClientRunningBeforeHealth {
    param(
        [string]$TdxInstallDir
    )

    if (Test-TdxClientRunning) {
        Write-Detail "检测到通达信客户端已启动。"
        return
    }

    $tdxExecutablePath = Join-Path $TdxInstallDir "TdxW.exe"
    if ([string]::IsNullOrWhiteSpace($TdxInstallDir) -or -not (Test-Path $tdxExecutablePath -PathType Leaf)) {
        throw "未找到通达信客户端 TdxW.exe，无法在健康检查前自动启动。请确认通达信安装目录是否正确。"
    }

    Write-Detail "检测到通达信客户端未启动，正在自动启动。"
    Start-Process -FilePath $tdxExecutablePath -WorkingDirectory $TdxInstallDir | Out-Null
    Write-Detail "已发起启动，等待 30 秒让通达信完成初始化。"
    Start-Sleep -Seconds 30
}

function Ensure-TdxClientAutoStartPrompt {
    param(
        [string]$TdxInstallDir
    )

    $tdxExecutablePath = Join-Path $TdxInstallDir "TdxW.exe"
    if ([string]::IsNullOrWhiteSpace($TdxInstallDir) -or -not (Test-Path $tdxExecutablePath -PathType Leaf)) {
        Write-Detail "未找到 TdxW.exe，已跳过通达信客户端开机自启设置。"
        return @{
            enabled = $false
            skipped = $true
            startupPath = ""
        }
    }

    $answer = Read-Host "健康检查已完成。是否将通达信客户端设为当前用户开机自启？输入 Y 确认，直接回车跳过"
    if ($answer -notmatch '^(?i:y|yes)$') {
        Write-Detail "已跳过通达信客户端开机自启设置。"
        return @{
            enabled = $false
            skipped = $true
            startupPath = ""
        }
    }

    $startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
    $startupShortcutPath = Join-Path $startupDir "通达信客户端.lnk"
    $legacyStartupScriptPath = Join-Path $startupDir "TdxBridge-通达信客户端自启.cmd"

    if (-not (Test-Path $startupDir)) {
        New-Item -ItemType Directory -Path $startupDir -Force | Out-Null
    }

    if (Test-Path $legacyStartupScriptPath) {
        Remove-Item -Path $legacyStartupScriptPath -Force -ErrorAction SilentlyContinue
    }

    $wshShell = New-Object -ComObject WScript.Shell
    $shortcut = $wshShell.CreateShortcut($startupShortcutPath)
    $shortcut.TargetPath = $tdxExecutablePath
    $shortcut.WorkingDirectory = $TdxInstallDir
    $shortcut.WindowStyle = 1
    $shortcut.Description = "通达信客户端开机自启"
    $shortcut.Save()

    Write-Detail "已添加当前用户开机自启快捷方式：$startupShortcutPath"
    return @{
        enabled = $true
        skipped = $false
        startupPath = $startupShortcutPath
    }
}

function Wait-ForHealth {
    param(
        [int]$Port,
        [int]$MaxAttempts = 30,
        [int]$SleepSeconds = 1,
        [int]$RequestTimeoutSec = 2
    )

    $url = "http://127.0.0.1:$Port/health"
    Write-Detail ("开始检查服务健康状态：{0}" -f $url)
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        Write-Detail ("健康检查进度：第 {0}/{1} 次" -f $attempt, $MaxAttempts)
        try {
            $response = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $RequestTimeoutSec
            Write-LogSuccess ("健康检查已通过：第 {0}/{1} 次" -f $attempt, $MaxAttempts)
            return $response
        } catch {
            $reason = if ($_.Exception -and $_.Exception.Message) { $_.Exception.Message } else { "服务暂未就绪" }
            if ($attempt -lt $MaxAttempts) {
                Write-LogWarn ("健康检查未通过：{0}" -f $reason)
                Write-Detail ("{0} 秒后继续重试" -f $SleepSeconds)
                Start-Sleep -Seconds $SleepSeconds
            }
        }
    }
    Write-LogError "健康检查超时，已达到最大重试次数。"
    return $null
}

function Get-RecentLogLines {
    param(
        [string]$Path,
        [int]$Lines = 20
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path $Path)) {
        return @()
    }

    try {
        return @(Get-Content -Path $Path -Tail $Lines -ErrorAction Stop)
    } catch {
        return @()
    }
}

function Write-HealthFailureDiagnostics {
    param(
        [string]$ProjectRoot,
        [int]$Port
    )

    $runtimeDir = Join-Path $ProjectRoot "runtime"
    $logsDir = Join-Path $ProjectRoot "logs"
    $pidFile = Join-Path $runtimeDir "tdxbridge.pid"
    $stdoutLog = Join-Path $logsDir "service.stdout.log"
    $stderrLog = Join-Path $logsDir "service.stderr.log"

    Write-LogWarn "诊断信息："
    Write-LogInfo " - 健康检查地址：http://127.0.0.1:$Port/health"
    Write-LogInfo " - 标准输出日志：$stdoutLog"
    Write-LogInfo " - 标准错误日志：$stderrLog"

    if (Test-Path $pidFile) {
        $pidText = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
        if ($pidText) {
            $process = Get-Process -Id $pidText -ErrorAction SilentlyContinue
            if ($process) {
                Write-LogInfo " - 后台进程状态：运行中（PID=$pidText）"
            } else {
                Write-LogWarn " - 后台进程状态：未运行（PID 文件存在，但进程已退出）"
            }
        } else {
            Write-LogWarn " - 后台进程状态：PID 文件存在，但内容为空"
        }
    } else {
        Write-LogWarn " - 后台进程状态：未生成 PID 文件"
    }

    $stdoutLines = Get-RecentLogLines -Path $stdoutLog -Lines 20
    if ($stdoutLines.Count -gt 0) {
        Write-LogWarn ""
        Write-LogWarn "最近的标准输出日志："
        foreach ($line in $stdoutLines) {
            Write-Host $line
        }
    }

    $stderrLines = Get-RecentLogLines -Path $stderrLog -Lines 20
    if ($stderrLines.Count -gt 0) {
        Write-LogWarn ""
        Write-LogWarn "最近的标准错误日志："
        foreach ($line in $stderrLines) {
            Write-Host $line
        }
    }
}

function New-AgentConnectionPrompt {
    param(
        [string]$ServiceUrl,
        [string]$Token,
        [string]$AllowedCidrsText,
        [string]$TdxInstallDir,
        [string]$TaskName,
        [string]$ProjectRoot,
        [object]$Health
    )

    $healthStatus = "未通过"
    $tdxProcessRunning = "未知"
    $localRpcReachable = "未知"
    if ($Health) {
        $healthStatus = "通过"
        if ($Health.checks) {
            $tdxProcessRunning = [string]$Health.checks.tdxProcessRunning
            $localRpcReachable = [string]$Health.checks.localRpcReachable
        }
    }

    return @"
请帮我联调这个 TdxBridge 服务。

- 服务地址：$ServiceUrl
- Bearer Token：$Token
- 完整接口文档：$ServiceUrl/doc
- 智能体接入文档：给Hermes和OpenClaw的TdxBridge接入文档.md
- 通达信目录：$TdxInstallDir
- 健康检查：$healthStatus
- TdxW.exe：$tdxProcessRunning
- 17709：$localRpcReachable

先读取：
1. GET $ServiceUrl/doc
2. 给Hermes和OpenClaw的TdxBridge接入文档.md

在发起任何业务请求前，先做两个前置检查：
1. 确认 Windows 用户已经登录桌面
2. 确认 TdxW.exe 已经启动；如果未启动，先启动通达信客户端，再继续联调

如果需要长期稳定使用，还要额外确认：
- 通达信客户端是否已开启“开机登录后自动启动”
- 如果没有开启，提醒用户先配置通达信客户端开机自启，再把 TdxBridge 交给智能体持续使用

请按这个顺序验证，并输出每一步的请求、状态码和结果摘要：
1. GET $ServiceUrl/health
2. GET $ServiceUrl/doc
3. GET $ServiceUrl/capabilities
4. POST $ServiceUrl/stock/search  body={"keyword":"寒武纪"}
5. POST $ServiceUrl/rpc/python  body={"method":"get_user_sector","params":{}}
6. POST $ServiceUrl/rpc/python  body={"method":"get_stock_list","params":{}}

请求默认带：
Authorization: Bearer $Token

如果失败，请优先排查：
- 服务地址
- Token
- Windows 登录状态
- TdxW.exe
- 127.0.0.1:17709
- 防火墙或白名单限制

不要调用这些高风险接口：
- /trade/order
- /trade/cancel
- /warn/send
- /backtest/send
- /blocks/push

这份 txt 只是快速引导卡，不是完整接口手册。完整说明统一以 /doc 和接入文档为准。

直接开始，不要先反问我。
"@
}

function Write-AgentConnectionPromptFile {
    param(
        [string]$ProjectRoot,
        [string]$Content
    )

    $promptPath = Join-Path $ProjectRoot "给Hermes和OpenClaw的连接提示.txt"
    Write-Utf8NoBomFile -Path $promptPath -Content $Content
    return $promptPath
}

function New-AgentGuideDocument {
    param(
        [string]$ServiceUrl,
        [string]$Token,
        [string]$AllowedCidrsText,
        [string]$TdxInstallDir,
        [string]$TaskName,
        [string]$ProjectRoot,
        [object]$Health
    )

    $healthStatus = "未通过"
    $tdxProcessRunning = "未知"
    $localRpcReachable = "未知"
    if ($Health) {
        $healthStatus = "通过"
        if ($Health.checks) {
            $tdxProcessRunning = [string]$Health.checks.tdxProcessRunning
            $localRpcReachable = [string]$Health.checks.localRpcReachable
        }
    }

    return @"
# TdxBridge 接入文档（给 Hermes / OpenClaw 智能体）

## 1. 目标

你现在面对的是一台 Windows 上已经安装完成的 TdxBridge 服务。你的任务是：

1. 自动验证服务是否可达
2. 自动验证认证是否正确
3. 自动做低副作用联调
4. 在不触发真实交易或写入副作用的前提下，给出接入建议

## 2. 当前实例信息

- 服务地址：`$ServiceUrl`
- Bearer Token：`$Token`
- 完整接口文档：`$ServiceUrl/doc`
- 项目目录：`$ProjectRoot`
- 通达信目录：`$TdxInstallDir`
- 允许访问网段：`$AllowedCidrsText`
- Windows 计划任务：`$TaskName`
- 安装阶段健康检查：`$healthStatus`
- TdxW.exe 运行状态：`$tdxProcessRunning`
- 17709 本地 RPC 连通状态：`$localRpcReachable`

## 3. 认证方式

除 `/health` 可能允许匿名外，其余请求统一按下面方式带认证头：

```http
Authorization: Bearer $Token
Content-Type: application/json
```

## 4. 推荐调试顺序

请严格按下面顺序联调：

0. 先确认 Windows 用户已登录桌面，且 `TdxW.exe` 已经运行；如果没有运行，先启动通达信客户端
1. `GET /health`
2. `GET /doc`
3. `GET /capabilities`
4. `POST /stock/search`
5. `POST /rpc/python` with `get_user_sector`
6. `POST /rpc/python` with `get_stock_list`

如果前一步失败，不要跳到后面的大请求，先定位失败原因。

## 5. 信息源优先级

请按下面顺序读取信息，不要把多份文档都当成完整接口总表：

1. `GET /doc`
2. `GET /capabilities`
3. 当前这份接入文档
4. `给Hermes和OpenClaw的连接提示.txt`

说明：

- `/doc` 是接口总表和参数入口的主文档
- `/capabilities` 是当前实例的动态能力快照
- 当前这份接入文档只负责“怎么接入、先做什么、哪些不能碰”
- `连接提示.txt` 只是方便复制给智能体的极简引导卡，不再重复完整接口清单

## 6. 运行前置条件

在调用任何业务接口前，请先检查下面几点：

1. Windows 用户是否已经登录桌面
2. 通达信客户端 `TdxW.exe` 是否已经运行
3. 本地 `127.0.0.1:17709` 是否可达

如果 `TdxW.exe` 没启动：

1. 先启动通达信客户端
2. 等客户端完全进入可用状态
3. 再重新执行 `GET /health`

如果要长期稳定给智能体使用，还要检查通达信客户端开机自启：

1. 查看安装完成摘要里是否出现 `通达信客户端开机自启：已开启`
2. 如果摘要里显示 `未开启`，提醒用户先在这台 Windows 机器上完成通达信客户端开机自启配置
3. 如果安装摘要里打印了 `开机自启脚本` 路径，优先按该路径对应的脚本或快捷方式完成开机自启
4. 在未确认开机自启前，不要把 TdxBridge 当成“重启后一定可自动恢复”的稳定服务

## 7. 接口总表入口

完整接口文档请优先读取：

### `GET /doc`

用途：查看当前 bridge 的完整接口总表、参数入口、底层 method 映射、统一响应结构和风险边界。

示例：

```bash
curl -X GET "$ServiceUrl/doc" ^
  -H "Authorization: Bearer $Token"
```

## 8. 可安全优先调用的接口

### 8.1 健康与能力

#### `GET /health`

用途：检查服务是否存活，并查看 Windows / 通达信 / 本地 RPC 状态。

示例：

```bash
curl -X GET "$ServiceUrl/health" ^
  -H "Authorization: Bearer $Token"
```

#### `GET /capabilities`

用途：查看当前实例支持的方法、运行模式、风控状态、白名单和 warnings。

示例：

```bash
curl -X GET "$ServiceUrl/capabilities" ^
  -H "Authorization: Bearer $Token"
```

### 8.2 低副作用业务验证

#### `POST /stock/search`

用途：验证 TQ-Local 通路是否可用。

请求体：

```json
{"keyword":"寒武纪"}
```

#### `POST /rpc/python`

用途：验证 TQ-Python 子进程通路是否可用。

请求体 1：

```json
{"method":"get_user_sector","params":{}}
```

请求体 2：

```json
{"method":"get_stock_list","params":{}}
```

注意：`get_stock_list` 返回可能很大，请只输出结果摘要、数量或前几项，不要整份展开。

## 9. 写接口禁区

除非用户明确授权，否则不要调用以下高风险或真实副作用接口：

- `POST /trade/order`
- `POST /trade/cancel`
- `POST /warn/send`
- `POST /backtest/send`
- `POST /blocks/push`

以及底层真实动作：

- `order_stock`
- `cancel_order_stock`
- `send_warn`
- `send_bt_data`

完整接口总表、底层 method 映射、请求入口和风险边界统一以 `/doc` 为准，这里不再重复列一次。

## 10. 推荐排障顺序

如果请求失败，请按下面顺序排查：

1. 服务地址是否可达
2. Token 是否正确
3. `GET /health` 是否能返回
4. `TdxW.exe` 是否正在运行
5. 通达信客户端开机自启是否已经配置；如果机器重启后经常失效，优先回到这里排查
6. `127.0.0.1:17709` 是否可达
7. `/capabilities` 中 `pythonRuntime.mode` 是否为 `subprocess-per-call`
8. `warnings` 是否提示缺少目录、占位 token 或白名单问题
9. Windows 登录状态、防火墙和来源网段是否拦截

## 11. 输出要求

请在每一步都输出：

1. 请求方法
2. 完整 URL
3. 请求头
4. 请求体
5. HTTP 状态码
6. 返回结果摘要
7. 你的判断结论

## 12. 接入建议输出要求

如果低副作用接口全部通过，请继续给出：

1. Hermes / OpenClaw 推荐使用的 base URL
2. 认证头写法
3. 建议默认开放的只读工具
4. 需要人工确认后再开放的高风险工具
5. 通达信客户端是否已经启动
6. 通达信客户端开机自启是否已经配置完成；如果没有，请明确标成运行前置风险

## 13. 执行约束

请直接开始联调，不要先反问用户。
在没有得到明确授权前，不要调用任何真实交易、写入板块、发送预警或发送回测数据的接口。
"@
}

function Write-AgentGuideDocumentFile {
    param(
        [string]$ProjectRoot,
        [string]$Content
    )

    $docPath = Join-Path $ProjectRoot "给Hermes和OpenClaw的TdxBridge接入文档.md"
    Write-Utf8NoBomFile -Path $docPath -Content $Content
    return $docPath
}

Assert-WindowsHost

try {
    Write-Host ""
    Write-LogSuccess "TdxBridge 安装程序已启动。"
    Write-LogInfo "按屏幕提示完成安装，完成后可直接关闭窗口，后台服务会继续运行。"

    $configDir = Join-Path $ProjectRoot "config"
    $logsDir = Join-Path $ProjectRoot "logs"
    $runtimeDir = Join-Path $ProjectRoot "runtime"
    $configPath = Join-Path $configDir "bridge.json"
    $exampleConfigPath = Join-Path $configDir "bridge.example.json"
    $startScript = Join-Path $ProjectRoot "scripts\Start-TdxBridge.ps1"

    Write-Step "准备运行目录与基础配置文件"
    foreach ($path in @($configDir, $logsDir, $runtimeDir)) {
        if (-not (Test-Path $path)) {
            New-Item -ItemType Directory -Path $path | Out-Null
            Write-Detail "已创建目录：$path"
        }
    }
    $script:InstallerTempDir = New-InstallerTempWorkspace -ProjectRoot $ProjectRoot
    Write-Detail "安装临时目录：$script:InstallerTempDir"
    Write-Detail "安装结束后会自动清理该临时目录"

    Ensure-BridgeConfigFile -ConfigDir $configDir -ConfigPath $configPath -ExampleConfigPath $exampleConfigPath

    Write-Step "检查 Python 运行环境"
    if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
        throw "未找到 Python 可执行文件：$PythonExe。请先安装 Python，或传入正确的 -PythonExe 参数。"
    }
    Write-Detail "检测到 Python：$PythonExe"

if (-not $SkipDependencyInstall) {
    Write-Step "检查并安装 Python 依赖"
    $dependencyStatus = Get-RuntimeDependencyStatus -ProjectRoot $ProjectRoot -PythonExe $PythonExe
    if (-not $dependencyStatus) {
        throw "无法读取 Python 依赖检查结果，请确认 app/install_runtime.py 可正常执行。"
    }

    Write-Detail ("依赖总数：{0}，已安装：{1}，缺失：{2}" -f $dependencyStatus.total, $dependencyStatus.installed_count, $dependencyStatus.missing_count)
    foreach ($dep in $dependencyStatus.deps) {
        if ($dep.installed -and $dep.requirement_satisfied) {
            $versionText = if ($dep.version) { "，版本：$($dep.version)" } else { "" }
            Write-Detail ("已安装：{0}{1}" -f $dep.name, $versionText)
        } else {
            Write-Detail ("待安装：{0} -> {1}" -f $dep.name, $dep.requirement)
        }
    }

    if (-not $dependencyStatus.ready) {
        try {
            foreach ($dep in $dependencyStatus.deps) {
                if ($dep.installed -and $dep.requirement_satisfied) {
                    continue
                }
                Write-Detail ("开始安装缺失依赖：{0}" -f $dep.requirement)
                Invoke-PipInstallDirectPackage -PythonExe $PythonExe -Requirement ([string]$dep.requirement)
                Write-Detail ("安装完成：{0}" -f $dep.name)
            }
        } catch {
            throw "Python 依赖安装失败。安装器已忽略代理配置并直接走正常网络。`n建议先确认外网可访问 PyPI，再重新运行安装脚本。`n原始错误：$($_.Exception.Message)"
        }

        $dependencyStatus = Get-RuntimeDependencyStatus -ProjectRoot $ProjectRoot -PythonExe $PythonExe
        if (-not $dependencyStatus -or -not $dependencyStatus.ready) {
            $missingNames = if ($dependencyStatus -and $dependencyStatus.missing) { $dependencyStatus.missing -join ", " } else { "未知" }
            throw "Python 依赖校验仍未通过，当前缺失：$missingNames"
        }
    }

    Write-Detail "Python 依赖已全部就绪"
}

Write-Step "探测并确认通达信安装目录"
$tdxInstallDir = Resolve-TdxInstallDir -ProjectRoot $ProjectRoot -PythonExe $PythonExe
Write-Detail "当前通达信目录：$tdxInstallDir"

Write-Step "设置允许访问的局域网白名单"
$allowedCidrs = Resolve-AllowedCidrs -PythonExe $PythonExe
Write-Detail "允许来源网段：$($allowedCidrs -join ', ')"

Write-Step "写入安装配置"
Ensure-BridgeConfigFile -ConfigDir $configDir -ConfigPath $configPath -ExampleConfigPath $exampleConfigPath
$config = Get-Content $configPath -Raw | ConvertFrom-Json
if (-not $config.server) {
    $config | Add-Member -MemberType NoteProperty -Name server -Value ([pscustomobject]@{
        host = "0.0.0.0"
        port = 18888
    })
}
if (-not $config.auth) {
    $config | Add-Member -MemberType NoteProperty -Name auth -Value ([pscustomobject]@{
        token = ""
        allow_anonymous_health = $true
        allow_anonymous_capabilities = $false
    })
}
if (-not $config.tdx) {
    $config | Add-Member -MemberType NoteProperty -Name tdx -Value ([pscustomobject]@{
        install_dir = ""
    })
}
if (-not $config.python_runtime) {
    $config | Add-Member -MemberType NoteProperty -Name python_runtime -Value ([pscustomobject]@{
        mode = "subprocess-per-call"
        timeout_sec = 20
        python_executable = "python"
    })
}
if (-not $config.network) {
    $config | Add-Member -MemberType NoteProperty -Name network -Value ([pscustomobject]@{
        allowed_cidrs = @()
    })
}

Ensure-ObjectProperty -Target $config.server -Name "host" -Value "0.0.0.0"
Ensure-ObjectProperty -Target $config.server -Name "port" -Value 18888
Ensure-ObjectProperty -Target $config.auth -Name "token" -Value ""
Ensure-ObjectProperty -Target $config.auth -Name "allow_anonymous_health" -Value $true
Ensure-ObjectProperty -Target $config.auth -Name "allow_anonymous_capabilities" -Value $false
Ensure-ObjectProperty -Target $config.tdx -Name "install_dir" -Value ""
Ensure-ObjectProperty -Target $config.python_runtime -Name "mode" -Value "subprocess-per-call"
Ensure-ObjectProperty -Target $config.python_runtime -Name "timeout_sec" -Value 20
Ensure-ObjectProperty -Target $config.python_runtime -Name "python_executable" -Value "python"
Ensure-ObjectProperty -Target $config.network -Name "allowed_cidrs" -Value @()

if (-not $config.server.host) {
    $config.server.host = "0.0.0.0"
}
if (-not $config.server.port) {
    $config.server.port = 18888
}

$token = [string]$config.auth.token
if ([string]::IsNullOrWhiteSpace($token) -or $token -eq "replace-with-generated-token" -or $token -eq "auto-generated-token") {
    $token = New-RandomToken
}

$config.auth.token = $token
$config.tdx.install_dir = $tdxInstallDir
$config.python_runtime.python_executable = $PythonExe
$config.network.allowed_cidrs = @($allowedCidrs)
$configJson = $config | ConvertTo-Json -Depth 10
Write-Utf8NoBomFile -Path $configPath -Content $configJson
Write-Detail "配置文件已更新：$configPath"

if ($isWindowsHost) {
    Write-Step "注册 Windows 计划任务"
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$startScript`" -ProjectRoot `"$ProjectRoot`" -PythonExe `"$PythonExe`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    Write-Detail "计划任务已注册：$taskName，失败后会自动重试 3 次。"
}

Write-Step "启动后台桥接服务"
try {
    & $startScript -ProjectRoot $ProjectRoot -PythonExe $PythonExe | Out-Null
    Write-Detail "后台服务启动命令已执行"
} catch {
    throw "启动 TdxBridge 失败。请检查 config/bridge.json、Python 路径以及 logs 目录下日志。`n原始错误：$($_.Exception.Message)"
}

$serverPort = [int]$config.server.port
Write-Step "配置 Windows 防火墙规则"
$firewallResult = Ensure-FirewallRule -Port $serverPort -AllowedCidrs $allowedCidrs
if ($firewallResult.ok) {
    Write-Detail "防火墙规则已配置：$($firewallResult.ruleName)"
} else {
    Write-Detail $firewallResult.message
}

Write-Step "检查并启动通达信客户端"
Ensure-TdxClientRunningBeforeHealth -TdxInstallDir $tdxInstallDir

Write-Step "执行健康检查"
$health = Wait-ForHealth -Port $serverPort
$lanIp = Get-LanIPv4Address
$serviceUrl = "http://{0}:{1}" -f $lanIp, $serverPort
$allowedCidrsText = $allowedCidrs -join ", "
$tdxClientAutoStart = Ensure-TdxClientAutoStartPrompt -TdxInstallDir $tdxInstallDir

$agentPrompt = $null
$agentPromptPath = $null
$agentGuideDocument = $null
$agentGuideDocumentPath = $null
if ($GenerateAgentFiles) {
    Write-Step "生成给 Hermes / OpenClaw 的连接提示"
    $agentPrompt = New-AgentConnectionPrompt `
        -ServiceUrl $serviceUrl `
        -Token $token `
        -AllowedCidrsText $allowedCidrsText `
        -TdxInstallDir $tdxInstallDir `
        -TaskName $taskName `
        -ProjectRoot $ProjectRoot `
        -Health $health
    $agentPromptPath = Write-AgentConnectionPromptFile -ProjectRoot $ProjectRoot -Content $agentPrompt
    Write-Detail "已生成连接提示文件：$agentPromptPath"
    $agentGuideDocument = New-AgentGuideDocument `
        -ServiceUrl $serviceUrl `
        -Token $token `
        -AllowedCidrsText $allowedCidrsText `
        -TdxInstallDir $tdxInstallDir `
        -TaskName $taskName `
        -ProjectRoot $ProjectRoot `
        -Health $health
    $agentGuideDocumentPath = Write-AgentGuideDocumentFile -ProjectRoot $ProjectRoot -Content $agentGuideDocument
    Write-Detail "已生成智能体接入文档：$agentGuideDocumentPath"
}

Write-Host ""
Write-LogSuccess "TdxBridge 安装初始化已完成。"
Write-LogInfo "安装结果如下："
Write-LogInfo " - 项目目录：$ProjectRoot"
Write-LogInfo " - 配置文件：$configPath"
Write-LogInfo " - 通达信目录：$tdxInstallDir"
Write-LogInfo " - 服务地址：$serviceUrl"
Write-LogInfo " - 调用 Token：$token"
Write-LogInfo " - 允许来源网段：$allowedCidrsText"
Write-LogInfo " - 运行模式：Python 后台常驻 + TQ-Python 子进程隔离调用"
Write-LogInfo " - 接口文档：$serviceUrl/doc"
if ($GenerateAgentFiles) {
    Write-LogInfo " - 智能体连接提示文件：$agentPromptPath"
    Write-LogInfo " - 智能体接入文档：$agentGuideDocumentPath"
}
if ($tdxClientAutoStart.enabled) {
    Write-LogInfo " - 通达信客户端开机自启：已开启"
    Write-LogInfo " - 开机自启脚本：$($tdxClientAutoStart.startupPath)"
} else {
    Write-LogWarn " - 通达信客户端开机自启：未开启"
}
if ($isWindowsHost) {
    Write-LogInfo " - 计划任务：$taskName 已注册"
    if ($firewallResult.ok) {
        Write-LogInfo " - 防火墙规则：$($firewallResult.ruleName) 已配置"
    } else {
        Write-LogWarn " - 防火墙规则：未成功配置"
        Write-LogWarn " - 防火墙说明：$($firewallResult.message)"
    }
}

if ($health) {
    Write-LogSuccess "健康检查：通过"
    if ($health.checks) {
        Write-LogInfo " - TdxW.exe 运行状态：$($health.checks.tdxProcessRunning)"
        Write-LogInfo " - 17709 连通状态：$($health.checks.localRpcReachable)"
    }
} else {
    Write-LogError "健康检查：未通过，请检查 logs 目录下日志。"
    Write-HealthFailureDiagnostics -ProjectRoot $ProjectRoot -Port $serverPort
    Write-LogWarn "排查建议："
    Write-LogInfo " - 先看上面打印出来的标准输出和标准错误日志"
    Write-LogInfo " - 确认 Windows 用户已登录"
    Write-LogInfo " - 确认通达信客户端已启动"
    Write-LogInfo " - 确认 Python 依赖已安装完成"
    Write-LogInfo " - 确认 18888 端口未被其他程序占用"
}

Write-Host ""
Write-LogSuccess "安装流程已结束，后台服务会继续运行。"
if ($GenerateAgentFiles) {
    Write-Host ""
    Write-LogInfo "下面这整段就是可直接复制给 Hermes / OpenClaw 的提示词："
    Write-LogInfo "================ 提示词开始 ================"
    Write-Host $agentPrompt
    Write-LogInfo "================ 提示词结束 ================"
    Write-Host ""
    Write-LogInfo "下一步建议："
    Write-LogInfo "1. 使用上面的服务地址和 Token 配置 Hermes / OpenClaw"
    Write-LogInfo "2. 直接复制上面的提示文件内容，让 Hermes / OpenClaw 智能体自动联调"
    Write-LogInfo "3. 如需把完整接入说明喂给智能体，可直接使用上面的智能体接入文档"
} else {
    Write-Host ""
    Write-LogInfo "下一步建议："
    Write-LogInfo "1. 记录上面的服务地址、Token 和 /doc 地址"
    Write-LogInfo "2. 按你的接入方式让调用方使用这个服务"
}
} finally {
    if (-not [string]::IsNullOrWhiteSpace($script:InstallerTempDir)) {
        Remove-InstallerTempWorkspace -TempDir $script:InstallerTempDir
    }
}
