[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = Split-Path -Parent $scriptDir
}

$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot.Trim().Trim('"'))
$builderScript = Join-Path $ProjectRoot "scripts\build_release.py"

if (-not (Test-Path $builderScript)) {
    throw "未找到跨平台打包脚本：$builderScript"
}

if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
    throw "未找到 Python 可执行文件：$PythonExe"
}

& $PythonExe $builderScript --project-root $ProjectRoot
if ($LASTEXITCODE -ne 0) {
    throw "打包失败，退出码：$LASTEXITCODE"
}
