@echo off
setlocal
title TdxBridge Release Builder
powershell.exe -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\Build-Release.ps1"
