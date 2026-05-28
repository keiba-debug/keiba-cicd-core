@echo off
REM ============================================
REM freebudget_bets.json で投票 (Session 134)
REM デフォルト dry-run、 --confirm 明示で本番 (selective_vote.bat と同じガード)。
REM 事前に freebudget_gen.bat で生成 + 目視チェック済みであること。
REM
REM 使い方:
REM   freebudget_vote.bat                                    (今日, dry-run)
REM   freebudget_vote.bat 2026-05-31                         (5/31, dry-run)
REM   freebudget_vote.bat 2026-05-31 --confirm               (5/31, 本番半自動)
REM   freebudget_vote.bat 2026-05-31 --auto-launch --confirm (5/31, フル自動)
REM ============================================

setlocal enabledelayedexpansion

REM --- パス定義 ---
set KEIBA_V2=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
set VENV=%KEIBA_V2%\.venv\Scripts\activate.bat
set DATA_ROOT=C:\KEIBA-CICD\data3
set LOG_DIR=%DATA_ROOT%\logs\target_clicker

REM --- 引数解釈 ---
set DATE_ARG=%1
if "%DATE_ARG%"=="" set DATE_ARG=today

REM 2番目以降の引数 (モードフラグ) をまとめて runner に渡す
set MODE_ARGS=%2 %3 %4

REM --- 日付を YYYY MM DD に解決 (パス組み立て用) ---
if "%DATE_ARG%"=="today" (
    set YYYY=%date:~0,4%
    set MM=%date:~5,2%
    set DD=%date:~8,2%
) else (
    set YYYY=%DATE_ARG:~0,4%
    set MM=%DATE_ARG:~5,2%
    set DD=%DATE_ARG:~8,2%
)
set FB_JSON=%DATA_ROOT%\races\!YYYY!\!MM!\!DD!\freebudget_bets.json

REM --- モード判定: %2 が空なら dry-run (--no-menu) ---
if "%2"=="" (
    set RUNNER_ARGS=--no-menu
    set MODE_LABEL=dry-run
) else (
    set RUNNER_ARGS=%MODE_ARGS%
    set MODE_LABEL=%MODE_ARGS%
)

REM --- ログディレクトリ ---
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\%TODAY%.log

REM --- freebudget_bets.json 存在チェック ---
if not exist "%FB_JSON%" (
    echo [freebudget_vote] freebudget_bets.json が見つかりません: %FB_JSON%
    echo   先に freebudget_gen.bat %DATE_ARG% を実行してください。
    endlocal
    exit /b 1
)

REM --- 実行 ---
echo. >> "%LOG_FILE%"
echo ====================================== >> "%LOG_FILE%"
echo [%date% %time%] freebudget_vote start (date=%DATE_ARG% mode=%MODE_LABEL%) >> "%LOG_FILE%"
echo   json=%FB_JSON% >> "%LOG_FILE%"
echo ====================================== >> "%LOG_FILE%"

cd /d "%KEIBA_V2%"
call "%VENV%"

echo [freebudget_vote] date=%DATE_ARG% mode=%MODE_LABEL%
echo [freebudget_vote] json=%FB_JSON%

python -m ml.target_clicker.runner --from-json "%FB_JSON%" %RUNNER_ARGS% >> "%LOG_FILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%

echo [%date% %time%] freebudget_vote end (exit=%EXIT_CODE%) >> "%LOG_FILE%"
echo [freebudget_vote] end (exit=%EXIT_CODE%) ? ログ: %LOG_FILE%

endlocal
exit /b %EXIT_CODE%
