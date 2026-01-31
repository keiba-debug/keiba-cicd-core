# データフォルダ構造の移行ガイド

## 概要

KEIBA-CIDCシステムのデータフォルダ構造を、より効率的で管理しやすい新しい構造に移行します。

## 現在の構造（旧構造）

```
Z:/KEIBA-CICD/data/
├── organized/      # 統合・整理済みデータ
│   └── YYYY/MM/DD/競馬場名/
│       ├── integrated_*.json
│       └── *.md
├── parsed/         # パース済みデータ
│   └── YYYYMMDD/
│       └── *.json
├── temp/           # 一時ファイル（全日付混在）
├── race_ids/       # レースID情報
│   └── YYYYMMDD_info.json
└── horses/         # 馬情報（変更なし）
```

## 新しい構造

```
Z:/KEIBA-CICD/data/
├── races/          # レース関連データ（日付階層で整理）
│   └── YYYY/
│       └── MM/
│           └── DD/
│               ├── race_info.json     # その日のレース情報
│               ├── summary.json       # その日のサマリー
│               ├── parsed/           # パース済みデータ
│               │   └── *.json
│               ├── temp/             # 日付別一時ファイル
│               │   └── *.json
│               └── 競馬場名/         # 競馬場別データ
│                   ├── integrated_*.json
│                   └── *.md
└── horses/         # 馬情報（変更なし）
    └── profiles/
```

## 新構造の利点

### 1. 階層的な整理
- 年/月/日の階層構造により、データの探索が容易
- 大量のファイルが一つのフォルダに集中しない

### 2. 日付別の管理
- 各日付のデータが独立して管理される
- 古いデータの削除やアーカイブが簡単

### 3. 統合された構造
- parsed、temp、race_infoが同じ日付フォルダに集約
- データの関連性が明確

### 4. メタデータの追加
- summary.jsonによる日付別のサマリー情報
- 処理状況の把握が容易

## 移行手順

### 1. 移行スクリプトの実行

#### ドライラン（確認のみ）
```bash
python scripts/migrate_data_structure.py
```

#### 実際の移行
```bash
python scripts/migrate_data_structure.py --execute
```

### 2. 環境変数の設定

新構造を使用する場合は、以下の環境変数を設定：

```bash
# Windows
set USE_NEW_DATA_STRUCTURE=true

# Linux/Mac
export USE_NEW_DATA_STRUCTURE=true
```

### 3. テストの実行

移行後、正しく動作することを確認：

```bash
python scripts/test_new_structure.py
```

## プログラムでの使用方法

### DataPathConfigの使用

```python
from src.config.data_paths import DataPathConfig

# 新構造を使用
config = DataPathConfig(use_new_structure=True)

# 日付別のパスを取得
date_str = "20250927"
race_date_path = config.get_race_date_path(date_str)
# => Z:/KEIBA-CICD/data/races/2025/09/27/

# 競馬場別のパスを取得
venue_path = config.get_venue_path(date_str, "中山")
# => Z:/KEIBA-CICD/data/races/2025/09/27/中山/

# レース情報のパスを取得
race_info_path = config.get_race_info_path(date_str)
# => Z:/KEIBA-CICD/data/races/2025/09/27/race_info.json
```

### 環境変数による切り替え

```python
import os

# 新構造を有効化
os.environ['USE_NEW_DATA_STRUCTURE'] = 'true'

# batch モジュールは自動的に新構造を使用
from src.batch.core.common import get_race_ids_file_path

path = get_race_ids_file_path("20250927")
# => Z:/KEIBA-CICD/data/races/2025/09/27/race_info.json
```

## 互換性の維持

移行期間中は、両方の構造をサポート：

1. **環境変数未設定時**: 旧構造を使用（デフォルト）
2. **USE_NEW_DATA_STRUCTURE=true**: 新構造を使用

## 注意事項

### 移行時の注意

1. **バックアップ**: 移行前に必ずデータのバックアップを作成
2. **段階的移行**: まず一部のデータで試してから全体を移行
3. **実行中の処理**: 移行中は他のデータ処理を停止

### 運用上の注意

1. **ディスク容量**: 移行中は一時的に2倍の容量が必要
2. **パフォーマンス**: 深い階層構造により、若干のI/Oオーバーヘッド
3. **スクリプトの更新**: 古いスクリプトは環境変数の設定が必要

## トラブルシューティング

### よくある問題

#### 1. ファイルが見つからない
```
FileNotFoundError: race_ids/20250927_info.json
```
**解決策**: 環境変数が正しく設定されているか確認

#### 2. パスの不一致
```
AssertionError: Expected organized/..., got races/...
```
**解決策**: USE_NEW_DATA_STRUCTURE環境変数を確認

#### 3. 権限エラー
```
PermissionError: Access denied
```
**解決策**: 管理者権限で実行、またはファイルの使用状況を確認

## 移行スケジュール

1. **Phase 1**: 開発環境での検証（完了）
2. **Phase 2**: テストデータでの移行テスト
3. **Phase 3**: 本番データの段階的移行
4. **Phase 4**: 旧構造の廃止

## お問い合わせ

移行に関する質問や問題がある場合は、開発チームまでご連絡ください。

---
*最終更新: 2025-09-27*