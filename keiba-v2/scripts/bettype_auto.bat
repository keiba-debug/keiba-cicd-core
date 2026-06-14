@echo off
REM ============================================
REM multi-bettype auto-vote scheduler launcher (Session 140)
REM Task Scheduler ・ｽ・ｽ・ｽ・ｽ 1-2 ・ｽ・ｽ・ｽ・ｽ・ｽﾆに呼ばゑｿｽ・ｽP・ｽ・ｽ・ｽp・ｽX・ｽB
REM   bettype_auto.bat dry   = dry-run (・ｽ・ｽ・ｽﾍ難ｿｽ・ｽ・ｽ・ｽﾈゑｿｽ・ｽE・ｽv・ｽ・ｽﾌゑｿｽ)
REM   bettype_auto.bat live  = LIVE ・ｽ・ｽ・ｽ・ｽ・ｽ[ (TARGET ・ｽN・ｽ・ｽ+IPAT・ｽ・ｽ・ｽO・ｽC・ｽ・ｽ+・ｽ・ｽ・ｽ・ｽ ・ｽK・ｽ{)
REM scheduler ・ｽ・ｽ・ｽg・ｽ・ｽ・ｽp・ｽ・ｽ + ・ｽe・ｽ・ｽ・ｽ[・ｽX [・ｽ・ｽ・ｽ・ｽ-6・ｽ・ｽ, ・ｽ・ｽ・ｽ・ｽ-2・ｽ・ｽ] ・ｽﾌみ難ｿｽ・ｽ[・ｽB
REM strategy=concentrate (AI mark = composite top axis. Session162: sizing=fixed_grade_v2)
REM   / sizing=fixed_grade_v2 (v1 + heavy-combo-on-strong-axis; skip-gate DISABLED S163: hindsight-trap, hurt ROI) / per_day=30000 / per_race=3000(config).
REM ・ｽ・ｽ・ｽ・ｽ=VOICEVOX ・ｽ・ｽ・ｽ・ｽq ・ｽ・ｽ・ｽ・ｽ・ｽ・ｽ(ID93) ・ｽ・ｽ bat ・ｽ・ｽ・ｽﾅ厄ｿｽ・ｽ・ｽ・ｽﾝ抵ｿｽ (User env ・ｽ・ｽﾋ托ｿｽ・ｽﾅ確・ｽ・ｽ・ｽﾉ趣ｿｽ・ｽ・ｽ・ｽ・ｽ)・ｽB
REM ・ｽ・ｽfreebudget_auto ・ｽﾆ難ｿｽ・ｽ・ｽ・ｽ・ｽ live ・ｽN・ｽ・ｽ・ｽ・ｽ・ｽﾈゑｿｽ (IPAT ・ｽr・ｽ・ｽ)・ｽB
REM ============================================
setlocal
set KEIBA_V2=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
set VENV=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\.venv\Scripts\activate.bat
set LOG_DIR=C:\KEIBA-CICD\data3\logs\bettype
set KEIBA_TTS_ENGINE=voicevox
set KEIBA_VOICEVOX_SPEAKER=93
set MODE=%1
if "%MODE%"=="" set MODE=dry
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\%TODAY%.log
cd /d "%KEIBA_V2%"
call "%VENV%"
if /i "%MODE%"=="live" (
    python -m ml.strategies.bettype_scheduler --date today --confirm --i-understand-live --strategy concentrate --sizing fixed_grade_v2 --per-day-max-yen 30000 >> "%LOG_FILE%" 2>&1
) else (
    python -m ml.strategies.bettype_scheduler --date today --strategy concentrate --sizing fixed_grade_v2 --per-day-max-yen 30000 >> "%LOG_FILE%" 2>&1
)
set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] bettype_auto mode=%MODE% strategy=concentrate exit=%EXIT_CODE% >> "%LOG_FILE%"
endlocal
exit /b %EXIT_CODE%
