# 競馬ブック データ取得 - 日次バッチスクリプト v2.0
# 新しい統合CLIシステム対応版

param(
    [Parameter(Mandatory=$false)]
    [string]$StartDate = (Get-Date).ToString("yyyy/MM/dd"),
    
    [Parameter(Mandatory=$false)]
    [string]$EndDate = "",
    
    [Parameter(Mandatory=$false)]
    [string]$DataTypes = "seiseki,shutsuba",
    
    [Parameter(Mandatory=$false)]
    [int]$Delay = 3,
    
    [Parameter(Mandatory=$false)]
    [int]$WaitBetweenPhases = 10,
    
    [Parameter(Mandatory=$false)]
    [switch]$ScheduleOnly,
    
    [Parameter(Mandatory=$false)]
    [switch]$DataOnly,
    
    [Parameter(Mandatory=$false)]
    [switch]$Debug,
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun,
    
    [Parameter(Mandatory=$false)]
    [string]$LogLevel = "INFO"
)

# ===== 設定・初期化 =====

$ErrorActionPreference = "Stop"
$ScriptName = "DailyBatch_v2"
$ScriptVersion = "2.0.0"
$LogFile = "logs/daily_batch_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# プロジェクトルートディレクトリの検出
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "$ProjectRoot/src/keibabook/batch_cli.py")) {
    Write-Error "プロジェクトルートが見つかりません: $ProjectRoot"
    exit 1
}

Set-Location $ProjectRoot

# ===== ヘルパー関数 =====

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$Level] $Message"
    Write-Host $LogMessage
    
    # ログファイルに出力
    if (-not (Test-Path "logs")) {
        New-Item -ItemType Directory -Path "logs" -Force | Out-Null
    }
    Add-Content -Path $LogFile -Value $LogMessage
}

