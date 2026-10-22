@echo off
chcp 65001 >nul 2>&1
rem ============================================================
rem  MCD x WorkBuddy Contest - one-click publish to GitHub
rem  Double-click this file. Enter your GitHub username + Token.
rem  (Chinese UI text lives in the .ps1 file)
rem ============================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish.ps1"
pause
