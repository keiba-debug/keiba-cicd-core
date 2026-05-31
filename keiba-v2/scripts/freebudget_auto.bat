@echo off
REM ============================================
REM freebudget auto-vote scheduler launcher (Session 140)
REM Task Scheduler から 1-2 分ごとに呼ばれる単発パス。
REM   freebudget_auto.bat dry   = dry-run (金は動かない・計画のみ)
REM   freebudget_auto.bat live  = LIVE 実投票 (TARGET 起動+IPATログイン+入金 必須)
REM scheduler 自身が冪等 + 各レース [発走-6分, 発走-2分] のみ投票。
REM ============================================
setlocal
set KEIBA_V2=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
set VENV=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\.venv\Scripts\activate.bat
set LOG_DIR=C:\KEIBA-CICD\data3\logs\freebudget
set MODE=%1
if "%MODE%"=="" set MODE=dry
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\%TODAY%.log
cd /d "%KEIBA_V2%"
call "%VENV%"
if /i "%MODE%"=="live" (
    python -m ml.strategies.freebudget_scheduler --date today --confirm --i-understand-live >> "%LOG_FILE%" 2>&1
) else (
    python -m ml.strategies.freebudget_scheduler --date today >> "%LOG_FILE%" 2>&1
)
set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] freebudget_auto mode=%MODE% exit=%EXIT_CODE% >> "%LOG_FILE%"
endlocal
exit /b %EXIT_CODE%
