@echo off
REM ============================================
REM Paddock Auto 自動実行
REM 13:00-17:00 3分間隔でパドック取得
REM 競馬ブックのパドック情報は7R以降のみ提供
REM → レース直前に順次公開されるため毎回実行
REM ============================================

setlocal

REM --- パス定義 ---
set KEIBA_V2=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
set VENV=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\.venv\Scripts\activate.bat
set LOG_DIR=C:\KEIBA-CICD\data3\logs\paddock_auto
set API_BASE=http://localhost:3000

REM --- ログディレクトリ作成 ---
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM --- 日付とログファイル名 ---
set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\%TODAY%.log

REM --- 二重起動防止: ロックファイル ---
set LOCK_FILE=%LOG_DIR%\paddock_auto.lock
if exist "%LOCK_FILE%" (
    echo [%date% %time%] previous run still active, skip >> "%LOG_FILE%"
    exit /b 0
)
echo %date% %time% > "%LOCK_FILE%"

REM --- 実行 ---
echo. >> "%LOG_FILE%"
echo ====================================== >> "%LOG_FILE%"
echo [%date% %time%] paddock_auto start >> "%LOG_FILE%"
echo [%date% %time%] fetching paddock (7R以降が対象)... >> "%LOG_FILE%"

cd /d "%KEIBA_V2%"
call "%VENV%"
python -m keibabook.batch_scraper --date %TODAY% --types paddok --from-race 7 >> "%LOG_FILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%

echo [%date% %time%] paddock fetch end (exit=%EXIT_CODE%) >> "%LOG_FILE%"

REM --- ロック解除 ---
del "%LOCK_FILE%" 2>nul

endlocal
exit /b %EXIT_CODE%
