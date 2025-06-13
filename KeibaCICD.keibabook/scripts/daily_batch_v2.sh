#!/bin/bash
# 競馬ブック データ取得 - 日次バッチスクリプト v2.0
# 新しい統合CLIシステム対応版（Linux/macOS）

set -euo pipefail

# ===== 設定・初期化 =====

SCRIPT_NAME="DailyBatch_v2"
SCRIPT_VERSION="2.0.0"
LOG_FILE="logs/daily_batch_$(date '+%Y%m%d_%H%M%S').log"

# デフォルト値
START_DATE="${START_DATE:-$(date '+%Y/%m/%d')}"
END_DATE="${END_DATE:-}"
DATA_TYPES="${DATA_TYPES:-seiseki,shutsuba}"
DELAY="${DELAY:-3}"
WAIT_BETWEEN_PHASES="${WAIT_BETWEEN_PHASES:-10}"
SCHEDULE_ONLY="${SCHEDULE_ONLY:-false}"
DATA_ONLY="${DATA_ONLY:-false}"
DEBUG="${DEBUG:-false}"
DRY_RUN="${DRY_RUN:-false}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# プロジェクトルートディレクトリの検出
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if [ ! -f "src/keibabook/batch_cli.py" ]; then
    echo "ERROR: 統合CLIシステムが見つかりません: src/keibabook/batch_cli.py" >&2
    exit 1
fi

# ===== ヘルパー関数 =====

log() {
    local level="${2:-INFO}"
    local message="$1"
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    local log_message="[$timestamp] [$level] $message"
    
    echo "$log_message"
    
    # ログファイルに出力
    mkdir -p logs
    echo "$log_message" >> "$LOG_FILE"
}

invoke_python_command() {
    local command="$1"
    local description="$2"
    
    log "実行中: $description"
    log "コマンド: python $command" "DEBUG"
    
    if [ "$DRY_RUN" = "true" ]; then
        log "[DRY RUN] 実際には実行されません" "WARNING"
        return 0
    fi
    
    if python $command; then
        log "$description が正常に完了しました" "SUCCESS"
        return 0
    else
        log "$description が失敗しました (終了コード: $?)" "ERROR"
        return 1
    fi
}

test_python_environment() {
    log "Python環境をチェック中..."
    
    # Pythonバージョン確認
    local python_version
    if ! python_version="$(python --version 2>&1)"; then
        log "Pythonが見つかりません" "ERROR"
        return 1
    fi
    log "Python バージョン: $python_version"
    
    # 統合CLIシステムの存在確認
    if [ ! -f "src/keibabook/batch_cli.py" ]; then
        log "統合CLIシステムが見つかりません: src/keibabook/batch_cli.py" "ERROR"
        return 1
    fi
    
    # モジュールのインポートテスト
    if ! python -m src.keibabook.batch_cli --help >/dev/null 2>&1; then
        log "統合CLIシステムのインポートに失敗しました" "ERROR"
        return 1
    fi
    
    log "Python環境は正常です"
    return 0
}

show_environment_info() {
    log "=== 環境情報 ==="
    log "スクリプト: $SCRIPT_NAME v$SCRIPT_VERSION"
    log "実行日時: $(date)"
    log "プロジェクトルート: $PROJECT_ROOT"
    log "開始日: $START_DATE"
    log "終了日: ${END_DATE:-$START_DATE}"
    log "データタイプ: $DATA_TYPES"
    log "リクエスト間隔: ${DELAY}秒"
    log "Phase間待機: ${WAIT_BETWEEN_PHASES}秒"
    log "ドライラン: $DRY_RUN"
    log "デバッグ: $DEBUG"
    log "================"
}

# ===== メイン処理関数 =====

