#!/bin/bash

# 競馬ブックスクレイピングシステム セットアップスクリプト
# 使用方法: ./scripts/setup.sh

set -e  # エラー時に終了

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ログ関数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# プロジェクトルートに移動
cd "$PROJECT_ROOT" || exit 1

log_info "競馬ブックスクレイピングシステムのセットアップを開始します"
log_info "プロジェクトディレクトリ: $PROJECT_ROOT"

# 1. システム要件の確認
log_info "=== システム要件の確認 ==="

# Python3の確認
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    log_success "Python3が見つかりました: $PYTHON_VERSION"
else
    log_error "Python3が見つかりません。インストールしてください。"
    exit 1
fi

# pipの確認
if command -v pip3 &> /dev/null || command -v pip &> /dev/null; then
    log_success "pipが利用可能です"
else
    log_warning "pipが見つかりません。後で手動インストールが必要かもしれません"
fi

# Gitの確認
if command -v git &> /dev/null; then
    log_success "Gitが利用可能です"
else
    log_warning "Gitが見つかりません"
fi

# 2. ディレクトリ構造の作成
log_info "=== ディレクトリ構造の作成 ==="

DIRECTORIES=(
    "data/keibabook/seiseki"
    "data/keibabook/shutsuba"
    "data/debug"
    "logs"
    "scripts"
)

for dir in "${DIRECTORIES[@]}"; do
    if mkdir -p "$dir"; then
        log_success "ディレクトリを作成しました: $dir"
    else
        log_error "ディレクトリの作成に失敗しました: $dir"
        exit 1
    fi
done

# 3. 仮想環境のセットアップ
log_info "=== 仮想環境のセットアップ ==="

if [ ! -d "venv" ]; then
    log_info "仮想環境を作成中..."
    if python3 -m venv venv; then
        log_success "仮想環境を作成しました"
    else
        log_warning "仮想環境の作成に失敗しました。システム全体にインストールを試行します"
    fi
else
    log_info "仮想環境は既に存在します"
fi

# 4. 依存関係のインストール
log_info "=== 依存関係のインストール ==="

# 仮想環境が利用可能な場合は有効化
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    log_info "仮想環境を有効化しています..."
    source venv/bin/activate
    PYTHON_CMD="python"
    PIP_CMD="pip"
else
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
fi

# requirements.txtが存在する場合はインストール
if [ -f "requirements.txt" ]; then
    log_info "requirements.txtから依存関係をインストール中..."
    if $PIP_CMD install -r requirements.txt; then
        log_success "依存関係のインストールが完了しました"
    else
        log_warning "pipでのインストールに失敗しました。システムパッケージを試行します"
        
        # Ubuntuの場合はapt-getでインストールを試行
        if command -v apt-get &> /dev/null; then
            log_info "システムパッケージでのインストールを試行します..."
            sudo apt-get update
            sudo apt-get install -y python3-bs4 python3-lxml python3-selenium || true
        fi
    fi
else
    log_warning "requirements.txtが見つかりません"
fi

# 5. ChromeDriverのインストール確認
log_info "=== ChromeDriverの確認 ==="

if command -v chromedriver &> /dev/null; then
    CHROMEDRIVER_VERSION=$(chromedriver --version)
    log_success "ChromeDriverが見つかりました: $CHROMEDRIVER_VERSION"
else
    log_warning "ChromeDriverが見つかりません"
    
    # OSを判定してインストール方法を提案
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        log_info "Ubuntuの場合: sudo apt-get install chromium-chromedriver"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        log_info "macOSの場合: brew install chromedriver"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        log_info "Windowsの場合: choco install chromedriver または手動ダウンロード"
    fi
    
    # Ubuntu/Debianの場合は自動インストールを試行
    if command -v apt-get &> /dev/null; then
        read -p "ChromeDriverを自動インストールしますか？ [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "ChromeDriverをインストール中..."
            sudo apt-get install -y chromium-chromedriver
            if command -v chromedriver &> /dev/null; then
                log_success "ChromeDriverのインストールが完了しました"
            else
                log_error "ChromeDriverのインストールに失敗しました"
            fi
        fi
    fi
fi

# 6. 環境変数ファイルの作成
log_info "=== 環境変数ファイルの設定 ==="

if [ ! -f ".env" ]; then
    log_info ".envファイルのテンプレートを作成中..."
    
    cat > .env << 'EOF'
# 競馬ブック認証情報
# ブラウザの開発者ツールから取得したCookieを設定してください
KEIBABOOK_SESSION="your_session_cookie_here"
KEIBABOOK_TK="your_tk_cookie_here"
KEIBABOOK_XSRF_TOKEN="your_xsrf_token_here"

# アプリケーション設定
DEBUG="false"
HEADLESS="true"
LOG_LEVEL="INFO"

# スクレイピング設定
DEFAULT_TIMEOUT="10"
DEFAULT_SLEEP_TIME="2.0"
MAX_RETRY_COUNT="3"
EOF
    
    log_success ".envファイルのテンプレートを作成しました"
    log_warning "実際のCookieを設定するために .env ファイルを編集してください"
else
    log_info ".envファイルは既に存在します"
fi

# 7. スクリプトファイルに実行権限を付与
log_info "=== スクリプトファイルの権限設定 ==="

SCRIPT_FILES=(
    "scripts/setup.sh"
    "scripts/daily_scraping.sh"
)

for script in "${SCRIPT_FILES[@]}"; do
    if [ -f "$script" ]; then
        chmod +x "$script"
        log_success "実行権限を付与しました: $script"
    fi
done

# 8. テストの実行
log_info "=== 初期テストの実行 ==="

read -p "基本的なテストを実行しますか？ [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "テストを実行中..."
    
    # Pythonモジュールのインポートテスト
    if $PYTHON_CMD -c "
import sys
sys.path.insert(0, 'src')
try:
    from utils.config import Config
    from utils.logger import setup_logger
    print('✅ 基本モジュールのインポートに成功')
except ImportError as e:
    print(f'❌ モジュールのインポートに失敗: {e}')
    sys.exit(1)
"; then
        log_success "基本モジュールのテストが成功しました"
    else
        log_error "基本モジュールのテストに失敗しました"
    fi
else
    log_info "テストをスキップしました"
fi

# 9. セットアップ完了
log_info "=== セットアップ完了 ==="

log_success "競馬ブックスクレイピングシステムのセットアップが完了しました！"
echo
log_info "次のステップ:"
log_info "1. .env ファイルに実際のCookieを設定してください"
log_info "2. テストを実行してください: python main.py --test"
log_info "3. 実際のデータ取得を試してください: python main.py --race-id [RACE_ID] --mode scrape_and_parse"
echo
log_info "詳細な使用方法は README.md を参照してください"

# 仮想環境の無効化（有効化していた場合）
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi