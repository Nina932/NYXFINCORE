@echo off
REM FinAI Deployment Helper for Windows Batch
REM Usage: deploy.bat [setup|start|stop|logs|status|backup|restore|help]

setlocal enabledelayedexpansion

color 0A
title FinAI Deployment Helper

if "%1"=="" goto :help
if /i "%1"=="setup" goto :setup
if /i "%1"=="start" goto :start
if /i "%1"=="stop" goto :stop
if /i "%1"=="logs" goto :logs
if /i "%1"=="status" goto :status
if /i "%1"=="backup" goto :backup
if /i "%1"=="restore" goto :restore
if /i "%1"=="health" goto :health
if /i "%1"=="help" goto :help
goto :help

:setup
echo.
echo [INFO] Setting up FinAI...
if exist ".env" (
    echo [INFO] .env already exists, skipping copy
) else (
    if not exist ".env.example" (
        echo [ERROR] .env.example not found
        pause
        exit /b 1
    )
    copy .env.example .env
    echo [SUCCESS] .env created from template
    echo [INFO] Edit .env with your configuration before running start
)

REM Create directories
for %%D in (static,uploads,exports,logs,ssl,backups) do (
    if not exist "%%D" mkdir "%%D" && echo [SUCCESS] Created directory: %%D
)

echo.
echo [INFO] Setup complete!
echo [INFO] Next steps:
echo [INFO] 1. Edit .env with your API key and database password
echo [INFO] 2. Copy FinAI_Platform_v7.html to static\ folder
echo [INFO] 3. Run: deploy.bat start
echo.
pause
exit /b 0

:start
echo.
echo [INFO] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker not found. Install from https://docs.docker.com/get-docker/
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env not found. Run: deploy.bat setup
    pause
    exit /b 1
)

echo [INFO] Starting FinAI stack...
docker compose up -d
if errorlevel 1 (
    echo [ERROR] Failed to start docker compose
    pause
    exit /b 1
)

echo [INFO] Waiting for services to start...
timeout /t 5 /nobreak

docker compose ps
echo.
echo [SUCCESS] FinAI started!
echo [INFO] Access your app:
echo [INFO]   Frontend: http://localhost
echo [INFO]   API Docs: http://localhost:8000/api/docs
echo [INFO]   Health:   http://localhost:8000/health
echo.
pause
exit /b 0

:stop
echo.
echo [INFO] Stopping FinAI...
docker compose down
if errorlevel 1 (
    echo [ERROR] Failed to stop docker compose
    pause
    exit /b 1
)
echo [SUCCESS] FinAI stopped
echo.
pause
exit /b 0

:status
echo.
docker compose ps
echo.
pause
exit /b 0

:logs
echo.
if "%2"=="" (
    set CONTAINER=api
) else (
    set CONTAINER=%2
)
echo [INFO] Showing logs for !CONTAINER! (Ctrl+C to exit)...
docker compose logs -f !CONTAINER!
exit /b 0

:backup
echo.
echo [INFO] Backing up database...
if not exist backups mkdir backups

for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set TIMESTAMP=!mydate!_!mytime!

set BACKUP_FILE=backups\finai_backup_!TIMESTAMP!.sql

docker compose exec -T db pg_dump -U finai finai_db > !BACKUP_FILE!
if errorlevel 1 (
    echo [ERROR] Backup failed
    pause
    exit /b 1
)

echo [SUCCESS] Backup created: !BACKUP_FILE!
echo.
pause
exit /b 0

:restore
echo.
if "%2"=="" (
    echo [ERROR] Usage: deploy.bat restore [backup_file]
    echo [INFO] Available backups:
    dir backups\ 2>nul || echo   No backups found
    echo.
    pause
    exit /b 1
)

if not exist "%2" (
    echo [ERROR] Backup file not found: %2
    pause
    exit /b 1
)

echo [INFO] Restoring database from %2...
type "%2" | docker compose exec -T db psql -U finai finai_db
if errorlevel 1 (
    echo [ERROR] Restore failed
    pause
    exit /b 1
)

echo [SUCCESS] Database restored from %2
echo.
pause
exit /b 0

:health
echo.
echo [INFO] Checking API health...
for /f %%a in ('curl -s http://localhost:8000/health') do (
    if "%%a"=="healthy" (
        echo [SUCCESS] API is healthy
        curl -s http://localhost:8000/health
        echo.
        pause
        exit /b 0
    )
)
echo [ERROR] API is not responding
pause
exit /b 1

:help
cls
echo.
echo   ====================================================
echo   FinAI Deployment Helper for Windows
echo   ====================================================
echo.
echo   Usage: deploy.bat [command]
echo.
echo   Commands:
echo   setup              - Initialize configuration (.env, directories)
echo   start              - Start all services (API, DB, Nginx)
echo   stop               - Stop all services
echo   status             - Show container status
echo   logs [container]   - View logs (default: api)
echo   health             - Check API health
echo   backup             - Backup database
echo   restore [file]     - Restore database from backup
echo   help               - Show this help message
echo.
echo   Examples:
echo   deploy.bat setup
echo   deploy.bat start
echo   deploy.bat logs api
echo   deploy.bat backup
echo   deploy.bat restore backups\finai_backup_20250304_120000.sql
echo.
echo   ====================================================
echo.
pause
exit /b 0
