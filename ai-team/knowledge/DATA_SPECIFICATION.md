# KeibaCICD データ仕様書

**バージョン**: 1.0
**最終更新**: 2026-01-30
**対象**: 全AIエージェント、開発者

---

## 🎯 目的

このドキュメントは、KeibaCICDプロジェクトのデータ構造、保存場所、取得方法、エージェント間連携を定義します。

**重要**: このシステムは**開発中**であり、今後バージョンアップ予定です。仕様変更時はこのドキュメントを更新してください。

---

## 📂 データディレクトリ構造

### 環境変数

```powershell
# 必須の環境変数（2つだけ）
$env:DATA_ROOT= "E:\share\KEIBA-CICD\data2"  # 競馬データ全般
$env:JV_DATA_ROOT_DIR = "C:\TFJV"                       # JRA-VAN生データ
```

### ディレクトリ構造

```
E:\share\KEIBA-CICD\data2\
  ├─ races\                    # レースデータ
  │   ├─ 2026\
  │   │   ├─ 01\
  │   │   │   ├─ 31\
  │   │   │   │   └─ temp\    # 一時データ（処理中）
  │   │   │   └─ ...
  │   │   └─ ...
  │   ├─ 2025\
  │   ├─ 2024\
  │   └─ 2023\                # ※2023年までのデータあり
  │
  ├─ analysis\                # 分析データ
  │   ├─ rpci\                # RPCI分析結果
  │   └─ rating\              # レイティング分析結果
  │
  └─ predictions\             # 予測データ（今後追加予定）

C:\TFJV\                      # JRA-VAN生データ
  ├─ CK\                      # 調教データ
  ├─ UM\                      # 馬マスタ
  ├─ DE\                      # 騎手・調教師データ
  └─ SE\                      # レースデータ
```

---

## 📊 データの種類と形式

### 1. レースデータ

**場所**: `${KEIBA_DATA_ROOT_DIR}/races/{year}/{month}/{day}/`

**含まれる情報**:
- 出馬表
- オッズ（単勝、複勝、馬連、馬単、ワイド、3連複、3連単）
- 予想印
- コメント
- レース結果（レース後）

**ファイル形式**: JSON / CSV（WebViewerで処理）

### 2. JRA-VANデータ

**場所**: `${JV_DATA_ROOT_DIR}/`

**データ種類**:
- **CK**: 調教データ（速度、ラップ、本数）
- **UM**: 馬マスタ（血統、性別、年齢）
- **DE**: 騎手・調教師データ
- **SE**: レースデータ（距離、コース、グレード）

**ファイル形式**: JRA-VAN固有形式（バイナリ + テキスト）

**参照**: `keiba-cicd-core/KeibaCICD.TARGET/docs/jravan/`

### 3. 分析データ

**場所**: `${KEIBA_DATA_ROOT_DIR}/analysis/`

**種類**:
- **RPCI分析**: コース別ペース変化指数
- **レイティング分析**: クラス別成績評価

**ファイル形式**: JSON

### 4. 予測データ（今後追加）

**場所**: `${KEIBA_DATA_ROOT_DIR}/predictions/`

**含まれる情報**:
- アルテタ（ML予想）の勝率予測
- シノ（期待値計算）の期待値データ
- シカマル（購入戦略）の推奨リスト

**ファイル形式**: JSON / CSV

---

## 🌐 WebViewer連携

### WebViewer URL

```
http://localhost:3000/
http://localhost:3000/admin  # 管理画面
```

### 主な機能

#### 1. データ登録画面（Admin）

**URL**: `http://localhost:3000/admin`

**機能**:
- **日付指定**: 特定日のレースデータ取得
- **期間指定**: 複数日のバッチ実行
- **スケジュール管理**: 自動実行設定
- **パドック情報**: パドック調教データ取得
- **データ取得**: スクレイピング実行

**実行内容**:
- 競馬ブックからのスクレイピング
- JRA-VANデータの処理
- データ加工・整形

#### 2. レース画面

**URL**: `http://localhost:3000/races/{date}/{race_id}`

**表示内容**:
- 出馬表
- オッズ
- 予想印
- コメント
- レース結果（レース後のみ）

#### 3. 馬情報画面

**URL**: `http://localhost:3000/horses-v2/{umacd}`

**表示内容**:
- 馬の基本情報（血統、性別、年齢）
- 過去の出走レース一覧
- 各レースの成績・上がり・通過順

**umacd取得方法**:
- 出馬表データの `umacd` フィールドから取得
- 例: ピースワンデュック → `0915378` → `/horses-v2/0915378`

**活用方法**:
- 過去レースIDの迅速な特定
- 脚質・上がりタイムの傾向確認
- コース適性の分析

#### 4. 分析画面

**URL**: `http://localhost:3000/analysis/`

**種類**:
- **RPCI分析**: コース別ランキング、速度指数
- **レイティング分析**: クラス別成績、適性評価

**今後の拡張**:
- 仮説と検証を視覚的に確認
- AIエージェントの分析結果表示
- バックテスト結果の可視化

---

## 🔄 エージェント間データフロー

### データの流れ

