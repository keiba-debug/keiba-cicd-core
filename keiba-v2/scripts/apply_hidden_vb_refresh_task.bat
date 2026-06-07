@echo off
REM ============================================
REM Switch KeibaCICD_vb_refresh to hidden VBS launch
REM Run as Administrator
REM ============================================

set TASK_NAME=KeibaCICD_vb_refresh
set HIDDEN_VBS=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\scripts\vb_refresh_auto_hidden.vbs

if not exist "%HIDDEN_VBS%" (
    echo [NG] not found: %HIDDEN_VBS%
    pause
    exit /b 1
)

echo Updating %TASK_NAME% to hidden VBS...
schtasks /change /tn "%TASK_NAME%" /tr "%HIDDEN_VBS%"

if errorlevel 1 (
    echo [NG] update failed. Check task name.
    pause
    exit /b 1
)

echo [OK] updated
schtasks /query /tn "%TASK_NAME%" /fo list /v | findstr /i "TaskName Task To Run"
echo.
pause
