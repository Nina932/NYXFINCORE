@echo off
REM ══════════════════════════════════════════════════════════
REM FinAI Backend Sidecar Builder
REM Compiles FastAPI backend into standalone .exe for Tauri
REM ══════════════════════════════════════════════════════════

echo.
echo  FinAI Sidecar Builder
echo  ═════════════════════
echo.

REM Step 1: Build the backend .exe with PyInstaller
echo [1/3] Compiling FastAPI backend with PyInstaller...
python -m PyInstaller ^
    --onefile ^
    --name finai-backend ^
    --add-data "static;static" ^
    --add-data "data;data" ^
    --hidden-import uvicorn ^
    --hidden-import uvicorn.logging ^
    --hidden-import uvicorn.loops ^
    --hidden-import uvicorn.loops.auto ^
    --hidden-import uvicorn.protocols ^
    --hidden-import uvicorn.protocols.http ^
    --hidden-import uvicorn.protocols.http.auto ^
    --hidden-import uvicorn.protocols.websockets ^
    --hidden-import uvicorn.protocols.websockets.auto ^
    --hidden-import uvicorn.lifespan ^
    --hidden-import uvicorn.lifespan.on ^
    main.py

if errorlevel 1 (
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

REM Step 2: Copy to Tauri binaries directory
echo [2/3] Copying to Tauri binaries directory...
mkdir src-tauri\binaries 2>nul
copy dist\finai-backend.exe src-tauri\binaries\finai-backend-x86_64-pc-windows-msvc.exe

if errorlevel 1 (
    echo [ERROR] Copy failed!
    pause
    exit /b 1
)

REM Step 3: Verify
echo [3/3] Verifying...
if exist src-tauri\binaries\finai-backend-x86_64-pc-windows-msvc.exe (
    echo.
    echo  ✓ Sidecar built successfully!
    echo  Location: src-tauri\binaries\finai-backend-x86_64-pc-windows-msvc.exe
    echo.
    echo  Next steps:
    echo    1. npm install           (install Tauri CLI)
    echo    2. npm run tauri:dev     (test in dev mode)
    echo    3. npm run tauri:build   (create installer)
    echo.
) else (
    echo [ERROR] Sidecar binary not found!
)

pause
