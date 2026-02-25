# 10. 【v2.1.1】modules/constants/の解説

> 出典: Zenn「競馬予想で始める機械学習〜完全版〜」Ch.10

---

## 定数モジュール構成

```
modules/constants/
├── __init__.py              # 外部インポート用の再エクスポート
├── _horse_info_cols.py      # 馬基本情報テーブルの列名定数
├── _horse_results_cols.py   # 馬過去成績テーブルの列名定数
├── _local_paths.py          # ローカルファイルパス定数
├── _master.py               # 開催場所・天気・クラス等のマスタ定数
├── _results_cols.py         # レース結果テーブルの列名定数
└── _url_paths.py            # netkeiba.com URL定数
```

- 全クラスに `@dataclasses.dataclass(frozen=True)` → イミュータブル
- `_`プレフィックス → 外部から直接importしない内部モジュール
- `__init__.py` で再エクスポート → `from modules.constants import Xxx` で使える

---

## 主な定数クラス

### Master（マスタデータ）
| 定数 | 型 | 内容 |
|------|---|------|
| PLACE_DICT | dict(MappingProxyType) | 開催場所名→コード（JRA10場+地方+海外） |
| RACE_TYPE_DICT | dict | 芝/ダ/障 → 芝/ダート/障害 |
| WEATHER_LIST | tuple | 晴, 曇, 小雨, 雨, 小雪, 雪 |
| GROUND_STATE_LIST | tuple | 良, 稍重, 重, 不良 |
| SEX_LIST | tuple | 牡, 牝, セ |
| AROUND_LIST | tuple | 右, 左, 直線, 障害 |
| RACE_CLASS_LIST | tuple | 新馬〜G1, 障害 |

- **地方・海外の場所コードも定義** — 30〜88まで。うちはJRA-VAN 01〜10のみ
- **MappingProxyType** — 辞書のイミュータブル版。書き換え防止

### HorseResultsCols（馬の過去成績列名）
- DATE, PLACE, WEATHER, R, RACE_NAME, N_HORSES, WAKUBAN, UMABAN
- TANSHO_ODDS, POPULARITY, RANK, JOCKEY, KINRYO
- RACE_TYPE_COURSE_LEN, GROUND_STATE, TIME, RANK_DIFF
- CORNER, PACE, **NOBORI（上がり）**, WEIGHT_AND_DIFF, PRIZE

### HorseInfoCols（馬の基本情報列名）
- BIRTHDAY, TRAINER, OWNER, BREEDER, ORIGIN
- PRICE（セリ取引価格）, WINNING_PRIZE, TOTAL_RESULTS
- VICTORY_RACE, RELATIVE_HORSE（近親馬）

---

## KeibaCICDとの比較

| 項目 | この書籍 v2 | KeibaCICD v4 |
|------|-----------|-------------|
| 定数管理 | dataclass(frozen=True) | config.py + constants.py |
| パス管理 | LocalPaths クラス | config.data_root() 関数 |
| 場所コード | Master.PLACE_DICT | constants.py VENUE辞書 |
| 列名管理 | 各テーブル専用の定数クラス | モデルクラス内で定義 |
| イミュータブル保証 | frozen=True + MappingProxyType | なし（慣習的に不変） |

## 参考になるポイント

1. **frozen dataclass パターン** — 定数のイミュータブル保証。Pythonでは慣習的にALL_CAPSだけど、frozen=Trueで実際に書き換え不可にする方が安全
2. **MappingProxyType** — 辞書のイミュータブル版。うちのconstants.pyにも適用できる
3. **列名定数化** — サイト仕様変更時に1箇所直すだけ。うちはJRA-VANのバイナリオフセットなので仕様変更リスクは低いが、設計思想は参考
4. **RACE_CLASS_LIST** — 新馬〜G1のクラス分類。うちのrace_classifier.pyのgrade体系と対応

## メモ

- この章はコード品質・保守性の話。機能的な新しさは少ない
- うちの `constants.py` も frozen dataclass にリファクタリングする価値はあるが、優先度は低い

## 次章で確認したいこと

- Ch.11 preparing（スクレイピング実装の詳細）
- Ch.13-14 preprocessing（前処理の詳細実装）
