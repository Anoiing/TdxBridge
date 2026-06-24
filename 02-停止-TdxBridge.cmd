@echo off
setlocal
title TdxBridge Stop
powershell.exe -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\Stop-TdxBridge.ps1"
