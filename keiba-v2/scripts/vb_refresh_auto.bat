@echo off
REM ============================================
REM VB Refresh 自動実行
REM 最新オッズで predictions.json / bets.json を再計算
REM タスクスケジューラから5分間隔で呼ばれる想定
REM ============================================

setlocal

REM --- パス定義 ---
set KEIBA_V2=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
set VENV=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v1\KeibaCICD.keibabook\.venv\Scripts\activate.bat
set LOG_DIR=C:\KEIBA-CICD\data3\logs\vb_refresh

REM --- ログディレクトリ作成 ---
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM --- 日付ごとのログファイル名 (例: 2026-05-02) ---
set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\%TODAY%.log

REM --- 多重起動防止: ロックファイル ---
set LOCK_FILE=%LOG_DIR%\vb_refresh.lock
if exist "%LOCK_FILE%" (
    echo [%date% %time%] previous run still active, skip >> "%LOG_FILE%"
    exit /b 0
)
echo %date% %time% > "%LOCK_FILE%"

REM --- 実行 ---
echo. >> "%LOG_FILE%"
echo ====================================== >> "%LOG_FILE%"
echo [%date% %time%] vb_refresh start >> "%LOG_FILE%"
echo ====================================== >> "%LOG_FILE%"

cd /d "%KEIBA_V2%"
call "%VENV%"
python -m ml.vb_refresh --today >> "%LOG_FILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%

echo [%date% %time%] vb_refresh end (exit=%EXIT_CODE%) >> "%LOG_FILE%"

REM --- ロック解除 ---
del "%LOCK_FILE%" 2>nul

endlocal
exit /b %EXIT_CODE%
