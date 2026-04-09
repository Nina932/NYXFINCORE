@echo off
title FinAI - Financial Intelligence OS
cd /d "%~dp0"
echo.
echo   FinAI - Financial Intelligence OS
echo   Starting desktop application...
echo.
venv2\Scripts\python.exe finai_app.py %*