```
1. キバ（TRACKER）
   ↓ データ収集
   ${KEIBA_DATA_ROOT_DIR}/races/{date}/

2. アルテタ（PREDICTOR）
   ↓ 予測結果
   ${KEIBA_DATA_ROOT_DIR}/predictions/{date}_predictions.json

3. シノ（EVALUATOR）
   ↓ 期待値計算
   ${KEIBA_DATA_ROOT_DIR}/predictions/{date}_expected_values.json

4. シカマル（STRATEGIST）
   ↓ 購入推奨
   ${KEIBA_DATA_ROOT_DIR}/strategies/{date}_recommendations.json

5. サイ（EXECUTOR）
   ↓ 実行記録
   keiba-ai/logs/betting/purchases_{date}.csv

6. ひなた（ANALYST）
   ↓ 分析結果
   keiba-ai/logs/backtest/report_{strategy}_{date}.json

7. ナルト（LEARNER）
   ↓ 改善提案
   keiba-ai/logs/improvements/{date}_improvements.json
```

### データアクセス方式

#### オプション1: ファイル直接読み込み（現在推奨）
- エージェント間でファイルを読み書き
- シンプルで実装しやすい
- バージョン管理しやすい

#### オプション2: WebViewer API（今後検討）
- WebViewerがAPIを提供
- エージェントがHTTP経由でアクセス
- より柔軟だが実装コストが高い

**現時点の方針**: **オプション1（ファイル直接読み込み）**を採用

---

## 📅 データの時系列

### 過去データ

- **利用可能期間**: 2020年〜2023年（現在）
- **制限**: 2022年以前のデータは別途取得が必要
- **取得方法**: WebViewer管理画面から期間指定で実行

### 未来データ

- **週末レース**: 金曜午後にデータ取得
- **保存先**: `${KEIBA_DATA_ROOT_DIR}/races/{year}/{month}/{day}/temp`
- **確定データ**: レース後に結果追加

---

## 🛠️ データ取得方法

### 方法1: WebViewer管理画面（手動）

1. `http://localhost:3000/admin` にアクセス
2. 日付を指定
3. 「データ取得」ボタンをクリック
4. スクレイピング・処理が実行される

### 方法2: キバ（TRACKER）による自動取得（今後実装）

```python
# キバがスケジュール実行
# 金曜 15:00 - 週末レースデータ取得
# 日曜 21:00 - レース結果取得
```

### 方法3: バッチスクリプト（既存）

```powershell
# KeibaCICD.TARGET のスクリプト
cd E:\share\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.TARGET
python scripts/fetch_race_data.py --date 20260201
```

---

## 🔍 データ確認方法

### 人間向け: WebViewer

- **レース確認**: `http://localhost:3000/races/{date}/{race_id}`
- **分析確認**: `http://localhost:3000/analysis/`

### エージェント向け: ファイル読み込み

```python
import json
from pathlib import Path
import os

# 環境変数から取得
data_root = Path(os.environ['KEIBA_DATA_ROOT_DIR'])

# レースデータ読み込み
race_file = data_root / 'races' / '2026' / '01' / '31' / 'race_data.json'
with open(race_file, 'r', encoding='utf-8') as f:
    race_data = json.load(f)
```

---

## 📊 分析機能の活用

### RPCI分析

**目的**: コース別のペース変化を分析

**活用方法**:
- アルテタ（PREDICTOR）: ペース適性を予測に組み込む
- ひなた（ANALYST）: 戦略別のコース適性を分析

### レイティング分析

**目的**: クラス別の成績評価

**活用方法**:
- アルテタ（PREDICTOR）: レーティングを特徴量に使用
- ナルト（LEARNER）: クラス別の戦略最適化

---

## 🚀 今後の拡張予定

### データ拡張

- [ ] 2022年以前の過去データ取得
- [ ] 海外レースデータ
- [ ] 天候・馬場状態の詳細データ

### 機能拡張

- [ ] WebViewer API実装
- [ ] リアルタイムオッズ取得
- [ ] AIエージェント用ダッシュボード
- [ ] 仮説検証ツール

### 分析拡張

- [ ] ペース分析の高度化
- [ ] 血統分析
- [ ] 騎手・調教師の傾向分析
- [ ] コース適性AI

---

## 📝 ドキュメント管理

### 更新ルール

1. **データ構造変更時**: このドキュメントを必ず更新
2. **新機能追加時**: 対応するセクションを追加
3. **バージョン番号**: 大きな変更時は更新
4. **変更履歴**: 重要な変更は記録

### 変更履歴

| 日付 | バージョン | 変更内容 | 担当 |
|------|-----------|---------|------|
| 2026-01-30 | 1.0 | 初版作成 | カカシ |

---

## 🤝 関連ドキュメント

- [チームガイドライン](CLAUDE.md)
- [JRA-VANライブラリ](../../keiba-cicd-core/KeibaCICD.TARGET/docs/jravan/README.md)
- [プロジェクト概要](../project.md)
- [エージェント名簿](../experts/TEAM_ROSTER.md)

---

**「データを制する者が、競馬を制する」**

---

*作成日: 2026-01-30*
*作成者: カカシ（AI相談役）*
*承認: ふくだ君（オーナー）*
