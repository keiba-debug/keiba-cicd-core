# KeibaCICD.TARGET

TARGET（競馬ソフト）連携用スクリプト・ツール集

## 📁 構成

```
KeibaCICD.TARGET/
├── data/
│   └── pci_standards.json                # コース・距離別PCI基準値マスタ（JSON）
├── docs/
│   ├── 外部指数仕様.md                   # 外部指数取り込み仕様書
│   ├── スピード指数開発計画.md           # スピード指数開発計画
│   ├── PCI分析とレース印.md              # PCI分析・レース印活用
│   ├── PCI基準値一覧.md                  # PCI基準値一覧（テーブル形式）
│   ├── 調教データ作成スクリプト開発.md   # 調教データ仕様書
│   └── training_summary_使い方.md        # 調教データ使い方ガイド
├── scripts/
│   ├── training_summary.py               # 調教データ集計スクリプト
│   └── analyze_pci_csv.py                # PCI基準値算出スクリプト
└── README.md                             # このファイル
```

## 🚀 スクリプト一覧

### training_summary.py

調教データ（坂路・コース）を集計し、TARGET取り込み用のタブ区切りファイルを出力するスクリプト。

**主な機能:**
- 坂路CSV / コースCSVの読み込み
- 調教ラップ分類（SS/S/A/B/C/D）の算出
- 調教タイム分類（坂/コ/両）の算出
- TARGET用タブ区切りファイルの出力
- クリップボードへのコピー（馬名・調教ラップ/タイム/詳細）

**使用例:**
```bash
# 基本的な使い方
python training_summary.py -s 坂路.csv -c コース.csv -d 20251228 -o output.txt

# クリップボードに調教ラップをコピー
python training_summary.py -s 坂路.csv -c コース.csv -d 20251228 -o output.txt --clip-lap
```

詳細は [training_summary_使い方.md](docs/training_summary_使い方.md) を参照。

---

## 📊 外部指数（開発中）

TARGETに外部で作成した指数を取り込み、出馬表分析や馬券シミュレーションで活用する機能。

### 仕様概要

- **ファイル形式**: 馬単位・CSV
- **レースID**: 新仕様（18桁・馬番付き）
- **競馬ブックデータから変換**

### ドキュメント

- [外部指数仕様.md](docs/外部指数仕様.md) - 詳細仕様書
- [スピード指数開発計画.md](docs/スピード指数開発計画.md) - 開発計画・タスク一覧
- [PCI分析とレース印.md](docs/PCI分析とレース印.md) - PCI分析・レース印活用
- [PCI基準値一覧.md](docs/PCI基準値一覧.md) - 全競馬場のPCI基準値テーブル

### 今後の実装予定

- [ ] 成績スクレイピング改善（距離/馬場/ラップ取得）
- [ ] レースID変換ユーティリティ
- [ ] スピード指数計算ロジック
- [ ] 外部指数ファイル生成スクリプト
- [ ] PCI分析・レース分類スクリプト

---

## 📝 データフォルダ

入出力データは以下のフォルダで管理：
- `Z:\KEIBA-CICD\調教データ\` - 調教CSV / 出力ファイル

## 🔗 関連プロジェクト

- `KeibaCICD.keibabook` - 競馬ブックデータ関連
- `KeibaCICD.JraVanSync` - JRA-VAN同期関連
