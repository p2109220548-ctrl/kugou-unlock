@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  start "" py kugou_unlock_gui.py
  exit /b
)
where python >nul 2>&1
if %errorlevel%==0 (
  start "" python kugou_unlock_gui.py
  exit /b
)
echo ==========================================================
echo   Python not found.
echo   Please double-click install_windows.bat first.
echo   (Developer: shushuu - personal use only, no commercial use)
echo ==========================================================
pause
