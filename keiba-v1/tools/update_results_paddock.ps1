Param(
    [Parameter(Mandatory = $true)] [string] $Date,
    [string] $EndDate,
    [string] $DataTypes = 'seiseki,paddok,syoin',
    [double] $Delay = 0.5,
    [int] $MaxWorkers = 8
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

<#!
成績（seiseki）とパドック（paddok）のみを更新し、統合とMarkdown生成を行うスクリプト。

使い方:
  # 単日
  powershell -ExecutionPolicy Bypass -File .\update_results_paddock.ps1 -Date 2025/08/23

  # 期間
  powershell -ExecutionPolicy Bypass -File .\update_results_paddock.ps1 -Date 2025/08/23 -EndDate 2025/08/24 -Delay 0.5 -MaxWorkers 8

備考:
  - デフォルトのデータタイプは 'seiseki,paddok'。必要に応じて -DataTypes で上書き可能。
  - サブシェル/パイプ未使用。
#>

function Write-Step([string] $Message) {
    Write-Host "[STEP] $Message" -ForegroundColor Cyan
}

# 入力検証（yyyy/MM/dd）
try {
    $startDateDt = [datetime]::ParseExact($Date, 'yyyy/MM/dd', $null)
} catch {
    Write-Error "日付形式が不正です。yyyy/MM/dd で指定してください。例: 2025/08/23"
    exit 1
}

if ([string]::IsNullOrWhiteSpace($EndDate)) {
    $EndDate = $Date
}

try {
    $endDateDt = [datetime]::ParseExact($EndDate, 'yyyy/MM/dd', $null)
} catch {
    Write-Error "終了日付形式が不正です。yyyy/MM/dd で指定してください。例: 2025/08/24"
    exit 1
}

# プロジェクトディレクトリ解決
$projectDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'KeibaCICD.keibabook'
if (-not (Test-Path $projectDir)) {
    Write-Error "プロジェクトディレクトリが見つかりません: $projectDir"
    exit 1
}

Push-Location $projectDir
try {
    Write-Step "fast_batch_cli data 実行: $Date → $EndDate (types=$DataTypes, delay=$Delay, workers=$MaxWorkers)"
    python -m src.fast_batch_cli data --start $Date --end $EndDate --data-types $DataTypes --delay $Delay --max-workers $MaxWorkers
    if ($LASTEXITCODE -ne 0) { throw "fast_batch_cli data 失敗: $LASTEXITCODE" }

    Write-Step "integrator_cli 統合: $Date → $EndDate"
    python -m src.integrator_cli batch --start-date $Date --end-date $EndDate
    if ($LASTEXITCODE -ne 0) { throw "integrator_cli 失敗: $LASTEXITCODE" }

    # markdown_cli は日付単位で実行
    $current = $startDateDt
    while ($current -le $endDateDt) {
        $d = $current.ToString('yyyy/MM/dd')
        Write-Step ("markdown_cli 生成: {0}" -f $d)
        python -m src.markdown_cli batch --date $d --organized
        if ($LASTEXITCODE -ne 0) { throw "markdown_cli 失敗: $LASTEXITCODE" }
        $current = $current.AddDays(1)
    }

    Write-Host ("DONE: {0} - {1} (types={2})" -f $Date, $EndDate, $DataTypes) -ForegroundColor Green
}
finally {
    Pop-Location
}
