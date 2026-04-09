@echo off
echo ============================================================
echo  FinAI Desktop Application Builder
echo ============================================================
echo.

REM Kill any running FinAI processes
taskkill /F /IM FinAI.exe 2>nul

REM Clean previous build
if exist dist\FinAI rmdir /s /q dist\FinAI 2>nul
if exist build\FinAI rmdir /s /q build\FinAI 2>nul

echo [1/3] Building standalone FinAI.exe...
venv2\Scripts\pyinstaller finai.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo [2/3] Copying data files...
xcopy /E /I /Y "app" "dist\FinAI\_internal\app" >nul 2>&1
xcopy /E /I /Y "static" "dist\FinAI\_internal\static" >nul 2>&1
copy /Y "main.py" "dist\FinAI\_internal\" >nul 2>&1
if exist finai.db copy /Y "finai.db" "dist\FinAI\_internal\" >nul 2>&1

echo.
echo [3/3] Creating desktop shortcut...
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\finai_shortcut.vbs"
echo sLinkFile = oWS.ExpandEnvironmentStrings("%%USERPROFILE%%") ^& "\Desktop\FinAI.lnk" >> "%TEMP%\finai_shortcut.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\finai_shortcut.vbs"
echo oLink.TargetPath = "%CD%\dist\FinAI\FinAI.exe" >> "%TEMP%\finai_shortcut.vbs"
echo oLink.WorkingDirectory = "%CD%\dist\FinAI" >> "%TEMP%\finai_shortcut.vbs"
echo oLink.Description = "FinAI Financial Intelligence OS" >> "%TEMP%\finai_shortcut.vbs"
echo oLink.Save >> "%TEMP%\finai_shortcut.vbs"
cscript //nologo "%TEMP%\finai_shortcut.vbs"
del "%TEMP%\finai_shortcut.vbs"

echo.
echo ============================================================
echo  BUILD COMPLETE!
echo  Location: dist\FinAI\FinAI.exe
echo  Desktop shortcut created.
echo ============================================================
echo.
pause
