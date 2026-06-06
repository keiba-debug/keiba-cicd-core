@echo off
REM ============================================
REM Settle Auto - ledger v2 自動精算 (VU-2 / W1/W5)
REM 開催日夜に確定レースを冪等 settle → /bankroll/auto に払戻反映。
REM Task Scheduler から夕方?夜に定期実行される想定。
REM   settle_auto.bat            = 今日 + 直近2日(catch-up) を settle
REM   settle_auto.bat 2026-05-30 = 指定日のみ settle (手動再実行用、日付は YYYY-MM-DD 固定)
REM 冪等: settled_at で二重計上しない。確定前レースは PENDING 据え置き。
REM ※settle 対象日は Python(datetime.now)が決める。バッチは --date を自動生成しない。
REM ============================================

setlocal enabledelayedexpansion

REM --- パス定義 ---
set KEIBA_V2=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
set VENV=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\.venv\Scripts\activate.bat
set LOG_DIR=C:\KEIBA-CICD\data3\logs\settle

REM --- ログディレクトリ作成 ---
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM --- ログファイル名専用の日付 (settle 対象日ではない。対象日は Python が決める) ---
set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\%TODAY%.log

REM --- 多重起動防止: ロックファイル (60分以上古い=異常終了の残骸は自動奪取) ---
REM   lock 残留で settle が永久 skip されると「払戻が出ない」問題が再発するため fail-open。
set LOCK_FILE=%LOG_DIR%\settle.lock
if exist "%LOCK_FILE%" (
    for /f %%A in ('powershell -NoProfile -Command "if(((Get-Date)-(Get-Item '%LOCK_FILE%').LastWriteTime).TotalMinutes -gt 60){'stale'}else{'active'}"') do set LOCK_STATE=%%A
    if "!LOCK_STATE!"=="active" (
        echo [%date% %time%] previous run still active, skip >> "%LOG_FILE%"
        exit /b 0
    )
    echo [%date% %time%] stale lock over 60min, taking over >> "%LOG_FILE%"
    del "%LOCK_FILE%" 2>nul
)
echo %date% %time% > "%LOCK_FILE%"

REM --- 実行 ---
echo. >> "%LOG_FILE%"
echo ====================================== >> "%LOG_FILE%"
echo [%date% %time%] settle start >> "%LOG_FILE%"
echo ====================================== >> "%LOG_FILE%"

cd /d "%KEIBA_V2%"
call "%VENV%"
if "%~1"=="" (
    python -m ml.settle_ledger --today --catchup-days 2 >> "%LOG_FILE%" 2>&1
) else (
    python -m ml.settle_ledger --date %~1 >> "%LOG_FILE%" 2>&1
)
set EXIT_CODE=%ERRORLEVEL%

echo [%date% %time%] settle end (exit=%EXIT_CODE%) >> "%LOG_FILE%"
if not "%EXIT_CODE%"=="0" echo [ERROR] settle exited non-zero - check log >> "%LOG_FILE%"

REM --- ロック解除 ---
del "%LOCK_FILE%" 2>nul

endlocal
exit /b %EXIT_CODE%
