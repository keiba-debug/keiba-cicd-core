# 13. 【v2.1.1】modules/preprocessing/の解説(前半)

> 出典: Zenn「競馬予想で始める機械学習〜完全版〜」Ch.13

---

## モジュール構成

```
modules/preprocessing/
├── _abstract_data_processor.py     # 抽象クラス
├── _results_processor.py           # レース結果テーブル前処理
├── _race_info_processor.py         # レース情報テーブル前処理
├── _horse_results_processor.py     # 馬の過去成績テーブル前処理
├── _horse_info_processor.py        # 馬の基本情報テーブル前処理
├── _peds_processor.py              # 血統テーブル前処理
├── _return_processor.py            # 払い戻しテーブル前処理
├── _shutuba_table_processor.py     # 出馬表前処理
├── _data_merger.py                 # テーブル結合（次章）
├── _shutuba_data_merger.py         # 出馬表用結合（次章）
└── _feature_engineering.py         # 特徴量作成（次章）
```

---

## 設計パターン: AbstractDataProcessor

```python
class AbstractDataProcessor(metaclass=ABCMeta):
    def __init__(self, filepath):
        self.__raw_data = pd.read_pickle(filepath)
        self.__preprocessed_data = self._preprocess()

    @abstractmethod
    def _preprocess(self):  # サブクラスで必ず実装
        pass

    @property
    def raw_data(self):
        return self.__raw_data.copy()  # コピーを返す（元データ保護）

    @property
    def preprocessed_data(self):
        return self.__preprocessed_data.copy()
```

- **抽象クラス + Template Method パターン**
- 全Processorが`_preprocess()`を実装する統一ルール
- `raw_data`/`preprocessed_data`は**コピーを返す**（元データ不変）

---

## 各Processorの前処理内容

### ResultsProcessor（レース結果）
| 処理 | 内容 |
|------|------|
| 着順 | 数字以外除外 → int → rank(3着以内=1) |
| 性齢 | 性 + 年齢に分割 |
| 馬体重 | 体重 + 体重変化に分割 |
| 型変換 | 単勝→float, 斤量→float, 枠番→int, 馬番→int |
| n_horses | index(race_id)のvalue_countsで出走数 |

**出力列**: 枠番, 馬番, 斤量, 単勝, horse_id, jockey_id, trainer_id, owner_id, 性, 年齢, 体重, 体重変化, n_horses, rank

### RaceInfoProcessor（レース情報）
- course_len: `// 100` で10の位切り捨て
- date: datetime変換
- 開催: race_idの5-6桁目

### HorseResultsProcessor（馬の過去成績）★最も重要
| 処理 | 内容 |
|------|------|
| 通過順位 | first_corner, final_corner 抽出 |
| 位置変動 | final_to_rank, first_to_rank, first_to_final |
| 開催場所 | 文字列→PLACE_DICT→コード（地方・海外含む） |
| race_type | 芝/ダ/障 → 芝/ダート/障害 |
| course_len | 距離文字列から数字抽出 → // 100 |
| **time_seconds** | タイム文字列→秒数変換（複数フォーマット対応） |

### HorseInfoProcessor（馬の基本情報）
- **birthday** → datetime変換（日齢計算用）
- **owner_id, breeder_id** を保持

### PedsProcessor（血統）
- 全62列をLabelEncoder → category型（v1と同じ）

### ShutubaTableProcessor（出馬表）
- **ResultsProcessorを継承**
- `_preprocess_rank()`を**空メソッドでオーバーライド**（着順列がないため）
- course_len, 開催, date を追加処理
- owner_idは含まない（出馬表には馬主IDがない）

---

## 継承の設計: Results → ShutubaTable

```
ResultsProcessor
  ├── _preprocess()        ← メイン処理
  ├── _preprocess_rank()   ← 着順処理（分離）
  └── _select_columns()    ← 列選択

ShutubaTableProcessor(ResultsProcessor)
  ├── _preprocess()        ← super()._preprocess() + 追加処理
  ├── _preprocess_rank()   ← オーバーライド（何もしない）
  └── _select_columns()    ← オーバーライド（出馬表用の列）
```

- 着順処理を別メソッドに切り出すことで、出馬表で空実装できる
- 「共通部分は継承、差分はオーバーライド」の教科書的パターン

---

## KeibaCICDとの比較

| 項目 | この書籍 v2 | KeibaCICD v4 |
|------|-----------|-------------|
| 前処理設計 | Processorクラス群（抽象クラス継承） | builders/*.py（ビルダーパターン） |
| 元データ保護 | `.copy()`で返す | JSONファイルとして保持 |
| time_seconds | 文字列→秒変換（複数フォーマット対応） | SE_DATAから直接秒数取得 |
| 訓練/予測の列統一 | 継承+オーバーライド | adapter.pyで変換 |
| 通過順位処理 | 文字列パース（regex） | SE_DATAバイナリ直読 |

## 参考になるポイント

1. **AbstractDataProcessor パターン** — 抽象クラスで処理を統一。うちのbuilders群にも適用可能だが、現状で十分動いているので優先度低
2. **ShutubaTableの継承設計** — 着順処理の分離→オーバーライドは綺麗。うちは訓練と予測で同じcompute_features_for_race()を使うので不要
3. **time_seconds の複数フォーマット対応** — `'%M:%S.%f'`以外に`'%M.%S.%f'`等も許容。防御的で良い
4. **raw_dataをコピーで返す** — 元データを誤って変更しない安全設計

## 次章で確認したいこと

- Ch.14 DataMerger（テーブル結合・過去成績集計）
- Ch.14 FeatureEngineering（特徴量作成の詳細）