invoke_schedule_collection() {
    log "=== Phase 1: レース日程取得 ==="
    
    local command="-m src.keibabook.batch_cli schedule --start-date \"$START_DATE\""
    
    if [ -n "$END_DATE" ]; then
        command="$command --end-date \"$END_DATE\""
    fi
    
    command="$command --delay $DELAY"
    
    if [ "$DEBUG" = "true" ]; then
        command="$command --debug"
    fi
    
    invoke_python_command "$command" "レース日程取得"
}

invoke_data_collection() {
    log "=== Phase 2: レースデータ取得 ==="
    
    local command="-m src.keibabook.batch_cli data --start-date \"$START_DATE\""
    
    if [ -n "$END_DATE" ]; then
        command="$command --end-date \"$END_DATE\""
    fi
    
    command="$command --data-types \"$DATA_TYPES\""
    command="$command --delay $DELAY"
    
    if [ "$DEBUG" = "true" ]; then
        command="$command --debug"
    fi
    
    invoke_python_command "$command" "レースデータ取得"
}

invoke_full_processing() {
    log "=== 全処理実行モード ==="
    
    local command="-m src.keibabook.batch_cli full --start-date \"$START_DATE\""
    
    if [ -n "$END_DATE" ]; then
        command="$command --end-date \"$END_DATE\""
    fi
    
    command="$command --data-types \"$DATA_TYPES\""
    command="$command --delay $DELAY"
    command="$command --wait-between-phases $WAIT_BETWEEN_PHASES"
    
    if [ "$DEBUG" = "true" ]; then
        command="$command --debug"
    fi
    
    invoke_python_command "$command" "全処理実行"
}

invoke_post_processing() {
    log "=== 事後処理 ==="
    
    # データファイルの確認
    local data_dirs=("data/keibabook/seiseki" "data/keibabook/race_ids")
    for dir in "${data_dirs[@]}"; do
        if [ -d "$dir" ]; then
            local file_count
            local total_size
            local size_kb
            
            file_count="$(find "$dir" -type f | wc -l)"
            total_size="$(find "$dir" -type f -exec du -b {} + 2>/dev/null | awk '{sum += $1} END {print sum+0}')"
            size_kb="$(echo "scale=2; $total_size / 1024" | bc -l 2>/dev/null || echo "0")"
            
            log "ディレクトリ $dir : $file_count ファイル, ${size_kb}KB"
        else
            log "ディレクトリが見つかりません: $dir" "WARNING"
        fi
    done
    
    # ログファイルサイズの確認
    if [ -d "logs" ]; then
        local log_count
        local log_size
        local log_size_kb
        
        log_count="$(find logs -name "*.log" -type f | wc -l)"
        log_size="$(find logs -name "*.log" -type f -exec du -b {} + 2>/dev/null | awk '{sum += $1} END {print sum+0}')"
        log_size_kb="$(echo "scale=2; $log_size / 1024" | bc -l 2>/dev/null || echo "0")"
        
        log "ログファイル: $log_count ファイル, ${log_size_kb}KB"
    fi
}

send_notification() {
    local success="$1"
    local summary="$2"
    
    # 将来的には Slack/Email 通知を実装
    local status
    if [ "$success" = "true" ]; then
        status="成功"
    else
        status="失敗"
    fi
    
    local message="日次バッチ処理が$status しました\n$summary"
    log "通知: $message"
    
    # 成功時はファイルに結果を保存
    if [ "$success" = "true" ]; then
        local result_file="logs/daily_batch_result_$(date '+%Y%m%d').txt"
        echo -e "$message" > "$result_file"
        log "結果ファイルを保存しました: $result_file"
    fi
}

# ===== コマンドライン引数処理 =====

