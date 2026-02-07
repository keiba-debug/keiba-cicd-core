# KeibaCICD セットアップガイド v3.0

> **最終更新**: 2026-02-06
> **対象バージョン**: v3.0
> **対象OS**: Windows 10/11

---

## 📋 目次

1. [前提条件](#前提条件)
2. [共通セットアップ](#共通セットアップ)
3. [モジュール別セットアップ](#モジュール別セットアップ)
4. [初回実行](#初回実行)
5. [トラブルシューティング](#トラブルシューティング)

---

## ✅ 前提条件

### 必須ソフトウェア

| ソフトウェア | バージョン | 用途 |
|-------------|-----------|------|
| **Python** | 3.11+ (keibabook) / 3.8+ (TARGET) | データ収集・分析 |
| **Node.js** | 20.9+ | WebViewer |
| **Git** | 最新版 | ソースコード管理 |
| **JRA-VAN Data Lab.** | 最新版 | JRA-VANデータ取得 |
| **TARGET frontier JV** | 最新版（オプション） | TARGET独自指数利用 |

### 推奨ソフトウェア

- **VSCode** - 推奨エディタ
- **Chrome/Edge** - Seleniumブラウザ自動化
- **Git Bash** - Windows向けBashシェル

### システム要件

- **OS**: Windows 10/11
- **RAM**: 8GB以上（16GB推奨）
- **ストレージ**: 50GB以上の空き容量
- **ネットワーク**: 安定したインターネット接続

---

## 🔧 共通セットアップ

### 1. リポジトリクローン

```bash
# プロジェクトルートディレクトリに移動
cd c:/KEIBA-CICD/

# リポジトリクローン
git clone <repository-url> _keiba
cd _keiba
```

### 2. データディレクトリ作成

```bash
# 共有データディレクトリ作成
mkdir -p C:/KEIBA-CICD/data2

# 必要なサブディレクトリ作成
cd C:/KEIBA-CICD/data2
mkdir -p organized races horses target logs
```

**ディレクトリ構造**:
```
C:/KEIBA-CICD/data2/
├── organized/      # keibabook統合出力
├── races/          # レースJSONデータ
├── horses/         # 馬データ
├── target/         # TARGET分析結果
└── logs/           # 実行ログ
```

### 3. JRA-VANデータディレクトリ確認

JRA-VAN Data Lab.をインストール済みの場合、以下のパスを確認：

```
C:/TFJV/           # JRA-VANローカルデータ
├── CK_DATA/       # 調教データ
├── UM_DATA/       # 馬マスタ
├── DE_DATA/       # 出馬表
└── SE_DATA/       # 成績データ
```

**注意**: パスが異なる場合は後述の環境変数設定で調整してください。

---

## 🐍 モジュール別セットアップ

### モジュール1: KeibaCICD.keibabook（データ収集）

#### 1. ディレクトリ移動

```bash
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core/KeibaCICD.keibabook
```

#### 2. Python仮想環境作成

```bash
# 仮想環境作成
python -m venv venv

# 仮想環境有効化（Git Bash）
source venv/Scripts/activate

# 仮想環境有効化（PowerShell）
.\venv\Scripts\Activate.ps1
```

#### 3. 依存ライブラリインストール

```bash
# 本体ライブラリ
pip install -r src/requirements.txt

# 管理API（オプション）
pip install -r api/requirements.txt
```

#### 4. 環境変数設定

`.env` ファイルを作成：

```bash
# .envファイル作成
cat > .env << 'EOF'
# データディレクトリ
KEIBA_DATA_ROOT_DIR=E:\share\KEIBA-CICD\data2
JV_DATA_ROOT_DIR=E:\TFJV

# 競馬ブック認証（要手動設定）
KEIBABOOK_SESSION=your_session_token_here
KEIBABOOK_TK=your_tk_token_here
KEIBABOOK_XSRF_TOKEN=your_xsrf_token_here
EOF
```

**Cookie取得方法**:
1. Chrome/Edgeで `https://p.keibabook.co.jp/` にログイン
2. 開発者ツール（F12）→ Application → Cookies
3. `SESSION`, `TK`, `XSRF-TOKEN` の値をコピー
4. `.env` ファイルに貼り付け

#### 5. 動作確認

```bash
# 高速バッチCLI動作確認
python src/fast_batch_cli.py --help

# 期待される出力:
# Usage: fast_batch_cli.py [OPTIONS]
# ...
```

---

### モジュール2: KeibaCICD.TARGET（データ分析）

#### 1. ディレクトリ移動

```bash
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core/KeibaCICD.TARGET
```

#### 2. Python仮想環境作成

```bash
# 仮想環境作成
python -m venv venv

# 仮想環境有効化（Git Bash）
source venv/Scripts/activate

# 仮想環境有効化（PowerShell）
.\venv\Scripts\Activate.ps1
```

#### 3. 依存ライブラリインストール

```bash
# ML関連ライブラリ
pip install -r ml/requirements.txt

# 共通ライブラリをPYTHONPATHに追加（またはシンボリックリンク）
export PYTHONPATH="${PYTHONPATH}:c:/KEIBA-CICD/_keiba/keiba-cicd-core/KeibaCICD.TARGET"
```

#### 4. 環境変数設定

keibabook の `.env` を共有、または新規作成：

```bash
# .envファイル作成
cat > .env << 'EOF'
KEIBA_DATA_ROOT_DIR=E:\share\KEIBA-CICD\data2
JV_DATA_ROOT_DIR=E:\TFJV
EOF
```

#### 5. 馬名インデックス構築

```bash
# 馬名⇔JRA-VAN ID変換インデックス構築
python scripts/horse_id_mapper.py --build-index

# 期待される出力:
# Building horse name index...
# Indexed 50000+ horses
# Index saved to: E:\share\KEIBA-CICD\data2\target\horse_name_index.json
```

#### 6. 調教師インデックス構築

```bash
# 調教師ID変換インデックス構築
python scripts/build_trainer_index.py

# 期待される出力:
# Building trainer index...
# Indexed 500+ trainers
```

#### 7. 動作確認

```bash
# common.jravanライブラリ動作確認
python -c "from common.jravan import get_horse_id_by_name; print(get_horse_id_by_name('ドウデュース'))"

# 期待される出力:
# 2019103487
```

---

### モジュール3: KeibaCICD.WebViewer（プレゼンテーション）

#### 1. ディレクトリ移動

```bash
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core/KeibaCICD.WebViewer
```

#### 2. 依存ライブラリインストール

```bash
# Node.jsパッケージインストール
npm install
```

#### 3. 環境変数設定

`.env.local` ファイルを作成：

```bash
# .env.localファイル作成
cat > .env.local << 'EOF'
# データルート（絶対パスまたはZドライブマッピング）
DATA_ROOT=C:/KEIBA-CICD/data2
# または
# DATA_ROOT=Z:/KEIBA-CICD/data2

# JRA-VANデータルート
JV_DATA_ROOT_DIR=C:/TFJV
EOF
```

#### 4. 開発サーバー起動

```bash
# 開発サーバー起動
npm run dev

# 期待される出力:
# ▲ Next.js 16.1.3
# - Local:   http://localhost:3000
```

#### 5. ブラウザで確認

ブラウザで `http://localhost:3000` を開き、トップページが表示されることを確認。

---

## 🚀 初回実行

### ステップ1: データ収集（keibabook）

```bash
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core/KeibaCICD.keibabook
source venv/Scripts/activate

# 直近の土曜日データ取得（例: 2026-02-08）
python src/fast_batch_cli.py --date 2026-02-08

# 統合JSON生成
python src/integrator_cli.py --date 2026-02-08

# Markdown新聞生成
python src/markdown_cli.py --date 2026-02-08
```

**確認**:
```bash
ls C:/KEIBA-CICD/data2/organized/2026/02/08/
# 期待される出力:
# 東京/ 京都/ 小倉/
```

### ステップ2: データ分析（TARGET）

```bash
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core/KeibaCICD.TARGET
source venv/Scripts/activate

# 調教データ集計
python scripts/training_summary.py 2026-02-08

# ML予測実行（事前にモデル訓練が必要）
# python ml/scripts/05_prediction.py --date 2026-02-08
```

### ステップ3: Web表示（WebViewer）

```bash
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core/KeibaCICD.WebViewer
npm run dev
```

ブラウザで `http://localhost:3000` → 日付選択 → 2026-02-08 → レース一覧が表示されることを確認。

---

## 🔍 トラブルシューティング

### 問題1: `ModuleNotFoundError: No module named 'common.jravan'`

**原因**: PYTHONPATHが設定されていない

**解決策**:
```bash
# 環境変数追加（Git Bash）
export PYTHONPATH="${PYTHONPATH}:c:/KEIBA-CICD/_keiba/keiba-cicd-core/KeibaCICD.TARGET"

# または、永続化（~/.bashrc に追記）
echo 'export PYTHONPATH="${PYTHONPATH}:c:/KEIBA-CICD/_keiba/keiba-cicd-core/KeibaCICD.TARGET"' >> ~/.bashrc
```

---

### 問題2: `FileNotFoundError: [Errno 2] No such file or directory: 'C:\\KEIBA-CICD\\data2'`

**原因**: データディレクトリが存在しない、または環境変数が間違っている

**解決策**:
```bash
# ディレクトリ作成
mkdir -p C:/KEIBA-CICD/data2

# 環境変数確認
cat .env
# KEIBA_DATA_ROOT_DIR=C:\KEIBA-CICD\data2 が正しく設定されているか確認
```

---

### 問題3: WebViewerで「データが見つかりません」と表示される

**原因**: keibabook でデータ収集が完了していない、またはDATA_ROOTが間違っている

**解決策**:
```bash
# データ存在確認
ls C:/KEIBA-CICD/data2/organized/2026/02/08/

# .env.local確認
cat .env.local
# DATA_ROOT=C:/KEIBA-CICD/data2 が正しいか確認

# Next.jsサーバー再起動
npm run dev
```

---

### 問題4: 競馬ブックスクレイピングで「401 Unauthorized」エラー

**原因**: Cookie が期限切れ、または間違っている

**解決策**:
1. ブラウザで競馬ブックに再ログイン
2. 開発者ツールで最新のCookie値を取得
3. `.env` ファイルを更新
4. スクリプト再実行

---

### 問題5: JRA-VANデータが読み込めない

**原因**: JV_DATA_ROOT_DIR が間違っている、またはJRA-VAN Data Lab.が未インストール

**解決策**:
```bash
# JRA-VAN Data Lab.インストール確認
ls C:/TFJV/CK_DATA/

# パスが異なる場合は.envを修正
# 例: JV_DATA_ROOT_DIR=Y:/ など
```

---

### 問題6: `npm install` で `EACCES` エラー

**原因**: 管理者権限が必要、またはnpmキャッシュ破損

**解決策**:
```bash
# npmキャッシュクリア
npm cache clean --force

# 管理者権限でPowerShell起動し、再実行
npm install
```

---

## 📚 次のステップ

セットアップ完了後、以下のドキュメントを参照してください：

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - システム全体構成の理解
- **[MODULE_OVERVIEW.md](./MODULE_OVERVIEW.md)** - 各モジュール詳細（次ステップで作成予定）
- **[開発ガイドライン](../../keiba-cicd-core/docs/development/development-guidelines.md)** - コーディング規約
- **[JRA-VAN使用ガイド](../../keiba-cicd-core/KeibaCICD.TARGET/docs/jravan/USAGE_GUIDE.md)** - JRA-VANライブラリ利用方法

---

## 🆘 サポート

問題が解決しない場合：

1. **GitHub Issues**: `https://github.com/your-org/keiba-cicd/issues`
2. **ドキュメント確認**: `ai-team/knowledge/` 配下の関連ドキュメント
3. **AIエージェント**: カカシ（AI相談役）に質問

---

## 📝 チェックリスト

初回セットアップ完了の確認：

- [ ] Python 3.11+ / 3.8+ インストール済み
- [ ] Node.js 20.9+ インストール済み
- [ ] データディレクトリ作成済み（`C:/KEIBA-CICD/data2`）
- [ ] keibabook仮想環境作成・ライブラリインストール完了
- [ ] keibabook `.env` 設定完了（Cookie含む）
- [ ] TARGET仮想環境作成・ライブラリインストール完了
- [ ] TARGET 馬名インデックス構築完了
- [ ] WebViewer `npm install` 完了
- [ ] WebViewer `.env.local` 設定完了
- [ ] keibabook 初回データ取得成功
- [ ] WebViewer 開発サーバー起動・レース表示確認

すべてチェックが完了したら、運用フェーズに進めます！

---

**作成者**: カカシ（AI相談役）
**承認**: ふくだ君
**次回レビュー予定**: 2026-03-01
