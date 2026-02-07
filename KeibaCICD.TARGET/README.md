# KeibaCICD.TARGET

> JRA-VANデータ解析・機械学習予測モジュール

TARGETデータ連携、PCI分析、機械学習による勝率予測を行います。

---

## 🎯 主要機能

- **JRA-VAN統合ライブラリ**: 馬名⇔ID変換、調教データ解析
- **PCI分析**: 競馬場・距離別ペース指数基準値算出
- **機械学習**: LightGBM/XGBoostによる勝率予測
- **期待値計算**: オッズ×勝率による投資判断

---

## 🚀 クイックスタート

### 1. セットアップ

```bash
cd KeibaCICD.TARGET
python -m venv venv
source venv/Scripts/activate
pip install -r ml/requirements.txt
```

### 2. 環境変数設定

`.env` ファイルを作成：
```ini
KEIBA_DATA_ROOT_DIR=E:\share\KEIBA-CICD\data2
JV_DATA_ROOT_DIR=C:\TFJV
```

### 3. 馬名インデックス構築（初回のみ）

```bash
python scripts/horse_id_mapper.py --build-index
```

---

## 📊 主要スクリプト

### JRA-VAN統合ライブラリ

```python
from common.jravan import (
    get_horse_id_by_name,      # 馬名 → JRA-VAN ID
    analyze_horse_training,    # 調教データ分析
    get_horse_info,            # 馬基本情報
)

# 使用例
horse_id = get_horse_id_by_name("ドウデュース")
# => "2019103487"

training = analyze_horse_training("ドウデュース", "20260125")
# => {'final': {'time_4f': 52.3, 'speed_class': 'A', ...}}
```

詳細は [JRA-VAN使用ガイド](./docs/jravan/USAGE_GUIDE.md) を参照。

---

### 調教データ集計

```bash
python scripts/training_summary.py 2026-02-08
```

TARGET取り込み用のタブ区切りファイルを出力します。

---

### PCI分析

```bash
python scripts/analyze_pci_csv.py
```

競馬場・距離別のPCI基準値を算出します。

出力: `C:/KEIBA-CICD/data2/target/pci_standards.json`

---

### 機械学習パイプライン

```bash
# データ準備
python ml/scripts/01_data_preparation.py

# 特徴エンジニアリング
python ml/scripts/02_feature_engineering.py

# モデル訓練
python ml/scripts/03_model_training.py

# バックテスト
python ml/scripts/04_backtest.py

# 予測実行
python ml/scripts/05_prediction.py --date 2026-02-08
```

---

## 📁 ディレクトリ構成

```
KeibaCICD.TARGET/
├── common/
│   └── jravan/                 # JRA-VAN統合ライブラリ ⭐
│       ├── __init__.py         # 統一インターフェース
│       ├── id_converter.py     # 馬名⇔ID変換
│       ├── data_access.py      # データ取得API
│       └── parsers/            # CK/UM/DE/SEパーサー
├── scripts/
│   ├── training_summary.py     # 調教データ集計
│   ├── analyze_pci_csv.py      # PCI分析
│   └── horse_id_mapper.py      # 馬IDマッパー
├── ml/
│   ├── scripts/
│   │   ├── 01_data_preparation.py
│   │   ├── 02_feature_engineering.py
│   │   ├── 03_model_training.py
│   │   ├── 04_backtest.py
│   │   └── 05_prediction.py
│   └── requirements.txt
├── data/
│   └── horse_name_index.json   # 馬名インデックス（2MB+）
└── docs/jravan/                # JRA-VANドキュメント
```

---

## 📚 ドキュメント

### はじめに読むドキュメント

- **[MODULE_OVERVIEW.md](../../ai-team/knowledge/MODULE_OVERVIEW.md)** - TARGETモジュール詳細
- **[SETUP_GUIDE.md](../../ai-team/knowledge/SETUP_GUIDE.md)** - 環境構築手順
- **[ARCHITECTURE.md](../../ai-team/knowledge/ARCHITECTURE.md)** - システム全体構成

### JRA-VANライブラリ

- **[README.md](./docs/jravan/README.md)** - JRA-VAN統合ライブラリ概要
- **[USAGE_GUIDE.md](./docs/jravan/USAGE_GUIDE.md)** - 使用ガイド
- **[QUICK_REFERENCE.md](./docs/jravan/QUICK_REFERENCE.md)** - クイックリファレンス
- **[ID_MAPPING.md](./docs/jravan/ID_MAPPING.md)** - ID変換仕様

### 分析・機械学習

- **[PCI分析とレース印.md](./docs/PCI分析とレース印.md)** - PCI分析手法
- **[PCI基準値一覧.md](./docs/PCI基準値一覧.md)** - PCI基準値テーブル
- **[training_summary_使い方.md](./docs/training_summary_使い方.md)** - 調教データ集計
- **[スピード指数開発計画.md](./docs/スピード指数開発計画.md)** - 速度指数開発計画

---

## 🔗 関連モジュール

- **[KeibaCICD.keibabook](../KeibaCICD.keibabook/)** - データ収集モジュール
- **[KeibaCICD.WebViewer](../KeibaCICD.WebViewer/)** - プレゼンテーションモジュール

---

**プロジェクトオーナー**: ふくだ君
**最終更新**: 2026-02-06
