# 競馬ブック データ取得システム v2.0 - 統合テストスクリプト

param(
    [Parameter(Mandatory=$false)]
    [string]$TestDate = "2025/02/04",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipSystemTest,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipCliTest,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipLegacyTest,
    
    [Parameter(Mandatory=$false)]
    [switch]$Verbose,
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

# ===== 設定・初期化 =====

$ErrorActionPreference = "Stop"
$ScriptName = "IntegrationTest_v2"
$ScriptVersion = "2.0.0"
$LogFile = "logs/integration_test_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# プロジェクトルートディレクトリの検出
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "$ProjectRoot/src/keibabook/batch_cli.py")) {
    Write-Error "プロジェクトルートが見つかりません: $ProjectRoot"
    exit 1
}

Set-Location $ProjectRoot

# ===== テスト結果管理 =====

$TestResults = @{
    SystemTests = @()
    CliTests = @()
    LegacyTests = @()
    TotalTests = 0
    PassedTests = 0
    FailedTests = 0
}

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

function Test-Command {
    param(
        [string]$TestName,
        [string]$Command,
        [string]$Category,
        [bool]$ExpectSuccess = $true,
        [string]$ExpectedOutput = ""
    )
    
    $TestResults.TotalTests++
    
    Write-Log "=== テスト実行: $TestName ===" "TEST"
    Write-Log "コマンド: $Command" "DEBUG"
    
    if ($DryRun) {
        Write-Log "[DRY RUN] 実際には実行されません" "WARNING"
        $TestResults.PassedTests++
        $TestResults.$Category += @{
            Name = $TestName
            Status = "SKIPPED (DRY RUN)"
            Command = $Command
            Output = ""
            Duration = "0s"
        }
        return $true
    }
    
    $StartTime = Get-Date
    
    try {
        $Process = Start-Process -FilePath "python" -ArgumentList $Command.Split(' ') -Wait -PassThru -RedirectStandardOutput "temp_output.txt" -RedirectStandardError "temp_error.txt" -NoNewWindow
        
        $Output = ""
        $ErrorOutput = ""
        
        if (Test-Path "temp_output.txt") {
            $Output = Get-Content "temp_output.txt" -Raw
            Remove-Item "temp_output.txt" -Force
        }
        
        if (Test-Path "temp_error.txt") {
            $ErrorOutput = Get-Content "temp_error.txt" -Raw
            Remove-Item "temp_error.txt" -Force
        }
        
        $Duration = "{0:F1}s" -f ((Get-Date) - $StartTime).TotalSeconds
        
        $Success = ($Process.ExitCode -eq 0) -eq $ExpectSuccess
        
        if ($Success) {
            if ($ExpectedOutput -and $Output -notmatch $ExpectedOutput) {
                $Success = $false
                Write-Log "期待された出力が見つかりませんでした: $ExpectedOutput" "ERROR"
            }
        }
        
        if ($Success) {
            Write-Log "✅ テスト成功: $TestName ($Duration)" "SUCCESS"
            $TestResults.PassedTests++
            $Status = "PASSED"
        } else {
            Write-Log "❌ テスト失敗: $TestName ($Duration)" "ERROR"
            Write-Log "終了コード: $($Process.ExitCode)" "ERROR"
            if ($ErrorOutput) {
                Write-Log "エラー出力: $ErrorOutput" "ERROR"
            }
            $TestResults.FailedTests++
            $Status = "FAILED"
        }
        
        if ($Verbose) {
            Write-Log "出力: $Output" "DEBUG"
        }
        
        $TestResults.$Category += @{
            Name = $TestName
            Status = $Status
            Command = $Command
            Output = $Output
            ErrorOutput = $ErrorOutput
            Duration = $Duration
            ExitCode = $Process.ExitCode
        }
        
        return $Success
        
    } catch {
        $Duration = "{0:F1}s" -f ((Get-Date) - $StartTime).TotalSeconds
        Write-Log "❌ テスト例外: $TestName - $($_.Exception.Message)" "ERROR"
        $TestResults.FailedTests++
        
        $TestResults.$Category += @{
            Name = $TestName
            Status = "EXCEPTION"
            Command = $Command
            Output = ""
            ErrorOutput = $_.Exception.Message
            Duration = $Duration
            ExitCode = -1
        }
        
        return $false
    }
}

function Test-FileExists {
    param([string]$FilePath, [string]$Description)
    
    if (Test-Path $FilePath) {
        Write-Log "✅ ファイル存在確認: $Description" "SUCCESS"
        return $true
    } else {
        Write-Log "❌ ファイル未発見: $Description - $FilePath" "ERROR"
        return $false
    }
}

# ===== システムテスト =====

