@echo off
REM ============================================
REM freebudget レース単位 ヘルパー (Session 135)
REM   freebudget_race.bat <date>                      一覧 (発走/締切/投票時刻 + あと何分 + race_id)
REM   freebudget_race.bat <date> <race_id>            指定レース dry-run (JSON生成のみ / clickしない)
REM   freebudget_race.bat <date> <race_id> --confirm  指定レース 本番投票
REM
REM 時刻定義: 締切=発走-2分 / 投票推奨=締切-4分(=発走-6分)
REM bankroll は 10000 固定 (OOS 条件: 1万円フリー予算)。
REM 投票出力はコンソールに直接出す (付きっ切り監視のため)。
REM 前提: TARGET起動 + IPATログイン (暗証番号) は手動で済ませておくこと。
REM ============================================

setlocal enabledelayedexpansion

set KEIBA_V2=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
set VENV=%KEIBA_V2%\.venv\Scripts\activate.bat
set DATA_ROOT=C:\KEIBA-CICD\data3

set DATE_ARG=%1
if "%DATE_ARG%"=="" set DATE_ARG=today
set RACE_ID=%2
set MODE_ARGS=%3 %4

cd /d "%KEIBA_V2%"
call "%VENV%"

REM --- race_id 無し → 一覧表示 (ライブ監視ダッシュボード) ---
if "%RACE_ID%"=="" (
    python -m ml.strategies.freebudget_race --date %DATE_ARG%
    endlocal
    exit /b 0
)

REM --- race_id から日付を導出 (先頭8桁 = YYYYMMDD。 当日変更/today でも確実) ---
set YYYY=%RACE_ID:~0,4%
set MM=%RACE_ID:~4,2%
set DD=%RACE_ID:~6,2%
set DATE_FROM_ID=!YYYY!-!MM!-!DD!
set FB_JSON=%DATA_ROOT%\races\!YYYY!\!MM!\!DD!\freebudget_bets_%RACE_ID%.json

REM --- (1) 指定レースだけ freebudget_bets_<id>.json を生成 ---
python -m ml.strategies.freebudget_race --date !DATE_FROM_ID! --race-id %RACE_ID%
if errorlevel 1 (
    echo [freebudget_race] 生成失敗 ^(候補外 or predictions 無し^)
    endlocal
    exit /b 1
)

REM --- (2) モード判定: %3 が無ければ dry-run (--no-menu = TARGET 触らない) ---
if "%3"=="" (
    set RUNNER_ARGS=--no-menu
    set MODE_LABEL=dry-run
) else (
    set RUNNER_ARGS=%MODE_ARGS%
    set MODE_LABEL=%MODE_ARGS%
)

echo.
echo [freebudget_race] race=%RACE_ID% mode=!MODE_LABEL!
echo [freebudget_race] json=%FB_JSON%
echo ----------------------------------------

python -m ml.target_clicker.runner --from-json "%FB_JSON%" --login-timeout 180 !RUNNER_ARGS!
set EXIT_CODE=!ERRORLEVEL!

echo ----------------------------------------
echo [freebudget_race] end (exit=!EXIT_CODE!)

endlocal
exit /b %EXIT_CODE%
