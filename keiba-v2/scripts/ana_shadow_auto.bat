@echo off
REM ============================================
REM ana-tansho shadow sleeve runner (Session 169) - PAPER ONLY, no real money
REM   ana_shadow_auto.bat log     = log value-longshot tansho picks in vote window
REM                                 (--window 8 = bet-time odds, run every 5min in race hours)
REM   ana_shadow_auto.bat settle  = settle today's picks by haraimodoshi + report
REM   ana_shadow_auto.bat report  = cumulative shadow stats (console)
REM Goal: confirm bench_ana_tansho sim ROI 103.5% reproduces live, then graduate to
REM       small isolated bankroll (shizune guardrails). See memory tansho-central-strategy.
REM ============================================
setlocal
set PYTHONIOENCODING=utf-8
set KEIBA_V2=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
set PY=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\.venv\Scripts\python.exe
set LOG_DIR=C:\KEIBA-CICD\data3\logs\ana_shadow
set MODE=%1
if "%MODE%"=="" set MODE=log
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\%TODAY%.log
cd /d "%KEIBA_V2%"
if "%MODE%"=="log" (
  "%PY%" -m ml.strategies.ana_tansho_shadow --today --log --window 8 >> "%LOG_FILE%" 2>&1
)
if "%MODE%"=="settle" (
  "%PY%" -m ml.strategies.ana_tansho_shadow --today --settle >> "%LOG_FILE%" 2>&1
  "%PY%" -m ml.strategies.ana_tansho_shadow --report >> "%LOG_FILE%" 2>&1
)
if "%MODE%"=="report" (
  "%PY%" -m ml.strategies.ana_tansho_shadow --report
)
endlocal