function Invoke-SystemTests {
    Write-Log "=== システム環境テスト開始 ===" "SECTION"
    
    # Python環境テスト
    Test-Command -TestName "Python バージョン確認" -Command "--version" -Category "SystemTests"
    
    # プロジェクト構造テスト
    $RequiredFiles = @(
        "src/keibabook/batch_cli.py",
        "src/keibabook/main.py",
        "src/keibabook/batch/__init__.py",
        "src/keibabook/batch/core/common.py",
        "src/keibabook/batch/data_fetcher.py",
        "src/keibabook/scrapers/legacy_scrapers.py"
    )
    
    foreach ($File in $RequiredFiles) {
        $TestResults.TotalTests++
        if (Test-FileExists -FilePath $File -Description $File) {
            $TestResults.PassedTests++
            $TestResults.SystemTests += @{
                Name = "ファイル存在: $File"
                Status = "PASSED"
                Command = "Test-Path $File"
                Output = "File exists"
                Duration = "0s"
            }
        } else {
            $TestResults.FailedTests++
            $TestResults.SystemTests += @{
                Name = "ファイル存在: $File"
                Status = "FAILED"
                Command = "Test-Path $File"
                Output = "File not found"
                Duration = "0s"
            }
        }
    }
    
    # 依存関係テスト
    Test-Command -TestName "依存関係チェック" -Command "-c 'import requests, bs4, selenium'" -Category "SystemTests"
    
    Write-Log "=== システム環境テスト完了 ===" "SECTION"
}

# ===== 統合CLIテスト =====

function Invoke-CliTests {
    Write-Log "=== 統合CLIシステムテスト開始 ===" "SECTION"
    
    # ヘルプ表示テスト
    Test-Command -TestName "CLIヘルプ表示" -Command "-m src.keibabook.batch_cli --help" -Category "CliTests" -ExpectedOutput "競馬ブック バッチ処理システム"
    
    # サブコマンドヘルプテスト
    Test-Command -TestName "schedule ヘルプ" -Command "-m src.keibabook.batch_cli schedule --help" -Category "CliTests" -ExpectedOutput "レース日程を取得"
    Test-Command -TestName "data ヘルプ" -Command "-m src.keibabook.batch_cli data --help" -Category "CliTests" -ExpectedOutput "レースデータを取得"
    Test-Command -TestName "full ヘルプ" -Command "-m src.keibabook.batch_cli full --help" -Category "CliTests" -ExpectedOutput "日程取得からデータ取得まで"
    
    # バッチモジュールインポートテスト
    Test-Command -TestName "バッチモジュールインポート" -Command "-c 'from src.keibabook.batch import DataFetcher, parse_date, BatchStats; print(""Import success"")'" -Category "CliTests" -ExpectedOutput "Import success"
    
    # 日付パース機能テスト
    Test-Command -TestName "日付パース機能" -Command "-c 'from src.keibabook.batch import parse_date; print(parse_date(""2025/02/04""))'" -Category "CliTests" -ExpectedOutput "2025-02-04"
    
    # 共通ユーティリティテスト
    Test-Command -TestName "共通ユーティリティ" -Command "-c 'from src.keibabook.batch.core.common import ensure_batch_directories; dirs = ensure_batch_directories(); print(len(dirs))'" -Category "CliTests"
    
    Write-Log "=== 統合CLIシステムテスト完了 ===" "SECTION"
}

# ===== レガシーシステムテスト =====

function Invoke-LegacyTests {
    Write-Log "=== レガシーシステムテスト開始 ===" "SECTION"
    
    # main.py ヘルプテスト
    Test-Command -TestName "main.py ヘルプ表示" -Command "src/keibabook/main.py --help" -Category "LegacyTests" -ExpectedOutput "race-id"
    
    # スクレイパーインポートテスト
    Test-Command -TestName "スクレイパーインポート" -Command "-c 'from src.keibabook.scrapers import KeibabookScraper, RequestsScraper, RaceIdExtractor; print(""Scrapers imported"")'" -Category "LegacyTests" -ExpectedOutput "Scrapers imported"
    
    # レガシースクレイパーインポートテスト
    Test-Command -TestName "レガシースクレイパーインポート" -Command "-c 'from src.keibabook.scrapers import DanwaScraper, SyutubaScraper; print(""Legacy scrapers imported"")'" -Category "LegacyTests" -ExpectedOutput "Legacy scrapers imported"
    
    # レースID抽出テスト
    Test-Command -TestName "レースID抽出機能" -Command "-c 'from src.keibabook.scrapers import RaceIdExtractor; print(RaceIdExtractor.extract_from_url(""https://p.keibabook.co.jp/cyuou/seiseki/202502041211""))'" -Category "LegacyTests" -ExpectedOutput "202502041211"
    
    # パーサーインポートテスト
    Test-Command -TestName "パーサーインポート" -Command "-c 'from src.keibabook.parsers.seiseki_parser import SeisekiParser; print(""Parser imported"")'" -Category "LegacyTests" -ExpectedOutput "Parser imported"
    
    Write-Log "=== レガシーシステムテスト完了 ===" "SECTION"
}

# ===== 実際のデータ処理テスト（軽量） =====

