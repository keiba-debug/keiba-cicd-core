@echo off
REM ============================================
REM Switch KeibaBettypeAuto to hidden VBS launch
REM Run as Administrator if schtasks /change fails
REM ============================================

set TASK_NAME=KeibaBettypeAuto
set HIDDEN_VBS=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\scripts\bettype_auto_hidden.vbs

if not exist "%HIDDEN_VBS%" (
    echo [NG] not found: %HIDDEN_VBS%
    pause
    exit /b 1
)

echo Updating %TASK_NAME% to hidden VBS...
echo   %HIDDEN_VBS%
echo.

schtasks /change /tn "%TASK_NAME%" /tr "%HIDDEN_VBS%"

if errorlevel 1 (
    echo [NG] update failed. Check task name or run as Administrator.
    pause
    exit /b 1
)

echo [OK] updated
schtasks /query /tn "%TASK_NAME%" /fo list /v | findstr /i "TaskName Task To Run"
echo.
echo Done. Next runs will not show a DOS window.
pause
