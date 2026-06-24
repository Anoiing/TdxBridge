@echo off
setlocal
title TdxBridge Debug All Endpoints
powershell.exe -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\Debug-AllEndpoints.ps1"
