@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ========================================================
echo   Starting TSub - Subtitle Translation Studio (Standalone)
echo ========================================================

:: 1. If compiled TSub.exe exists in this dir or dist, run it
if exist "%~dp0TSub.exe" (
    start "" "%~dp0TSub.exe"
    exit /b 0
)
if exist "%~dp0..\..\..\releases\TSub_v1.0.0_Standalone\dist\TSub\TSub.exe" (
    start "" "%~dp0..\..\..\releases\TSub_v1.0.0_Standalone\dist\TSub\TSub.exe"
    exit /b 0
)

:: 2. Try User Profile Python 3.10
if exist "%LocalAppData%\Programs\Python\Python310\python.exe" (
    "%LocalAppData%\Programs\Python\Python310\python.exe" main.py
    if %errorlevel% equ 0 goto done
)

:: 3. Try local Python in PATH
python main.py
if %errorlevel% equ 0 goto done

:: 4. Try py launcher
py -3.10 main.py
if %errorlevel% equ 0 goto done

echo.
echo [Error] Failed to start TSub.
echo Please make sure Python 3.10 or TSub.exe is present.
pause

:done