function Invoke-LightDataTests {
    Write-Log "=== 軽量データ処理テスト開始 ===" "SECTION"
    
    # 既存HTMLファイルでのパーステスト
    $HtmlFiles = Get-ChildItem "data/debug/*.html" -ErrorAction SilentlyContinue
    if ($HtmlFiles) {
        $SampleHtml = $HtmlFiles[0].FullName
        Test-Command -TestName "HTMLパーステスト" -Command "src/keibabook/main.py --mode parse_only --html-file `"$SampleHtml`" --race-id 202502041211" -Category "CliTests"
    } else {
        Write-Log "⚠️ HTMLテストファイルが見つかりません - パーステストをスキップ" "WARNING"
    }
    
    Write-Log "=== 軽量データ処理テスト完了 ===" "SECTION"
}

# ===== 結果サマリー =====

function Show-TestSummary {
    Write-Log "=== テスト結果サマリー ===" "SECTION"
    
    $PassRate = if ($TestResults.TotalTests -gt 0) { 
        ($TestResults.PassedTests / $TestResults.TotalTests * 100) 
    } else { 
        0 
    }
    
    Write-Log "総テスト数: $($TestResults.TotalTests)" "INFO"
    Write-Log "成功: $($TestResults.PassedTests)" "SUCCESS"
    Write-Log "失敗: $($TestResults.FailedTests)" "ERROR"
    Write-Log "成功率: {0:F1}%" -f $PassRate "INFO"
    
    # カテゴリ別サマリー
    $Categories = @("SystemTests", "CliTests", "LegacyTests")
    foreach ($Category in $Categories) {
        if ($TestResults.$Category.Count -gt 0) {
            $CategoryPassed = ($TestResults.$Category | Where-Object { $_.Status -eq "PASSED" }).Count
            $CategoryTotal = $TestResults.$Category.Count
            Write-Log "$Category : $CategoryPassed/$CategoryTotal" "INFO"
        }
    }
    
    # 失敗テストの詳細
    if ($TestResults.FailedTests -gt 0) {
        Write-Log "=== 失敗テスト詳細 ===" "ERROR"
        foreach ($Category in $Categories) {
            $FailedTests = $TestResults.$Category | Where-Object { $_.Status -ne "PASSED" -and $_.Status -ne "SKIPPED (DRY RUN)" }
            foreach ($Test in $FailedTests) {
                Write-Log "❌ $($Test.Name) - $($Test.Status)" "ERROR"
                if ($Test.ErrorOutput) {
                    Write-Log "   エラー: $($Test.ErrorOutput)" "ERROR"
                }
            }
        }
    }
    
    # 結果ファイル保存
    $ResultFile = "logs/integration_test_result_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    $TestResults | ConvertTo-Json -Depth 3 | Out-File -FilePath $ResultFile -Encoding UTF8
    Write-Log "詳細結果をファイルに保存しました: $ResultFile" "INFO"
    
    Write-Log "=== テスト結果サマリー完了 ===" "SECTION"
}

# ===== メイン実行処理 =====

function Main {
    try {
        Write-Log "=== 競馬ブック データ取得システム v2.0 統合テスト開始 ===" "INFO"
        Write-Log "スクリプト: $ScriptName v$ScriptVersion" "INFO"
        Write-Log "実行日時: $(Get-Date)" "INFO"
        Write-Log "プロジェクトルート: $ProjectRoot" "INFO"
        Write-Log "テスト日付: $TestDate" "INFO"
        Write-Log "ドライラン: $DryRun" "INFO"
        
        # システムテスト実行
        if (-not $SkipSystemTest) {
            Invoke-SystemTests
        } else {
            Write-Log "システムテストをスキップしました" "WARNING"
        }
        
        # 統合CLIテスト実行
        if (-not $SkipCliTest) {
            Invoke-CliTests
        } else {
            Write-Log "統合CLIテストをスキップしました" "WARNING"
        }
        
        # レガシーシステムテスト実行
        if (-not $SkipLegacyTest) {
            Invoke-LegacyTests
        } else {
            Write-Log "レガシーシステムテストをスキップしました" "WARNING"
        }
        
        # 軽量データ処理テスト
        Invoke-LightDataTests
        
        # 結果サマリー表示
        Show-TestSummary
        
        # 最終判定
        if ($TestResults.FailedTests -eq 0) {
            Write-Log "🎉 全てのテストが成功しました！" "SUCCESS"
            exit 0
        } else {
            Write-Log "⚠️ 一部のテストが失敗しました。" "ERROR"
            exit 1
        }
        
    } catch {
        Write-Log "予期しないエラーが発生しました: $($_.Exception.Message)" "ERROR"
        exit 1
    }
}

# スクリプト実行
Main

# ===== 使用例 =====
<#
# 基本的な実行
.\scripts\integration_test_v2.ps1

# 特定の日付でテスト
.\scripts\integration_test_v2.ps1 -TestDate "2025/02/04"

# 一部のテストをスキップ
.\scripts\integration_test_v2.ps1 -SkipLegacyTest

# 詳細ログ付きで実行
.\scripts\integration_test_v2.ps1 -Verbose

# ドライラン（実際には実行しない）
.\scripts\integration_test_v2.ps1 -DryRun
#>