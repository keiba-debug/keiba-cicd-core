# 競馬ブックスクレイピングシステム - 設定ガイド

## 📁 データ保存ディレクトリの設定

### 概要

競馬ブックスクレイピングシステムでは、データ保存ディレクトリを環境変数で柔軟に設定できます。これにより、外部ストレージや任意の場所にデータを保存することが可能です。

### 🔧 設定可能な環境変数

| 環境変数名 | 説明 | デフォルト値 |
|-----------|------|-------------|
| `KEIBA_DATA_ROOT_DIR` | データルートディレクトリ | `{プロジェクトルート}/data` |
| `KEIBA_DATA_DIR` | メインデータディレクトリ | `{DATA_ROOT_DIR}` |
| `KEIBA_KEIBABOOK_DIR` | 競馬ブックデータディレクトリ | `{DATA_DIR}/keibabook` |
| `KEIBA_SEISEKI_DIR` | 成績データディレクトリ | `{KEIBABOOK_DIR}/seiseki` |
| `KEIBA_SHUTSUBA_DIR` | 出馬表データディレクトリ | `{KEIBABOOK_DIR}/shutsuba` |
| `KEIBA_DEBUG_DIR` | デバッグデータディレクトリ | `{DATA_DIR}/debug` |
| `KEIBA_LOG_DIR` | ログディレクトリ | `{プロジェクトルート}/logs` |
| `LOG_LEVEL` | ログレベル | `INFO` |

### 🛠 設定方法

#### 1. 環境変数テンプレートの生成

```bash
# テンプレートファイルを生成
python tools/config_manager.py --generate-template

# カスタムファイル名で生成
python tools/config_manager.py --generate-template .env.custom
```

#### 2. 環境変数ファイルの作成

```bash
# テンプレートをコピー
cp .env.template .env

# 設定を編集
nano .env  # または任意のエディタ
```

#### 3. 環境変数の設定例

```bash
# .env ファイルの例

# 外部ストレージにデータを保存
KEIBA_DATA_ROOT_DIR=/mnt/external_storage/keiba_data

# プロジェクト内の別フォルダに保存
KEIBA_DATA_DIR=./custom_data

# 成績データのみ別の場所に保存
KEIBA_SEISEKI_DIR=/path/to/seiseki_storage

# ログレベルをDEBUGに変更
LOG_LEVEL=DEBUG

# デバッグモードを有効化
DEBUG=true
```

### 📋 設定管理ツールの使用方法

#### 現在の設定を確認

```bash
python tools/config_manager.py --show
```

出力例：
```
=== 現在の設定 ===
data_root_dir: /c/source/git-h.fukuda1207/_keiba/keiba-cicd-core/data
data_dir: /c/source/git-h.fukuda1207/_keiba/keiba-cicd-core/data
keibabook_dir: /c/source/git-h.fukuda1207/_keiba/keiba-cicd-core/data/keibabook
seiseki_dir: /c/source/git-h.fukuda1207/_keiba/keiba-cicd-core/data/keibabook/seiseki
shutsuba_dir: /c/source/git-h.fukuda1207/_keiba/keiba-cicd-core/data/keibabook/shutsuba
debug_dir: /c/source/git-h.fukuda1207/_keiba/keiba-cicd-core/data/debug
log_dir: /c/source/git-h.fukuda1207/_keiba/keiba-cicd-core/logs

=== ディレクトリ存在確認 ===
data_dir: ✅ /c/source/git-h.fukuda1207/_keiba/keiba-cicd-core/data
keibabook_dir: ✅ /c/source/git-h.fukuda1207/_keiba/keiba-cicd-core/data/keibabook
seiseki_dir: ✅ /c/source/git-h.fukuda1207/_keiba/keiba-cicd-core/data/keibabook/seiseki
```

#### 設定可能な環境変数を確認

```bash
python tools/config_manager.py --env-vars
```

#### 必要なディレクトリを作成

```bash
python tools/config_manager.py --create-dirs
```

#### カスタムパスでのテスト

```bash
python tools/config_manager.py --test-custom "/path/to/custom/data"
```

### 🎯 実用的な設定例

#### 例1: 外部ストレージに全データを保存

```bash
# .env
KEIBA_DATA_ROOT_DIR=/mnt/external_storage/keiba_data
```

この設定により、以下のディレクトリ構造になります：
```
/mnt/external_storage/keiba_data/
├── keibabook/
│   ├── seiseki/
│   └── shutsuba/
└── debug/
```

#### 例2: データタイプ別に異なる場所に保存

```bash
# .env
KEIBA_SEISEKI_DIR=/fast_ssd/keiba/seiseki
KEIBA_DEBUG_DIR=/tmp/keiba_debug
KEIBA_LOG_DIR=/var/log/keiba
```

#### 例3: プロジェクト内の別フォルダに保存

```bash
# .env
KEIBA_DATA_DIR=./my_keiba_data
```

### 🔄 動的設定変更（将来実装予定）

将来的には、Web画面やGUIツールから設定を変更できるようになります：

```python
# 将来の実装例
from src.keibabook.utils.config import Config

# 設定変更API（将来実装）
Config.set_data_dir("/new/path/to/data")
Config.save_config()
```

### ⚠️ 注意事項

1. **パス形式**: Windows環境では `\` の代わりに `/` または `\\` を使用してください
2. **権限**: 指定したディレクトリに書き込み権限があることを確認してください
3. **絶対パス推奨**: 本番環境では絶対パスの使用を推奨します
4. **バックアップ**: 重要なデータは定期的にバックアップしてください

### 🧪 設定のテスト

設定変更後は必ずテストを実行してください：

```bash
# 設定確認
python tools/config_manager.py --show

# ディレクトリ作成テスト
python tools/config_manager.py --create-dirs

# 実際のスクレイピングテスト
python main.py --race-id 202502041211 --mode scrape_and_parse
```

### 🔧 トラブルシューティング

#### 問題: ディレクトリが作成されない

**解決策**:
1. パスの権限を確認
2. 親ディレクトリが存在することを確認
3. パス形式が正しいことを確認

```bash
# 権限確認
ls -la /path/to/parent/directory

# 手動でディレクトリ作成
mkdir -p /path/to/your/data
```

#### 問題: 環境変数が反映されない

**解決策**:
1. `.env` ファイルの場所を確認
2. 環境変数名のスペルを確認
3. アプリケーションを再起動

```bash
# 環境変数確認
echo $KEIBA_DATA_DIR

# 設定確認
python tools/config_manager.py --show
```

### 📚 関連ドキュメント

- [セットアップガイド](setup_guide.md)
- [データ仕様書](data_specification.md)
- [トラブルシューティング](troubleshooting.md) 