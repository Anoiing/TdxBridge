@echo off
setlocal
title TdxBridge Uninstall
powershell.exe -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\Uninstall-TdxBridge.ps1"
