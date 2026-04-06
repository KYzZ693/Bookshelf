@echo off
echo ========================================
echo   BookShelf API Server
echo ========================================
echo.
cd /d "%~dp0"
python scraper.py
pause
