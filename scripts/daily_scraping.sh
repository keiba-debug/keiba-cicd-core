#!/bin/bash

# 日次競馬スクレイピングスクリプト v2.1
# 新しいbatch_cliシステム（同一フォルダ保存）に対応
# 使用方法: ./scripts/daily_scraping.sh [date]
# 例: ./scripts/daily_scraping.sh 20250204

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# プロジェクトルートに移動
cd "$PROJECT_ROOT" || exit 1

# ログファイルの設定
LOG_DIR="logs"
DATE=$(date '+%Y%m%d_%H%M%S')
LOG_FILE="$LOG_DIR/daily_scraping_v2_$DATE.log"

# ログ関数
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" | tee -a "$LOG_FILE"
}

# エラーハンドリング
error_exit() {
    log "ERROR: $1"
    exit 1
}

# 必要なディレクトリを作成
mkdir -p "$LOG_DIR"

log "=== 日次競馬スクレイピング v2.1 を開始 ==="

# 環境変数を読み込み
if [ -f ".env" ]; then
    source .env
    log "環境変数を .env から読み込みました"
else
    log "WARNING: .env ファイルが見つかりません"
fi

# 対象日付の設定（引数で指定可能）
TARGET_DATE=${1:-$(date '+%Y%m%d')}
# batch_cli用の日付形式に変換 (YYYY/MM/DD)
FORMATTED_DATE="${TARGET_DATE:0:4}/${TARGET_DATE:4:2}/${TARGET_DATE:6:2}"
log "対象日付: $TARGET_DATE ($FORMATTED_DATE)"

# 新しいbatch_cliシステムを使用
log "=== Phase 1: レース日程取得 ==="
if python3 -m src.keibabook.batch_cli schedule --start-date "$FORMATTED_DATE" --delay 3 >> "$LOG_FILE" 2>&1; then
    log "✅ レース日程取得が完了"
else
    error_exit "❌ レース日程取得でエラーが発生"
fi

# Phase間の待機
log "Phase間待機中... (5秒)"
sleep 5

# 全データタイプを取得（デフォルト: seiseki,shutsuba,cyokyo,danwa）
log "=== Phase 2: 全レースデータ取得 ==="
log "取得データタイプ: seiseki, shutsuba, cyokyo, danwa"

if python3 -m src.keibabook.batch_cli data --start-date "$FORMATTED_DATE" --delay 3 >> "$LOG_FILE" 2>&1; then
    log "✅ 全レースデータ取得が完了"
    SUCCESS_FLAG=true
else
    log "❌ レースデータ取得でエラーが発生"
    SUCCESS_FLAG=false
fi

# 結果サマリー
log "=== 処理結果サマリー ==="
log "対象日付: $TARGET_DATE"
log "処理方式: batch_cli v2.1 システム（同一フォルダ保存）"

if [ "$SUCCESS_FLAG" = true ]; then
    log "✅ 全ての処理が正常に完了しました"
    
    # 生成されたJSONファイルの確認（新しいディレクトリ構造）
    log "=== 生成されたJSONファイル ==="
    
    # JSONファイルの確認（data/keibabook/ 直下）
    JSON_BASE_DIR="data/keibabook"
    for data_type in seiseki shutsuba cyokyo danwa; do
        if [ -d "$JSON_BASE_DIR" ]; then
            JSON_COUNT=$(find "$JSON_BASE_DIR" -name "${data_type}_*${TARGET_DATE}*.json" | wc -l)
            log "$data_type JSON: ${JSON_COUNT}件"
            if [ $JSON_COUNT -gt 0 ]; then
                find "$JSON_BASE_DIR" -name "${data_type}_*${TARGET_DATE}*.json" -exec ls -la {} \; | head -3 | tee -a "$LOG_FILE"
            fi
        fi
    done
    
    # nittei JSONファイルの確認
    NITTEI_JSON="$JSON_BASE_DIR/nittei_${TARGET_DATE}.json"
    if [ -f "$NITTEI_JSON" ]; then
        log "nittei JSON: 1件"
        ls -la "$NITTEI_JSON" | tee -a "$LOG_FILE"
    fi
    
    # 合計ファイル数の表示
    TOTAL_JSON_COUNT=$(find "$JSON_BASE_DIR" -name "*${TARGET_DATE}*.json" | wc -l)
    log "合計JSONファイル数: ${TOTAL_JSON_COUNT}件"
    
    # ファイル一覧の表示（デバッグ用）
    log "=== 保存されたファイル一覧 ==="
    find "$JSON_BASE_DIR" -name "*${TARGET_DATE}*.json" | sort | tee -a "$LOG_FILE"
    
    exit 0
else
    log "⚠️  一部の処理でエラーが発生しました"
    log "詳細はログファイルを確認してください: $LOG_FILE"
    
    # エラー通知（必要に応じて有効化）
    # notify_error "日次スクレイピングでエラーが発生: $TARGET_DATE"
    
    exit 1
fi