show_help() {
    cat << EOF
競馬ブック データ取得 - 日次バッチスクリプト v2.0

使用方法:
    $0 [オプション]

オプション:
    -s, --start-date DATE      取得開始日 (YYYY/MM/DD) [デフォルト: 今日]
    -e, --end-date DATE        取得終了日 (YYYY/MM/DD) [デフォルト: 開始日と同じ]
    -t, --data-types TYPES     データタイプ (カンマ区切り) [デフォルト: seiseki,shutsuba]
    -d, --delay SECONDS        リクエスト間隔(秒) [デフォルト: 3]
    -w, --wait-phases SECONDS  Phase間待機時間(秒) [デフォルト: 10]
    --schedule-only            レース日程取得のみ
    --data-only                レースデータ取得のみ
    --debug                    デバッグモード
    --dry-run                  ドライラン（実際には実行しない）
    -h, --help                 このヘルプを表示

実行例:
    # 基本的な実行（今日のデータを全処理）
    $0

    # 特定日の処理
    $0 --start-date "2025/02/04"

    # 期間指定の処理
    $0 --start-date "2025/02/01" --end-date "2025/02/07"

    # 環境変数での設定
    START_DATE="2025/02/04" DEBUG=true $0

EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -s|--start-date)
                START_DATE="$2"
                shift 2
                ;;
            -e|--end-date)
                END_DATE="$2"
                shift 2
                ;;
            -t|--data-types)
                DATA_TYPES="$2"
                shift 2
                ;;
            -d|--delay)
                DELAY="$2"
                shift 2
                ;;
            -w|--wait-phases)
                WAIT_BETWEEN_PHASES="$2"
                shift 2
                ;;
            --schedule-only)
                SCHEDULE_ONLY="true"
                shift
                ;;
            --data-only)
                DATA_ONLY="true"
                shift
                ;;
            --debug)
                DEBUG="true"
                shift
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo "ERROR: 不明なオプション: $1" >&2
                show_help
                exit 1
                ;;
        esac
    done
}

# ===== メイン実行処理 =====

main() {
    local success="false"
    
    log "=== 競馬ブック 日次バッチ処理 v2.0 開始 ==="
    
    # 環境情報表示
    show_environment_info
    
    # Python環境チェック
    if ! test_python_environment; then
        log "Python環境のチェックに失敗しました" "ERROR"
        exit 1
    fi
    
    # .env ファイルの存在確認
    if [ ! -f ".env" ]; then
        log ".envファイルが見つかりません。認証情報を設定してください。" "WARNING"
    fi
    
    # 終了日の設定
    if [ -z "$END_DATE" ]; then
        END_DATE="$START_DATE"
    fi
    
    # 処理モードの判定と実行
    if [ "$SCHEDULE_ONLY" = "true" ]; then
        # 日程取得のみ
        if invoke_schedule_collection; then
            success="true"
        fi
    elif [ "$DATA_ONLY" = "true" ]; then
        # データ取得のみ
        if invoke_data_collection; then
            success="true"
        fi
    else
        # 全処理実行（デフォルト）
        if invoke_full_processing; then
            success="true"
        fi
    fi
    
    # 事後処理
    invoke_post_processing
    
    # 結果サマリー
    local execution_mode
    if [ "$SCHEDULE_ONLY" = "true" ]; then
        execution_mode="日程のみ"
    elif [ "$DATA_ONLY" = "true" ]; then
        execution_mode="データのみ"
    else
        execution_mode="全処理"
    fi
    
    local summary="処理期間: $START_DATE ～ $END_DATE
データタイプ: $DATA_TYPES
実行モード: $execution_mode
ログファイル: $LOG_FILE"
    
    # 通知送信
    send_notification "$success" "$summary"
    
    if [ "$success" = "true" ]; then
        log "=== 日次バッチ処理が正常に完了しました ===" "SUCCESS"
        exit 0
    else
        log "=== 日次バッチ処理でエラーが発生しました ===" "ERROR"
        exit 1
    fi
}

# ===== スクリプト実行 =====

# 引数解析
parse_arguments "$@"

# エラーハンドリング
trap 'log "予期しないエラーが発生しました (行: $LINENO)" "ERROR"; send_notification "false" "予期しないエラー"; exit 1' ERR

# メイン処理実行
main