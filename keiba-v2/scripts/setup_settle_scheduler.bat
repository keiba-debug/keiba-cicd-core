@echo off
REM ============================================
REM Settle 自動精算 タスクスケジューラ登録 (VU-2 / W1/W5)
REM 管理者権限で実行すること
REM
REM スケジュール:
REM   - 毎日 17:00 開始 / 30分間隔 / 6時間59分 (= 23:59まで、日付境界で窓を重ねない)
REM   - 開催日の各レース確定後に settle、確定レースのみ payout 反映
REM   - 確定前レースは PENDING 据え置き、再実行で二重計上しない (冪等)
REM   - 非開催日は ledger 無し → no-op (exit 0)、害なし
REM   - settle_auto.bat は今日+直近2日を catch-up (前日確定の遅延払戻/連続非稼働を吸収)
REM ============================================

echo タスクスケジューラに settle 自動精算タスクを登録します...

set TASK_NAME=KeibaCICD_settle
set BAT_PATH=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\scripts\settle_auto.bat

REM --- 既存タスクがあれば削除 (再登録に対応) ---
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo 既存タスクを削除します...
    schtasks /delete /tn "%TASK_NAME%" /f
)

REM --- 毎日 17:00-23:59 / 30分間隔で実行 ---
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%BAT_PATH%\"" ^
    /sc daily ^
    /st 17:00 ^
    /ri 30 ^
    /du 06:59 ^
    /rl highest ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo [OK] %TASK_NAME%: 毎日 17:00-23:59 / 30分間隔
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
echo 手動テスト実行する場合は以下を実行:
echo   schtasks /run /tn "%TASK_NAME%"
echo ログ確認:
echo   type C:\KEIBA-CICD\data3\logs\settle\YYYY-MM-DD.log
echo.
pause