function Invoke-PythonCommand {
    param([string]$Command, [string]$Description)
    
    Write-Log "実行中: $Description"
    Write-Log "コマンド: $Command" "DEBUG"
    
    if ($DryRun) {
        Write-Log "[DRY RUN] 実際には実行されません" "WARNING"
        return $true
    }
    
    try {
        $Process = Start-Process -FilePath "python" -ArgumentList $Command.Split(' ') -Wait -PassThru -NoNewWindow
        
        if ($Process.ExitCode -eq 0) {
            Write-Log "$Description が正常に完了しました" "SUCCESS"
            return $true
        } else {
            Write-Log "$Description が失敗しました (終了コード: $($Process.ExitCode))" "ERROR"
            return $false
        }
    } catch {
        Write-Log "$Description の実行中にエラーが発生しました: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

function Test-PythonEnvironment {
    Write-Log "Python環境をチェック中..."
    
    try {
        $PythonVersion = python --version 2>&1
        Write-Log "Python バージョン: $PythonVersion"
        
        # 新しいCLIシステムの存在確認
        if (-not (Test-Path "src/keibabook/batch_cli.py")) {
            Write-Log "統合CLIシステムが見つかりません: src/keibabook/batch_cli.py" "ERROR"
            return $false
        }
        
        # モジュールのインポートテスト
        $TestCommand = "-m src.keibabook.batch_cli --help"
        $TestResult = python $TestCommand.Split(' ') 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Log "統合CLIシステムのインポートに失敗しました" "ERROR"
            Write-Log "エラー詳細: $TestResult" "ERROR"
            return $false
        }
        
        Write-Log "Python環境は正常です"
        return $true
        
    } catch {
        Write-Log "Python環境のチェック中にエラーが発生しました: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

function Get-EnvironmentInfo {
    Write-Log "=== 環境情報 ==="
    Write-Log "スクリプト: $ScriptName v$ScriptVersion"
    Write-Log "実行日時: $(Get-Date)"
    Write-Log "プロジェクトルート: $ProjectRoot"
    Write-Log "開始日: $StartDate"
    Write-Log "終了日: $(if ($EndDate) { $EndDate } else { $StartDate })"
    Write-Log "データタイプ: $DataTypes"
    Write-Log "リクエスト間隔: ${Delay}秒"
    Write-Log "Phase間待機: ${WaitBetweenPhases}秒"
    Write-Log "ドライラン: $DryRun"
    Write-Log "デバッグ: $Debug"
    Write-Log "================"
}

# ===== メイン処理関数 =====

function Invoke-ScheduleCollection {
    Write-Log "=== Phase 1: レース日程取得 ==="
    
    $Command = "-m src.keibabook.batch_cli schedule --start-date `"$StartDate`""
    
    if ($EndDate) {
        $Command += " --end-date `"$EndDate`""
    }
    
    $Command += " --delay $Delay"
    
    if ($Debug) {
        $Command += " --debug"
    }
    
    return Invoke-PythonCommand -Command $Command -Description "レース日程取得"
}

function Invoke-DataCollection {
    Write-Log "=== Phase 2: レースデータ取得 ==="
    
    $Command = "-m src.keibabook.batch_cli data --start-date `"$StartDate`""
    
    if ($EndDate) {
        $Command += " --end-date `"$EndDate`""
    }
    
    $Command += " --data-types `"$DataTypes`""
    $Command += " --delay $Delay"
    
    if ($Debug) {
        $Command += " --debug"
    }
    
    return Invoke-PythonCommand -Command $Command -Description "レースデータ取得"
}

function Invoke-FullProcessing {
    Write-Log "=== 全処理実行モード ==="
    
    $Command = "-m src.keibabook.batch_cli full --start-date `"$StartDate`""
    
    if ($EndDate) {
        $Command += " --end-date `"$EndDate`""
    }
    
    $Command += " --data-types `"$DataTypes`""
    $Command += " --delay $Delay"
    $Command += " --wait-between-phases $WaitBetweenPhases"
    
    if ($Debug) {
        $Command += " --debug"
    }
    
    return Invoke-PythonCommand -Command $Command -Description "全処理実行"
}

function Invoke-PostProcessing {
    Write-Log "=== 事後処理 ==="
    
    # データファイルの確認
    $DataDirs = @("data/keibabook/seiseki", "data/keibabook/race_ids")
    foreach ($Dir in $DataDirs) {
        if (Test-Path $Dir) {
            $FileCount = (Get-ChildItem $Dir -File | Measure-Object).Count
            $TotalSize = (Get-ChildItem $Dir -File | Measure-Object -Property Length -Sum).Sum
            $SizeKB = [math]::Round($TotalSize / 1KB, 2)
            Write-Log "ディレクトリ $Dir : $FileCount ファイル, ${SizeKB}KB"
        } else {
            Write-Log "ディレクトリが見つかりません: $Dir" "WARNING"
        }
    }
    
    # ログファイルサイズの確認
    if (Test-Path "logs") {
        $LogFiles = Get-ChildItem "logs" -Filter "*.log"
        $LogSize = ($LogFiles | Measure-Object -Property Length -Sum).Sum
        $LogSizeKB = [math]::Round($LogSize / 1KB, 2)
        Write-Log "ログファイル: $($LogFiles.Count) ファイル, ${LogSizeKB}KB"
    }
}

function Send-Notification {
    param([bool]$Success, [string]$Summary)
    
    # 将来的には Slack/Email 通知を実装
    $Status = if ($Success) { "成功" } else { "失敗" }
    $Message = "日次バッチ処理が$Status しました`n$Summary"
    
    Write-Log "通知: $Message"
    
    # 成功時はファイルに結果を保存
    if ($Success) {
        $ResultFile = "logs/daily_batch_result_$(Get-Date -Format 'yyyyMMdd').txt"
        $Message | Out-File -FilePath $ResultFile -Encoding UTF8
        Write-Log "結果ファイルを保存しました: $ResultFile"
    }
}

# ===== メイン実行処理 =====

function Main {
    try {
        Write-Log "=== 競馬ブック 日次バッチ処理 v2.0 開始 ==="
        
        # 環境情報表示
        Get-EnvironmentInfo
        
        # Python環境チェック
        if (-not (Test-PythonEnvironment)) {
            throw "Python環境のチェックに失敗しました"
        }
        
        # .env ファイルの存在確認
        if (-not (Test-Path ".env")) {
            Write-Log ".envファイルが見つかりません。認証情報を設定してください。" "WARNING"
        }
        
        # 終了日の設定
        if (-not $EndDate) {
            $EndDate = $StartDate
        }
        
        # 処理モードの判定と実行
        $Success = $false
        
        if ($ScheduleOnly) {
            # 日程取得のみ
            $Success = Invoke-ScheduleCollection
            
        } elseif ($DataOnly) {
            # データ取得のみ
            $Success = Invoke-DataCollection
            
        } else {
            # 全処理実行（デフォルト）
            $Success = Invoke-FullProcessing
        }
        
        # 事後処理
        Invoke-PostProcessing
        
        # 結果サマリー
        $Summary = @"
処理期間: $StartDate ～ $EndDate
データタイプ: $DataTypes
実行モード: $(if ($ScheduleOnly) { "日程のみ" } elseif ($DataOnly) { "データのみ" } else { "全処理" })
ログファイル: $LogFile
"@
        
        # 通知送信
        Send-Notification -Success $Success -Summary $Summary
        
        if ($Success) {
            Write-Log "=== 日次バッチ処理が正常に完了しました ===" "SUCCESS"
            exit 0
        } else {
            Write-Log "=== 日次バッチ処理でエラーが発生しました ===" "ERROR"
            exit 1
        }
        
    } catch {
        Write-Log "予期しないエラーが発生しました: $($_.Exception.Message)" "ERROR"
        Send-Notification -Success $false -Summary "予期しないエラー: $($_.Exception.Message)"
        exit 1
    }
}

# スクリプト実行
Main

# ===== 使用例 =====
<#
# 基本的な実行（今日のデータを全処理）
.\scripts\daily_batch_v2.ps1

# 特定日の処理
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04"

# 期間指定の処理
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/01" -EndDate "2025/02/07"

# 日程取得のみ
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04" -ScheduleOnly

# データ取得のみ
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04" -DataOnly

# デバッグモードで実行
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04" -Debug

# ドライラン（実際には実行しない）
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04" -DryRun

# カスタム設定での実行
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04" -DataTypes "seiseki" -Delay 5 -WaitBetweenPhases 15
#>