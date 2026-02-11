#!/bin/bash

# 週次競馬スクレイピングスクリプト
# 使用方法: ./scripts/weekly_scraping.sh [start_date] [end_date]
# 例: ./scripts/weekly_scraping.sh 20250201 20250207

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# プロジェクトルートに移動
cd "$PROJECT_ROOT" || exit 1

# ログファイルの設定
LOG_DIR="logs"
DATE=$(date '+%Y%m%d_%H%M%S')
LOG_FILE="$LOG_DIR/weekly_scraping_$DATE.log"

# ログ関数
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" | tee -a "$LOG_FILE"
}

# 必要なディレクトリを作成
mkdir -p "$LOG_DIR"

log "=== 週次競馬スクレイピングを開始 ==="

# 環境変数を読み込み
if [ -f ".env" ]; then
    source .env
    log "環境変数を .env から読み込みました"
else
    log "WARNING: .env ファイルが見つかりません"
fi

# 日付範囲の設定
START_DATE=${1:-$(date -d "last Sunday" '+%Y%m%d')}
END_DATE=${2:-$(date -d "next Saturday" '+%Y%m%d')}

log "処理期間: $START_DATE から $END_DATE"

# 主要競馬場のコードリスト
# 01:札幌, 02:函館, 03:福島, 04:新潟, 05:東京, 06:中山, 07:中京, 08:京都, 09:阪神, 10:小倉
KEIBA_VENUES=(
    "05"  # 東京
    "06"  # 中山
    "09"  # 阪神
    "08"  # 京都
    "07"  # 中京
    "10"  # 小倉
    "04"  # 新潟
    "03"  # 福島
    "01"  # 札幌
    "02"  # 函館
)

# 処理対象日のリストを生成
PROCESS_DATES=()
current_date="$START_DATE"

while [ "$current_date" -le "$END_DATE" ]; do
    # 土日のみを処理対象とする
    day_of_week=$(date -d "$current_date" '+%u')  # 1=月曜, 7=日曜
    
    if [ "$day_of_week" -eq 6 ] || [ "$day_of_week" -eq 7 ]; then  # 土曜または日曜
        PROCESS_DATES+=("$current_date")
    fi
    
    # 次の日へ
    current_date=$(date -d "$current_date + 1 day" '+%Y%m%d')
done

log "処理対象日: ${PROCESS_DATES[*]}"

# 統計カウンタ
TOTAL_SUCCESS=0
TOTAL_FAILURE=0
TOTAL_RACES=0

# 各日付の処理
for process_date in "${PROCESS_DATES[@]}"; do
    log "=== $process_date の処理開始 ==="
    
    day_success=0
    day_failure=0
    day_races=0
    
    # 各競馬場の処理
    for venue in "${KEIBA_VENUES[@]}"; do
        log "競馬場 $venue の処理開始 ($process_date)"
        
        # 各レース（1R-12R）の処理
        for race_num in {11..22}; do  # 11-22 = 1R-12R
            race_id="${process_date}${venue}${race_num}"
            
            log "処理中: $race_id"
            ((day_races++))
            ((TOTAL_RACES++))
            
            # メイン処理の実行
            if timeout 300 python3 src/keibabook/main.py --race-id "$race_id" --mode scrape_and_parse >> "$LOG_FILE" 2>&1; then
                log "✅ $race_id 完了"
                ((day_success++))
                ((TOTAL_SUCCESS++))
            else
                log "❌ $race_id エラー"
                ((day_failure++))
                ((TOTAL_FAILURE++))
            fi
            
            # 競馬ブックへの負荷軽減のため待機
            sleep 15
        done
        
        # 競馬場間の待機
        log "競馬場 $venue 完了。次の競馬場まで60秒待機..."
        sleep 60
    done
    
    # 日別サマリー
    log "=== $process_date の処理完了 ==="
    log "処理レース数: $day_races"
    log "成功: $day_success"
    log "失敗: $day_failure"
    log "成功率: $(( day_success * 100 / day_races ))%"
    
    # 日付間の待機
    if [ ${#PROCESS_DATES[@]} -gt 1 ]; then
        log "次の日付まで120秒待機..."
        sleep 120
    fi
done

# 週次サマリー
log "=== 週次処理結果サマリー ==="
log "処理期間: $START_DATE - $END_DATE"
log "総レース数: $TOTAL_RACES"
log "成功: $TOTAL_SUCCESS"
log "失敗: $TOTAL_FAILURE"
log "全体成功率: $(( TOTAL_SUCCESS * 100 / TOTAL_RACES ))%"

# 生成されたファイルの統計
log "=== 生成されたファイル統計 ==="
for process_date in "${PROCESS_DATES[@]}"; do
    file_count=$(find data/keibabook/seiseki/ -name "seiseki_${process_date}*.json" | wc -l)
    log "$process_date: ${file_count}ファイル"
done

# データファイルの詳細リスト
total_files=$(find data/keibabook/seiseki/ -name "seiseki_*.json" | wc -l)
log "総データファイル数: $total_files"

# 最新ファイルの例
log "=== 最新生成ファイル（最大10件） ==="
find data/keibabook/seiseki/ -name "seiseki_*.json" -type f -printf '%T@ %p\n' | \
    sort -nr | head -10 | while read -r timestamp file; do
    file_date=$(date -d "@$timestamp" '+%Y-%m-%d %H:%M:%S')
    file_size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "unknown")
    log "$file ($file_date, ${file_size}bytes)"
done

# エラー発生時の処理
if [ $TOTAL_FAILURE -gt 0 ]; then
    log "⚠️  一部のレースでエラーが発生しました"
    
    # エラー率が50%を超える場合はアラート
    error_rate=$(( TOTAL_FAILURE * 100 / TOTAL_RACES ))
    if [ $error_rate -gt 50 ]; then
        log "🚨 エラー率が50%を超えています($error_rate%)。システムを確認してください"
        
        # 通知の送信（例：メール、Slack等）
        # send_alert "週次スクレイピングでエラー率が${error_rate}%に達しました"
    fi
    
    # エラーの詳細分析
    log "=== エラー分析 ==="
    log "詳細なエラーログは以下で確認してください:"
    log "grep '❌\\|ERROR\\|Failed' $LOG_FILE"
    
    exit 1
else
    log "✅ 全てのレースが正常に処理されました"
    
    # 成功時の後処理
    # - データベースへの投入
    # - レポートの生成
    # - 成功通知の送信等
    
    exit 0
fi