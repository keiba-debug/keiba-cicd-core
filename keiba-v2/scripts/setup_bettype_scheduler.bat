@echo off
REM ============================================
REM multi-bettype auto-vote タスクスケジューラー登録 (Session 161)
REM 毎日 09:30-18:00 / 1分間隔 で bettype_auto.bat live を実行する。
REM   ※旧トリガーは「/sc once」で当日18:00固定 (日付が昨日のまま) になり翌日発火しない
REM     不具合があった (2026-06-14 発覚)。 本スクリプトは /sc daily で恒久化する。
REM 管理者として実行すること (schtasks /create が権限を要求するため)。
REM ============================================

echo タスクスケジューラーに bettype 自動投票タスクを登録します...

set TASK_NAME=KeibaBettypeAuto
set VBS_PATH=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\scripts\bettype_auto_hidden.vbs

if not exist "%VBS_PATH%" (
    echo [NG] not found: %VBS_PATH%
    pause
    exit /b 1
)

REM --- 既存タスク削除 (再登録のため) ---
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo 既存タスクを削除中...
    schtasks /delete /tn "%TASK_NAME%" /f
)

REM --- 毎日 09:30-18:00 / 1分間隔で実行 (08:30 = 8時間30分) ---
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "wscript.exe \"%VBS_PATH%\"" ^
    /sc daily ^
    /st 09:30 ^
    /ri 1 ^
    /du 08:30 ^
    /rl highest ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo [OK] %TASK_NAME%: 毎日 09:30-18:00 / 1分間隔
) else (
    echo [NG] タスク登録に失敗しました (管理者で実行していますか?)
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
echo   type C:\KEIBA-CICD\data3\logs\bettype\YYYY-MM-DD.log
echo.
echo ※ freebudget_auto (単勝のみ) と同時 live 起動しないこと (IPAT 排他)。
echo.
pause
