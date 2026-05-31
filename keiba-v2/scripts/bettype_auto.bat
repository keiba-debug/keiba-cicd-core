@echo off
REM ============================================
REM multi-bettype auto-vote scheduler launcher (Session 140)
REM Task Scheduler から 1-2 分ごとに呼ばれる単発パス。
REM   bettype_auto.bat dry   = dry-run (金は動かない・計画のみ)
REM   bettype_auto.bat live  = LIVE 実投票 (TARGET 起動+IPATログイン+入金 必須)
REM scheduler 自身が冪等 + 各レース [発走-6分, 発走-2分] のみ投票。
REM strategy=hole_seeker (妙味軸=過小評価馬。value無いレースは composite軸にフォールバック)
REM   / sizing=anchor_kelly_combo_ev / per_day=30000 / per_race=3000(config)。
REM 音声=VOICEVOX ぞん子 実況風(ID93) を bat 内で明示設定 (User env 非依存で確実に実況風)。
REM ★freebudget_auto と同時に live 起動しない (IPAT 排他)。
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
    python -m ml.strategies.bettype_scheduler --date today --confirm --i-understand-live --strategy hole_seeker --per-day-max-yen 30000 >> "%LOG_FILE%" 2>&1
) else (
    python -m ml.strategies.bettype_scheduler --date today --strategy hole_seeker --per-day-max-yen 30000 >> "%LOG_FILE%" 2>&1
)
set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] bettype_auto mode=%MODE% strategy=hole_seeker exit=%EXIT_CODE% >> "%LOG_FILE%"
endlocal
exit /b %EXIT_CODE%
