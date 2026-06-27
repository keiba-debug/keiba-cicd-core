@echo off
REM ============================================
REM gap5-tansho-edge shadow sleeve (Session 174/175) - PAPER ONLY, no real money
REM   gap_shadow_auto.bat log     = log gap>=5 tansho-edge picks inside the vote window
REM                                 (--window 8 = bet-time odds, run every 5min in race hours)
REM   gap_shadow_auto.bat settle  = settle today's picks by haraimodoshi + report
REM   gap_shadow_auto.bat report  = cumulative shadow stats (console)
REM Edge (committed) = gap>=5 single-win x {maiden/jouken/graded}, ALL odds.
REM   S175 audit: broad ROI 130% / P(null>=130%)=0.026 (edge is real);
REM   odds[15,30) "218%" was best-of-search overfit (p=0.0625) and was DROPPED.
REM   See docs/market_calibration_edge_map.md section 8 / ml/analyze/audit_gap_edge.py
REM ============================================
setlocal
set PYTHONIOENCODING=utf-8
set KEIBA_V2=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
set PY=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\.venv\Scripts\python.exe
set LOG_DIR=C:\KEIBA-CICD\data3\logs\gap_shadow
set MODE=%1
if "%MODE%"=="" set MODE=log
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\%TODAY%.log
cd /d "%KEIBA_V2%"
if "%MODE%"=="log" (
  "%PY%" -m ml.strategies.gap_tansho_shadow --today --log --window 8 >> "%LOG_FILE%" 2>&1
)
if "%MODE%"=="settle" (
  "%PY%" -m ml.strategies.gap_tansho_shadow --today --settle >> "%LOG_FILE%" 2>&1
  "%PY%" -m ml.strategies.gap_tansho_shadow --report >> "%LOG_FILE%" 2>&1
)
if "%MODE%"=="report" (
  "%PY%" -m ml.strategies.gap_tansho_shadow --report
)
endlocal
