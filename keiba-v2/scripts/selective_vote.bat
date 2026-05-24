@echo off
REM ============================================
REM selective_bets.json ?? target_clicker ???????[
REM Session 128 ????
REM
REM ?g????:
REM   selective_vote.bat                       (????, 100?~/??, dry-run)
REM   selective_vote.bat 2026-05-31            (5/31, 100?~/??, dry-run)
REM   selective_vote.bat 2026-05-31 200        (5/31, 200?~/??, dry-run)
REM   selective_vote.bat 2026-05-31 100 --confirm (?????[???[?h)
REM ============================================

setlocal

REM --- ?p?X??` ---
set KEIBA_V2=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
set VENV=%KEIBA_V2%\.venv\Scripts\activate.bat
set LOG_DIR=C:\KEIBA-CICD\data3\logs\target_clicker

REM --- ???????? ---
set DATE_ARG=%1
if "%DATE_ARG%"=="" set DATE_ARG=today

set AMOUNT_ARG=%2
if "%AMOUNT_ARG%"=="" set AMOUNT_ARG=100

set MODE_ARG=%3
REM ??3?????? --confirm ???????[?A ??????????? dry-run (--no-menu)

REM --- ???O?f?B???N?g???? ---
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM --- ???????t????O?t?@?C?? ---
set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\%TODAY%.log

REM --- ???s ---
echo. >> "%LOG_FILE%"
echo ====================================== >> "%LOG_FILE%"
echo [%date% %time%] selective_vote start (date=%DATE_ARG% amount=%AMOUNT_ARG% mode=%MODE_ARG%) >> "%LOG_FILE%"
echo ====================================== >> "%LOG_FILE%"

cd /d "%KEIBA_V2%"
call "%VENV%"

if "%MODE_ARG%"=="--confirm" (
    echo [%date% %time%] *** REAL VOTE MODE *** >> "%LOG_FILE%"
    python -m ml.target_clicker.runner --from-date %DATE_ARG% --amount %AMOUNT_ARG% --confirm >> "%LOG_FILE%" 2>&1
) else (
    echo [%date% %time%] dry-run mode ^(no menu, no click^) >> "%LOG_FILE%"
    python -m ml.target_clicker.runner --from-date %DATE_ARG% --amount %AMOUNT_ARG% --no-menu >> "%LOG_FILE%" 2>&1
)
set EXIT_CODE=%ERRORLEVEL%

echo [%date% %time%] selective_vote end (exit=%EXIT_CODE%) >> "%LOG_FILE%"

endlocal
exit /b %EXIT_CODE%
