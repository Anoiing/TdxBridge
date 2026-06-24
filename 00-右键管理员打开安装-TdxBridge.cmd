@echo off
setlocal
title TdxBridge Installer
powershell.exe -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\Install-TdxBridge.ps1"
