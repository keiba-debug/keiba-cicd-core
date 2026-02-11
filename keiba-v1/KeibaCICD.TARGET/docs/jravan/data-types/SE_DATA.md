# SE_DATA: 成績データ仕様書

JRA-VAN SE_DATAの解析・活用のための詳細仕様書

## 📋 概要

**SE_DATA**はレース後の成績情報を格納したファイルです。

- **用途**: レース結果取得、着順、タイム、配当金
- **更新頻度**: 毎日（レース終了後）
- **データ形式**: Shift-JIS テキストファイル（可変長レコード）
- **主要レコード**: SE（レース結果）, HR（着順）

## 📂 ファイル構造

### ディレクトリ構成

```
{JV_DATA_ROOT_DIR}/SE_DATA/
└── {年}/
    └── SR{YYYYMMDD}.DAT  # 日付ごとの成績
```

### ファイル命名規則

| ファイル名 | 説明 | 例 |
|----------|------|-----|
| SR{YYYYMMDD}.DAT | 指定日の成績 | SR20260124.DAT |

## 📊 レコード構造

### SEレコード（レース成績）

**レコード長**: 約800バイト（可変）

| 位置 (0-based) | サイズ | フィールド | 説明 | 例 |
|---------------|-------|----------|------|-----|
| 0-1 | 2 | RecordType | レコード種別 | `SE` |
| 11-26 | 16 | RaceID | レースID | `2026012406010208` |
| 27-28 | 2 | Umaban | 馬番 | `01` |
| 29-30 | 2 | Wakuban | 枠番 | `1` |
| 31-40 | 10 | KettoNum | 血統登録番号（馬ID） | `2019103487` |
| ... | ... | KakuteiJuni | 確定着順 | `1` |
| ... | ... | Time | タイム | `11234` (1:12.34) |
| ... | ... | PassOrder | 通過順位 | `05-03-02-01` |

### HRレコード（配当情報）

**レコード長**: 可変

| 位置 | サイズ | フィールド | 説明 | 例 |
|-----|-------|----------|------|-----|
| 0-1 | 2 | RecordType | レコード種別 | `HR` |
| 11-26 | 16 | RaceID | レースID | `2026012406010208` |
| ... | ... | TanPay | 単勝配当 | `150` (150円) |
| ... | ... | FukuPay | 複勝配当 | `110,120,180` |
| ... | ... | UmaTanPay | 馬単配当 | `1250` |

## 🔧 データアクセス

### レース結果取得（未実装・提案）

```python
from common.jravan.se_parser import get_race_results

# 指定レースの結果を取得
results = get_race_results("2026012406010208")

for result in results:
    print(f"{result['chakujun']:2d}着 {result['umaban']:2d}番 {result['horse_name']}")
    print(f"  タイム: {result['time']} 通過: {result['pass_order']}")
```

### 配当情報取得（未実装・提案）

```python
from common.jravan.se_parser import get_payout_info

# 配当情報取得
payouts = get_payout_info("2026012406010208")

print(f"単勝: {payouts['tan']}円")
print(f"複勝: {', '.join(payouts['fuku'])}円")
print(f"馬連: {payouts['umaren']}円")
```

## 🎯 実用例（今後の実装予定）

### 当日の成績取得

```powershell
# 未実装
python scripts/parse_se_data.py --date 2026-01-24
```

### 過去成績の統計分析

```python
# レースタイプごとのPCI計算など
from common.jravan.se_parser import calculate_race_statistics

stats = calculate_race_statistics(
    start_date="2025-01-01",
    end_date="2025-12-31",
    track="中山",
    distance=1600
)
```

## 📝 注意事項

### 現在の実装状況

**未実装**: SE_DATAの本格的なパーサーは未実装です。

**代替手段**:
- 競馬ブックからスクレイピングでレース結果を取得
- JRA公式サイトからスクレイピング

### 今後の実装予定

1. **SE_DATAパーサー**: `scripts/parse_se_data.py` の作成
2. **成績インデックス**: レースID→結果の高速検索
3. **統計分析**: 過去成績の集計・分析機能
4. **データベース連携**: PostgreSQL等への格納

## 📚 関連リソース

### プロジェクト内

- [DE_DATA仕様](./DE_DATA.md) - 出馬表データ
- [ID変換](../ID_MAPPING.md) - レースID変換

### 参考

- JV-Data SE仕様書
- JV-Data HR仕様書

---

*最終更新: 2026-01-30*
