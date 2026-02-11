Param(
    [Parameter(Mandatory = $true)] [string] $Date,
    [string] $EndDate,
    [double] $Delay = 0.5,
    [int] $MaxWorkers = 8,
    [switch] $SkipOrganize
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

<#!
使い方:
  powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -Date 2025/08/24
  powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -Date 2025/08/23 -EndDate 2025/08/24 -Delay 0.5 -MaxWorkers 8

注意:
  - 日付形式は yyyy/MM/dd を指定
  - サブシェルやパイプは使用しません
#>

function Write-Step([string] $Message) {
    Write-Host "[STEP] $Message" -ForegroundColor Cyan
}

# 入力検証（yyyy/MM/dd）
try {
    $startDateDt = [datetime]::ParseExact($Date, 'yyyy/MM/dd', $null)
} catch {
    Write-Error "日付形式が不正です。yyyy/MM/dd で指定してください。例: 2025/08/24"
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

# プロジェクトディレクトリ解決（KeibaCICD.keibabook 配下で python -m を実行）
$projectDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'KeibaCICD.keibabook'
if (-not (Test-Path $projectDir)) {
    Write-Error "プロジェクトディレクトリが見つかりません: $projectDir"
    exit 1
}

Push-Location $projectDir
try {
    Write-Step "fast_batch_cli 実行: $Date → $EndDate (delay=$Delay, workers=$MaxWorkers)"
    python -m src.fast_batch_cli full --start $Date --end $EndDate --delay $Delay --max-workers $MaxWorkers
    if ($LASTEXITCODE -ne 0) { throw "fast_batch_cli 失敗: $LASTEXITCODE" }

    Write-Step "integrator_cli 実行: $Date → $EndDate"
    python -m src.integrator_cli batch --start-date $Date --end-date $EndDate
    if ($LASTEXITCODE -ne 0) { throw "integrator_cli 失敗: $LASTEXITCODE" }

    # markdown_cli は日付単位で実行
    $current = $startDateDt
    while ($current -le $endDateDt) {
        $d = $current.ToString('yyyy/MM/dd')
        Write-Step ("markdown_cli 実行: {0}" -f $d)
        python -m src.markdown_cli batch --date $d --organized
        if ($LASTEXITCODE -ne 0) { throw "markdown_cli 失敗: $LASTEXITCODE" }
        $current = $current.AddDays(1)
    }

    if (-not $SkipOrganize) {
        Write-Step "organizer_cli organize 実行（--copy --delete-original）"
        python -m src.organizer_cli organize --copy --delete-original
        if ($LASTEXITCODE -ne 0) { throw "organizer organize 失敗: $LASTEXITCODE" }

        Write-Step "organizer_cli index 実行"
        python -m src.organizer_cli index
        if ($LASTEXITCODE -ne 0) { throw "organizer index 失敗: $LASTEXITCODE" }
    }

    Write-Host ("完了: {0} ～ {1}" -f $Date, $EndDate) -ForegroundColor Green
}
finally {
    Pop-Location
}
