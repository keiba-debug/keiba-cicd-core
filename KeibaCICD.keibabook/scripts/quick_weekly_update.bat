@echo off
REM KeibaCICD 週末データ更新バッチファイル
REM 使用例: quick_weekly_update.bat 2025/09/14 2025/09/15

echo ==================================================
echo KeibaCICD 週末データ一括更新
echo ==================================================

if "%1"=="" (
    echo エラー: 土曜日の日付を指定してください
    echo 使用例: quick_weekly_update.bat 2025/09/14 2025/09/15
    exit /b 1
)

if "%2"=="" (
    echo エラー: 日曜日の日付を指定してください
    echo 使用例: quick_weekly_update.bat 2025/09/14 2025/09/15
    exit /b 1
)

set SATURDAY=%1
set SUNDAY=%2

echo.
echo 対象日: %SATURDAY% (土), %SUNDAY% (日)
echo.

cd /d C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook

echo [1/5] 騎手情報更新中...
python -m src.scrapers.jockey_stats_aggregator --start 2025-08-01 --end %SUNDAY:-/=-%

echo.
echo [2/5] 土曜日データ取得中...
python -m src.fast_batch_cli full --start %SATURDAY% --end %SATURDAY% --delay 0.5 --max-workers 8
python -m src.integrator_cli batch --date %SATURDAY%
python -m src.markdown_cli batch --date %SATURDAY% --organized

echo.
echo [3/5] 日曜日データ取得中...
python -m src.fast_batch_cli full --start %SUNDAY% --end %SUNDAY% --delay 0.5 --max-workers 8
python -m src.integrator_cli batch --date %SUNDAY%
python -m src.markdown_cli batch --date %SUNDAY% --organized

echo.
echo [4/5] 土曜日全出走馬プロファイル生成中...
python -m src.horse_profile_cli --date %SATURDAY% --all --with-history

echo.
echo [5/5] 日曜日全出走馬プロファイル生成中...
python -m src.horse_profile_cli --date %SUNDAY% --all --with-history

echo.
echo ==================================================
echo 更新完了！
echo ==================================================
echo.
echo MD新聞保存先:
echo   Z:\KEIBA-CICD\data\organized\%SATURDAY:-/=\%
echo   Z:\KEIBA-CICD\data\organized\%SUNDAY:-/=\%
echo.
echo 馬プロファイル: Z:\KEIBA-CICD\data\horses\profiles\
echo 騎手プロファイル: Z:\KEIBA-CICD\data\jockeys\profiles\
echo.
pause