@echo off
REM ============================================
REM Paddock Auto タスクスケジューラー登録
REM 毎日 13:00-17:00 / 3分間隔
REM ============================================

echo タスクスケジューラーに paddock_auto タスクを登録中...

set TASK_NAME=KeibaCICD_paddock_auto
set VBS_PATH=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\scripts\paddock_auto_hidden.vbs

REM --- 既存タスク削除（再登録のため）---
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo 既存タスクを削除中...
    schtasks /delete /tn "%TASK_NAME%" /f
)

REM --- 毎日 13:00-17:00 / 3分間隔で実行 ---
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "wscript.exe \"%VBS_PATH%\"" ^
    /sc daily ^
    /st 13:00 ^
    /ri 3 ^
    /du 04:00 ^
    /rl highest ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo [OK] %TASK_NAME%: 毎日 13:00-17:00 / 3分間隔
) else (
    echo [NG] タスク登録に失敗しました
    pause
    exit /b 1
)

echo.
echo === 登録内容 ===
schtasks /query /tn "%TASK_NAME%" /fo list 2>nul | findstr /C:"TaskName" /C:"Status" /C:"Next Run"

echo.
echo === 動作確認 ===
echo 手動テスト:
echo   schtasks /run /tn "%TASK_NAME%"
echo ログ確認:
echo   type C:\KEIBA-CICD\data3\logs\paddock_auto\YYYY-MM-DD.log
echo.
pause
