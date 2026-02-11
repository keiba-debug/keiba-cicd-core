#!/bin/bash

# 高速日次競馬スクレイピングスクリプト v2.3
# RequestsScraperを使用した高速版（10-20倍高速化）
# 使用方法: ./scripts/fast_daily_scraping.sh [date]
# 例: ./scripts/fast_daily_scraping.sh 20250607

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# プロジェクトルートに移動
cd "$PROJECT_ROOT" || exit 1

# ログファイルの設定
LOG_DIR="logs"
DATE=$(date '+%Y%m%d_%H%M%S')
LOG_FILE="$LOG_DIR/fast_daily_scraping_v2.3_$DATE.log"

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

log "=== 🚀 高速日次競馬スクレイピング v2.3 を開始 ==="
log "🔥 RequestsScraperを使用（Selenium不使用）"
log "⚡ 並列処理対応（10-20倍高速化）"

# 環境変数を読み込み
if [ -f ".env" ]; then
    source .env
    log "環境変数を .env から読み込みました"
else
    log "WARNING: .env ファイルが見つかりません"
fi

# 対象日付の設定（引数で指定可能）
TARGET_DATE=${1:-$(date '+%Y%m%d')}
# fast_batch_cli用の日付形式に変換 (YYYY/MM/DD)
FORMATTED_DATE="${TARGET_DATE:0:4}/${TARGET_DATE:4:2}/${TARGET_DATE:6:2}"
log "対象日付: $TARGET_DATE ($FORMATTED_DATE)"

# パフォーマンス設定
DELAY="0.5"
MAX_WORKERS="8"
WAIT_BETWEEN_PHASES="2"

log "⚙️ パフォーマンス設定:"
log "   - リクエスト間隔: ${DELAY}秒"
log "   - 並列処理数: ${MAX_WORKERS}"
log "   - Phase間待機: ${WAIT_BETWEEN_PHASES}秒"

# 処理開始時刻を記録
START_TIME=$(date +%s)

# 高速版batch_cliを使用して全処理を一括実行
log "=== 🚀 超高速全処理実行 ==="
log "📊 取得データタイプ: seiseki, shutsuba, cyokyo, danwa + nittei"

if python3 -m src.keibabook.fast_batch_cli full \
    --start-date "$FORMATTED_DATE" \
    --delay "$DELAY" \
    --max-workers "$MAX_WORKERS" \
    --wait-between-phases "$WAIT_BETWEEN_PHASES" >> "$LOG_FILE" 2>&1; then
    
    SUCCESS_FLAG=true
    log "✅ 超高速全処理が完了しました"
else
    SUCCESS_FLAG=false
    log "❌ 超高速全処理でエラーが発生しました"
fi

# 処理時間計算
END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))
MINUTES=$((TOTAL_TIME / 60))
SECONDS=$((TOTAL_TIME % 60))

# 結果サマリー
log "=== 📊 処理結果サマリー ==="
log "対象日付: $TARGET_DATE"
log "処理方式: fast_batch_cli v2.3 システム（RequestsScraperによる高速化）"
log "⏱️ 総処理時間: ${MINUTES}分${SECONDS}秒"

if [ "$SUCCESS_FLAG" = true ]; then
    log "✅ 全ての処理が正常に完了しました"
    
    # 生成されたJSONファイルの確認
    log "=== 📁 生成されたJSONファイル ==="
    
    # JSONファイルの確認（data/keibabook/ 直下）
    JSON_BASE_DIR="data/keibabook"
    if [ -d "$JSON_BASE_DIR" ]; then
        # 各データタイプのファイル数をカウント
        for data_type in seiseki shutsuba cyokyo danwa; do
            JSON_COUNT=$(find "$JSON_BASE_DIR" -name "${data_type}_*${TARGET_DATE}*.json" 2>/dev/null | wc -l)
            log "📄 $data_type JSON: ${JSON_COUNT}件"
            
            # サンプルファイルを表示（最大3件）
            if [ $JSON_COUNT -gt 0 ]; then
                find "$JSON_BASE_DIR" -name "${data_type}_*${TARGET_DATE}*.json" 2>/dev/null | head -3 | while read file; do
                    if [ -f "$file" ]; then
                        SIZE=$(ls -lh "$file" | awk '{print $5}')
                        log "   └─ $(basename "$file") (${SIZE})"
                    fi
                done
            fi
        done
        
        # nittei JSONファイルの確認
        NITTEI_JSON="$JSON_BASE_DIR/nittei_${TARGET_DATE}.json"
        if [ -f "$NITTEI_JSON" ]; then
            SIZE=$(ls -lh "$NITTEI_JSON" | awk '{print $5}')
            log "📄 nittei JSON: 1件"
            log "   └─ $(basename "$NITTEI_JSON") (${SIZE})"
        fi
        
        # 合計ファイル数の表示
        TOTAL_JSON_COUNT=$(find "$JSON_BASE_DIR" -name "*${TARGET_DATE}*.json" 2>/dev/null | wc -l)
        log "📊 合計JSONファイル数: ${TOTAL_JSON_COUNT}件"
        
        # 合計ファイルサイズ
        TOTAL_SIZE=$(find "$JSON_BASE_DIR" -name "*${TARGET_DATE}*.json" -exec ls -l {} \; 2>/dev/null | awk '{sum += $5} END {print sum}')
        if [ -n "$TOTAL_SIZE" ] && [ "$TOTAL_SIZE" -gt 0 ]; then
            TOTAL_SIZE_MB=$((TOTAL_SIZE / 1024 / 1024))
            log "💾 合計ファイルサイズ: ${TOTAL_SIZE_MB}MB"
        fi
        
        # パフォーマンス統計
        if [ $TOTAL_JSON_COUNT -gt 0 ] && [ $TOTAL_TIME -gt 0 ]; then
            FILES_PER_SECOND=$(echo "scale=2; $TOTAL_JSON_COUNT / $TOTAL_TIME" | bc -l 2>/dev/null || echo "N/A")
            log "🚀 処理速度: ${FILES_PER_SECOND}ファイル/秒"
        fi
        
        # 従来版との比較（推定）
        ESTIMATED_OLD_TIME=$((TOTAL_TIME * 10))  # 10倍の時間がかかると仮定
        OLD_MINUTES=$((ESTIMATED_OLD_TIME / 60))
        OLD_SECONDS=$((ESTIMATED_OLD_TIME % 60))
        log "📈 従来版推定時間: ${OLD_MINUTES}分${OLD_SECONDS}秒（約10倍）"
        
    else
        log "⚠️ JSONディレクトリが見つかりません: $JSON_BASE_DIR"
    fi
    
    exit 0
else
    log "⚠️ 処理でエラーが発生しました"
    log "詳細はログファイルを確認してください: $LOG_FILE"
    
    # エラー詳細の表示
    log "=== ❌ エラー詳細 ==="
    tail -20 "$LOG_FILE" | grep -E "(ERROR|❌|Exception)" | tail -5
    
    # エラー通知（必要に応じて有効化）
    # notify_error "高速日次スクレイピングでエラーが発生: $TARGET_DATE"
    
    exit 1
fi 