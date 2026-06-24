@echo off
setlocal
title TdxBridge Start
powershell.exe -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\Start-TdxBridge.ps1"
