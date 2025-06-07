#!/bin/bash

# 日次競馬スクレイピングスクリプト
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
LOG_FILE="$LOG_DIR/daily_scraping_$DATE.log"

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

log "=== 日次競馬スクレイピングを開始 ==="

# 環境変数を読み込み
if [ -f ".env" ]; then
    source .env
    log "環境変数を .env から読み込みました"
else
    log "WARNING: .env ファイルが見つかりません"
fi

# 対象日付の設定（引数で指定可能）
TARGET_DATE=${1:-$(date '+%Y%m%d')}
log "対象日付: $TARGET_DATE"

# レースID一覧を定義（実際の運用では外部ファイルやAPIから取得）
# 形式: YYYYMMDDTTRR (YYYY=年, MM=月, DD=日, TT=競馬場コード, RR=レース番号)
declare -a RACE_IDS

# 東京競馬場（05）の例
TOKYO_RACES=(
    "${TARGET_DATE}0511"  # 1R
    "${TARGET_DATE}0512"  # 2R
    "${TARGET_DATE}0513"  # 3R
    "${TARGET_DATE}0514"  # 4R
    "${TARGET_DATE}0515"  # 5R
    "${TARGET_DATE}0516"  # 6R
    "${TARGET_DATE}0517"  # 7R
    "${TARGET_DATE}0518"  # 8R
    "${TARGET_DATE}0519"  # 9R
    "${TARGET_DATE}0520"  # 10R
    "${TARGET_DATE}0521"  # 11R
    "${TARGET_DATE}0522"  # 12R
)

# 中山競馬場（06）の例
NAKAYAMA_RACES=(
    "${TARGET_DATE}0611"
    "${TARGET_DATE}0612"
    "${TARGET_DATE}0613"
    "${TARGET_DATE}0614"
    "${TARGET_DATE}0615"
    "${TARGET_DATE}0616"
    "${TARGET_DATE}0617"
    "${TARGET_DATE}0618"
    "${TARGET_DATE}0619"
    "${TARGET_DATE}0620"
    "${TARGET_DATE}0621"
    "${TARGET_DATE}0622"
)

# 実行するレースIDの選択
# デフォルトは東京競馬場のみ
RACE_IDS=("${TOKYO_RACES[@]}")

# オプション: 両競馬場を処理する場合
# RACE_IDS=("${TOKYO_RACES[@]}" "${NAKAYAMA_RACES[@]}")

log "処理対象レース数: ${#RACE_IDS[@]}"

# 成功・失敗カウンタ
SUCCESS_COUNT=0
FAILURE_COUNT=0
TOTAL_COUNT=${#RACE_IDS[@]}

# 各レースの処理
for race_id in "${RACE_IDS[@]}"; do
    log "処理開始: レース $race_id"
    
    # メイン処理の実行
    if python3 main.py --race-id "$race_id" --mode scrape_and_parse >> "$LOG_FILE" 2>&1; then
        log "✅ レース $race_id の処理が完了"
        ((SUCCESS_COUNT++))
    else
        log "❌ レース $race_id の処理でエラーが発生"
        ((FAILURE_COUNT++))
        
        # エラー時の詳細ログ
        log "エラー詳細を確認してください: tail -50 $LOG_FILE"
    fi
    
    # アクセス間隔を空ける（競馬ブックへの負荷軽減）
    if [ ${#RACE_IDS[@]} -gt 1 ]; then
        log "待機中... (30秒)"
        sleep 30
    fi
done

# 結果サマリー
log "=== 処理結果サマリー ==="
log "総レース数: $TOTAL_COUNT"
log "成功: $SUCCESS_COUNT"
log "失敗: $FAILURE_COUNT"
log "成功率: $(( SUCCESS_COUNT * 100 / TOTAL_COUNT ))%"

# 成功したデータファイルの一覧
log "=== 生成されたデータファイル ==="
if [ $SUCCESS_COUNT -gt 0 ]; then
    find data/keibabook/seiseki/ -name "seiseki_${TARGET_DATE}*.json" -exec ls -la {} \; | tee -a "$LOG_FILE"
else
    log "データファイルは生成されませんでした"
fi

# エラー発生時の終了処理
if [ $FAILURE_COUNT -gt 0 ]; then
    log "⚠️  一部のレースでエラーが発生しました"
    
    # Slackやメール通知などを追加可能
    # notify_error "$FAILURE_COUNT/$TOTAL_COUNT レースでエラーが発生"
    
    exit 1
else
    log "✅ 全てのレースが正常に処理されました"
    exit 0
fi