@echo off
REM ============================================
REM freebudget_bets.json 生成 + 目視チェック (Session 134)
REM 投票はしない。 シズネ ??-1 の per_race<=3000 / total<=10000 を自動表示。
REM
REM 使い方:
REM   freebudget_gen.bat                     (今日, bankroll 10000)
REM   freebudget_gen.bat 2026-05-31          (5/31, bankroll 10000)
REM   freebudget_gen.bat 2026-05-31 9000     (5/31, 5/30終了残高9000)
REM ============================================

setlocal enabledelayedexpansion

REM --- パス定義 ---
set KEIBA_V2=C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
set VENV=%KEIBA_V2%\.venv\Scripts\activate.bat
set DATA_ROOT=C:\KEIBA-CICD\data3

REM --- 引数解釈 ---
set DATE_ARG=%1
if "%DATE_ARG%"=="" set DATE_ARG=today

set BANKROLL_ARG=%2
if "%BANKROLL_ARG%"=="" set BANKROLL_ARG=10000

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

cd /d "%KEIBA_V2%"
call "%VENV%"

REM --- 生成 ---
echo ======================================
echo [freebudget_gen] date=%DATE_ARG% bankroll=%BANKROLL_ARG%
echo ======================================
python -m ml.strategies.freebudget --date %DATE_ARG% --bankroll %BANKROLL_ARG%
set GEN_EXIT=%ERRORLEVEL%

if not %GEN_EXIT%==0 (
    echo [freebudget_gen] 生成に失敗しました ^(exit=%GEN_EXIT%^)
    endlocal
    exit /b %GEN_EXIT%
)

REM --- シズネ ??-1 目視チェック (per_race / total) ---
echo.
echo ====== 目視チェック ^(per_race^<=3000 / total^<=10000^) ======
if not exist "%FB_JSON%" (
    echo [freebudget_gen] freebudget_bets.json が見つかりません: %FB_JSON%
    echo   ^(対象なし = 0 件の可能性。 ML 出力 / オッズを確認^)
    endlocal
    exit /b 0
)
python -c "import json;from collections import defaultdict;d=json.load(open(r'%FB_JSON%',encoding='utf-8'));pr=defaultdict(int);[pr.__setitem__(b['race_id'],pr[b['race_id']]+b['amount']) for b in d['bets']];print('total:',sum(pr.values()),'(per_day_max=10000)');[print('  ',k,':',v,'OVER!' if v>3000 else '') for k,v in pr.items()]"

echo.
echo 目視で per_race^<=3000 / total^<=10000 を確認してから
echo freebudget_vote.bat を実行してください。
echo ============================================

endlocal
exit /b 0
