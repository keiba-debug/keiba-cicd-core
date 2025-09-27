# KeibaCICD レース当日更新スクリプト
# 使用例: .\race_day_update.ps1 -Date "2025/09/14" -UpdateType "paddok"

param(
    [Parameter(Mandatory=$true)]
    [string]$Date,

    [Parameter(Mandatory=$true)]
    [ValidateSet("paddok", "seiseki", "both")]
    [string]$UpdateType
)

Write-Host "================== レース当日更新 ==================" -ForegroundColor Cyan
Write-Host "対象日: $Date" -ForegroundColor Yellow
Write-Host "更新タイプ: $UpdateType" -ForegroundColor Yellow
Write-Host ""

# 作業ディレクトリに移動
$workDir = "C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook"
Set-Location $workDir

# エラー時の処理
$ErrorActionPreference = "Continue"

# パドック情報更新
if ($UpdateType -eq "paddok" -or $UpdateType -eq "both") {
    Write-Host "[更新] パドック情報取得..." -ForegroundColor Green
    python -m src.fast_batch_cli data --start $Date --end $Date --data-types paddok
}

# 成績情報更新
if ($UpdateType -eq "seiseki" -or $UpdateType -eq "both") {
    Write-Host "[更新] 成績情報取得..." -ForegroundColor Green
    python -m src.fast_batch_cli data --start $Date --end $Date --data-types seiseki
}

# MD新聞再生成
Write-Host ""
Write-Host "[統合] データ統合中..." -ForegroundColor Green
python -m src.integrator_cli batch --date $Date

Write-Host "[生成] MD新聞更新中..." -ForegroundColor Green
python -m src.markdown_cli batch --date $Date --organized

# 完了メッセージ
Write-Host ""
Write-Host "================== 更新完了 ==================" -ForegroundColor Cyan
Write-Host "MD新聞: Z:\KEIBA-CICD\data\organized\$($Date.Replace('/', '\'))" -ForegroundColor Yellow

if ($UpdateType -eq "paddok") {
    Write-Host ""
    Write-Host "パドック情報が更新されました。" -ForegroundColor Green
    Write-Host "レース終了後は成績情報を更新してください：" -ForegroundColor Yellow
    Write-Host "  .\race_day_update.ps1 -Date `"$Date`" -UpdateType seiseki"
}
elseif ($UpdateType -eq "seiseki") {
    Write-Host ""
    Write-Host "成績情報が更新されました。" -ForegroundColor Green
    Write-Host "レース結果がMD新聞に反映されています。" -ForegroundColor Yellow
}