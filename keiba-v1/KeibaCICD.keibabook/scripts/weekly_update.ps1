# KeibaCICD 週末競馬データ更新スクリプト
# 使用例: .\weekly_update.ps1 -Saturday "2025/09/14" -Sunday "2025/09/15"

param(
    [Parameter(Mandatory=$true)]
    [string]$Saturday,

    [Parameter(Mandatory=$true)]
    [string]$Sunday,

    [int]$MaxWorkers = 8,
    [float]$Delay = 0.5
)

Write-Host "================== KeibaCICD 週末データ更新 ==================" -ForegroundColor Cyan
Write-Host "対象日: $Saturday (土), $Sunday (日)" -ForegroundColor Yellow
Write-Host ""

# 作業ディレクトリに移動
$workDir = "C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook"
Set-Location $workDir

# エラー時の処理
$ErrorActionPreference = "Continue"

# 1. 騎手情報更新
Write-Host "[Step 1] 騎手情報更新..." -ForegroundColor Green
$month = [datetime]::Parse($Saturday).Month
$year = [datetime]::Parse($Saturday).Year

Write-Host "  騎手リーディング取得..."
python -m src.jockey_cli leading --year $year --month $month

Write-Host "  騎手統計集計..."
$startDate = [datetime]::Parse($Saturday).AddDays(-30).ToString("yyyy-MM-dd")
$endDate = [datetime]::Parse($Sunday).ToString("yyyy-MM-dd")
python -m src.scrapers.jockey_stats_aggregator --start $startDate --end $endDate

# 2. 土曜日データ取得
Write-Host ""
Write-Host "[Step 2] 土曜日データ取得..." -ForegroundColor Green
Write-Host "  日程データ取得..."
python -m src.fast_batch_cli schedule --start $Saturday --end $Saturday

Write-Host "  詳細データ取得..."
python -m src.fast_batch_cli data --start $Saturday --end $Saturday --data-types seiseki,shutsuba,cyokyo,danwa,syoin,paddok --max-workers $MaxWorkers --delay $Delay

Write-Host "  データ統合..."
python -m src.integrator_cli batch --date $Saturday

Write-Host "  MD新聞生成..."
python -m src.markdown_cli batch --date $Saturday --organized

# 3. 日曜日データ取得
Write-Host ""
Write-Host "[Step 3] 日曜日データ取得..." -ForegroundColor Green
Write-Host "  日程データ取得..."
python -m src.fast_batch_cli schedule --start $Sunday --end $Sunday

Write-Host "  詳細データ取得..."
python -m src.fast_batch_cli data --start $Sunday --end $Sunday --data-types seiseki,shutsuba,cyokyo,danwa,syoin,paddok --max-workers $MaxWorkers --delay $Delay

Write-Host "  データ統合..."
python -m src.integrator_cli batch --date $Sunday

Write-Host "  MD新聞生成..."
python -m src.markdown_cli batch --date $Sunday --organized

# 4. 馬プロファイル生成（全出走馬）
Write-Host ""
Write-Host "[Step 4] 馬プロファイル生成（全出走馬）..." -ForegroundColor Green
Write-Host "  土曜日全出走馬..."
python -m src.horse_profile_cli --date $Saturday --all --with-history

Write-Host "  日曜日全出走馬..."
python -m src.horse_profile_cli --date $Sunday --all --with-history

# 完了メッセージ
Write-Host ""
Write-Host "================== 更新完了 ==================" -ForegroundColor Cyan
Write-Host "MD新聞: Z:\KEIBA-CICD\data\organized\$($Saturday.Replace('/', '\'))" -ForegroundColor Yellow
Write-Host "MD新聞: Z:\KEIBA-CICD\data\organized\$($Sunday.Replace('/', '\'))" -ForegroundColor Yellow
Write-Host ""
Write-Host "次のステップ:" -ForegroundColor Green
Write-Host "1. 生成されたMD新聞を確認"
Write-Host "2. 馬・騎手プロファイルを確認"
Write-Host "3. 当日のパドック情報・成績情報は別途更新"