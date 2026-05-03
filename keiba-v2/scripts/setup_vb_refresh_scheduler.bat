@echo off
REM ============================================
REM VB Refresh タスクスケジューラ登録
REM 管理者権限で実行すること
REM
REM スケジュール:
REM   - 毎日 9:00 開始 / 17:00 まで / 5分間隔
REM   - mykeibadbの土日5分間隔オッズ取得とは独立に動作
REM   - 開催日でなければ predictions.json 不在で即終了する
REM ============================================

echo タスクスケジューラに vb_refresh タスクを登録します...

set TASK_NAME=KeibaCICD_vb_refresh
set BAT_PATH=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\scripts\vb_refresh_auto.bat

REM --- 既存タスクがあれば削除（再登録に対応） ---
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo 既存タスクを削除します...
    schtasks /delete /tn "%TASK_NAME%" /f
)

REM --- 毎日 9:00-17:00 / 5分間隔で実行 ---
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%BAT_PATH%\"" ^
    /sc daily ^
    /st 09:00 ^
    /ri 5 ^
    /du 08:00 ^
    /rl highest ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo [OK] %TASK_NAME%: 毎日 9:00-17:00 / 5分間隔
) else (
    echo [NG] タスク登録に失敗しました
    pause
    exit /b 1
)

echo.
echo === 登録内容 ===
schtasks /query /tn "%TASK_NAME%" /fo list 2>nul | findstr "TaskName Status Next"

echo.
echo === 動作確認 ===
echo 即時テスト実行する場合は以下を実行:
echo   schtasks /run /tn "%TASK_NAME%"
echo ログ確認:
echo   type C:\KEIBA-CICD\data3\logs\vb_refresh\YYYY-MM-DD.log
echo.
pause
