@echo off
title KuGou Unlocker - One-click Installer
echo ==========================================================
echo    KuGou Unlocker  -  One-click Installer
echo    Developer: shushuu  ^|  Personal non-commercial use only
echo    ==========================================================
echo    This wizard will install everything for you:
echo      1. Python (official installer, silent mode)
echo      2. Required components (pycryptodome / numpy)
echo      3. A desktop shortcut: "KuGou Unlocker"
echo    Already have Python? You can skip installing it (choose 2 or 3).
echo    No command line knowledge needed. Just wait.
echo ==========================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1"
echo.
pause
