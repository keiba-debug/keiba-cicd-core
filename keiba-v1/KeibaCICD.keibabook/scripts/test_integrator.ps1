# 統合機能テストスクリプト (PowerShell)
# データ統合機能の動作確認用

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  競馬データ統合システム テスト" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan

# プロジェクトルートに移動
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptPath
Set-Location $projectRoot

Write-Host "`n[1] 環境確認" -ForegroundColor Yellow
Write-Host "現在のディレクトリ: $(Get-Location)"
Write-Host "Python バージョン:"
python --version

# 仮想環境のアクティベート確認
Write-Host "`n[2] 仮想環境の確認" -ForegroundColor Yellow
if (Test-Path "venv\Scripts\activate.ps1") {
    Write-Host "仮想環境が存在します" -ForegroundColor Green
} else {
    Write-Host "仮想環境が見つかりません。セットアップを実行してください。" -ForegroundColor Red
    exit 1
}

# テスト用の日付（例：2024/12/29）
$testDate = "2024/12/29"
$testRaceId = "202412290511"  # 阪神5R

Write-Host "`n[3] テストデータの確認" -ForegroundColor Yellow
Write-Host "テスト日付: $testDate"
Write-Host "テストレースID: $testRaceId"

# データの存在確認
Write-Host "`n[4] 既存データの確認" -ForegroundColor Yellow
$dataRoot = $env:KEIBA_DATA_ROOT_DIR
if (-not $dataRoot) {
    $dataRoot = "./data/keibabook"
}

$shutsubaFile = "$dataRoot/shutsuba_$testRaceId.json"
$cyokyoFile = "$dataRoot/cyokyo_$testRaceId.json"
$danwaFile = "$dataRoot/danwa_$testRaceId.json"

if (Test-Path $shutsubaFile) {
    Write-Host "✅ 出走表データ: 存在" -ForegroundColor Green
} else {
    Write-Host "❌ 出走表データ: なし" -ForegroundColor Red
}

if (Test-Path $cyokyoFile) {
    Write-Host "✅ 調教データ: 存在" -ForegroundColor Green
} else {
    Write-Host "❌ 調教データ: なし" -ForegroundColor Red
}

if (Test-Path $danwaFile) {
    Write-Host "✅ 厩舎談話データ: 存在" -ForegroundColor Green
} else {
    Write-Host "❌ 厩舎談話データ: なし" -ForegroundColor Red
}

# 統合ファイル生成テスト
Write-Host "`n[5] 統合ファイル生成テスト" -ForegroundColor Yellow
Write-Host "実行コマンド: python -m src.keibabook.integrator_cli single --race-id $testRaceId"

python -m src.keibabook.integrator_cli single --race-id $testRaceId

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 統合ファイル生成成功" -ForegroundColor Green
    
    # 生成されたファイルの確認
    $integratedFile = "$dataRoot/integrated/integrated_$testRaceId.json"
    if (Test-Path $integratedFile) {
        Write-Host "✅ 統合ファイルが作成されました: $integratedFile" -ForegroundColor Green
        
        # ファイルサイズ表示
        $fileInfo = Get-Item $integratedFile
        $sizeKB = [math]::Round($fileInfo.Length / 1KB, 2)
        Write-Host "   ファイルサイズ: $sizeKB KB" -ForegroundColor Cyan
        
        # 内容の簡易確認
        Write-Host "`n[6] 統合ファイルの内容確認" -ForegroundColor Yellow
        $content = Get-Content $integratedFile -Raw | ConvertFrom-Json
        
        Write-Host "メタデータ:"
        Write-Host "  - レースID: $($content.meta.race_id)"
        Write-Host "  - データバージョン: $($content.meta.data_version)"
        Write-Host "  - 作成日時: $($content.meta.created_at)"
        
        Write-Host "`nレース情報:"
        Write-Host "  - 日付: $($content.race_info.date)"
        Write-Host "  - 競馬場: $($content.race_info.venue)"
        Write-Host "  - レース番号: $($content.race_info.race_number)R"
        Write-Host "  - レース名: $($content.race_info.race_name)"
        
        Write-Host "`n出走頭数: $($content.entries.Count)頭"
        
        Write-Host "`nデータソース状態:"
        $content.meta.data_sources.PSObject.Properties | ForEach-Object {
            $status = if ($_.Value -eq "取得済") { "✅" } else { "❌" }
            Write-Host "  $status $($_.Name): $($_.Value)"
        }
        
    } else {
        Write-Host "❌ 統合ファイルが見つかりません" -ForegroundColor Red
    }
} else {
    Write-Host "❌ 統合ファイル生成失敗" -ForegroundColor Red
}

# バッチ処理テスト
Write-Host "`n[7] バッチ処理テスト（オプション）" -ForegroundColor Yellow
$runBatch = Read-Host "指定日の全レース統合を実行しますか？ (y/n)"

if ($runBatch -eq 'y') {
    $batchDate = Read-Host "処理する日付を入力してください (YYYY/MM/DD)"
    Write-Host "実行コマンド: python -m src.keibabook.integrator_cli batch --date $batchDate"
    
    python -m src.keibabook.integrator_cli batch --date $batchDate
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ バッチ処理成功" -ForegroundColor Green
    } else {
        Write-Host "❌ バッチ処理失敗" -ForegroundColor Red
    }
}

# 分析レポートテスト
Write-Host "`n[8] 分析レポート生成テスト" -ForegroundColor Yellow
Write-Host "実行コマンド: python -m src.keibabook.integrator_cli analyze --race-id $testRaceId"

python -m src.keibabook.integrator_cli analyze --race-id $testRaceId

Write-Host "`n===========================================" -ForegroundColor Cyan
Write-Host "  テスト完了" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan