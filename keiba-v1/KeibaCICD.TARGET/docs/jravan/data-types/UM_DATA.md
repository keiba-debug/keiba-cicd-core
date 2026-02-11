# UM_DATA: 馬マスタデータ仕様書

JRA-VAN UM_DATAの解析・活用のための詳細仕様書

## 📋 概要

**UM_DATA**は馬の基本情報（マスタデータ）を格納したファイルです。

- **用途**: 馬の基本情報取得、馬名→ID変換、血統情報
- **更新頻度**: 半期ごと（年2回: 1月・7月）
- **データ形式**: Shift-JIS バイナリファイル（固定長レコード）
- **レコード長**: 1609バイト

## 📂 ファイル構造

### ディレクトリ構成

```
{JV_DATA_ROOT_DIR}/UM_DATA/
└── {年}/
    ├── UM{年}1.DAT  # 前期（1月～6月）
    └── UM{年}2.DAT  # 後期（7月～12月）
```

### ファイル命名規則

| ファイル名 | 期間 | 例 |
|----------|------|-----|
| UM20261.DAT | 2026年前期 | 2026/1/1～6/30 |
| UM20262.DAT | 2026年後期 | 2026/7/1～12/31 |

**注意**: 引退馬や10歳以上の馬を含めるため、過去10年分のファイル（約20ファイル）を使用します。

## 📊 レコード構造

### UMレコード - 1609バイト

| 位置 (0-based) | サイズ | フィールド | 説明 | 例 |
|---------------|-------|----------|------|-----|
| 0-1 | 2 | RecordType | レコード種別（固定） | `UM` |
| 11-20 | 10 | KettoNum | 血統登録番号（馬ID） | `2020104764` |
| 21 | 1 | DelKubun | 抹消区分 (0=現役, 1=抹消) | `0` |
| 22-29 | 8 | RegDate | 登録年月日 (YYYYMMDD) | `20200401` |
| 30-37 | 8 | DelDate | 抹消年月日 (YYYYMMDD) | `00000000` |
| 38-45 | 8 | BirthDate | 生年月日 (YYYYMMDD) | `20200215` |
| 46-81 | 36 | Bamei | 馬名 | `ドウデュース` |
| 82-117 | 36 | BameiKana | 馬名カナ | `ドウデュース` |
| 118-177 | 60 | BameiEng | 馬名英字 | `Do Deuce` |
| 200 | 1 | SexCD | 性別コード (1=牡, 2=牝, 3=セン) | `1` |
| 848 | 1 | TozaiCD | 東西所属 (1=美浦, 2=栗東) | `2` |
| 849-853 | 5 | ChokyoshiCode | 調教師コード | `01234` |
| 854-861 | 8 | ChokyoshiRyakusho | 調教師名略称 | `友道康夫` |
| 920-959 | 40 | BreederName | 生産者名 | `ノーザンファーム` |
| 970-1013 | 44 | OwnerName | 馬主名 | `（株）Ｇ1レーシング` |

**その他のフィールド**:
- 父馬・母馬・母父馬の血統情報（200バイト付近）
- 産地情報
- 毛色コード

## 🔧 データアクセス

### 馬IDで検索

```python
from common.jravan.um_parser import find_horse_by_id

# 馬IDで検索
horse = find_horse_by_id("2020104764")

if horse:
    print(f"馬名: {horse.name}")
    print(f"生年月日: {horse.birth_date}")
    print(f"性別: {horse.sex_name}")
    print(f"所属: {horse.tozai_name}")
    print(f"調教師: {horse.trainer_name}")
```

### 馬名で検索

```python
from common.jravan.um_parser import search_horses_by_name

# 馬名で部分一致検索
horses = search_horses_by_name("ドウデュース", limit=10)

for horse in horses:
    print(f"{horse.ketto_num}: {horse.name} ({horse.sex_name}{horse.get_age()}歳)")
```

### 馬名→IDの高速変換

```python
from common.jravan import get_horse_id_by_name

# 馬名から10桁IDを取得（インデックス使用）
horse_id = get_horse_id_by_name("ドウデュース")
# => "2019103487"
```

## 🔍 馬名インデックス

### インデックス構築（初回のみ）

馬名→IDの高速変換のため、インデックスを構築します:

```powershell
cd KeibaCICD.TARGET
python scripts/horse_id_mapper.py --build-index
```

インデックスファイル: `KeibaCICD.TARGET/data/horse_name_index.json`

### インデックスの仕組み

1. **ファイル**: 過去10年分のUM_DATAファイル（約20ファイル）を読み込み
2. **構築**: 馬名→10桁IDの辞書を作成
3. **保存**: JSON形式で保存（約50MB）
4. **使用**: 初回アクセス時に自動ロード

### インデックス更新

半期ごと（1月・7月）にUM_DATAが更新されたら再構築:

```powershell
python scripts/horse_id_mapper.py --build-index
```

## 📈 年齢計算

競馬の年齢は1月1日で加算されます:

```python
from datetime import datetime

horse = find_horse_by_id("2020104764")

# 現在の年齢
age = horse.get_age()

# 特定日時点の年齢
ref_date = datetime(2026, 5, 1)
age_at_date = horse.get_age(ref_date)
```

## 🎯 実用例

### 出走馬の基本情報取得

```python
from common.jravan import get_horse_info

# レース出走馬のリスト（競馬ブックから取得）
horse_names = ["ドウデュース", "イクイノックス", "ジャスティンパレス"]

for name in horse_names:
    info = get_horse_info(name)
    if info:
        print(f"{info['name']} ({info['sex']}{info['age']}歳) {info['tozai']} {info['trainer_name']}")
```

### 調教師・馬主でフィルタ

```python
# 全馬データから特定調教師の馬を抽出
from common.jravan.um_parser import build_horse_name_index

index = build_horse_name_index()

friendly_horses = []
for name, horse_id in index.items():
    horse = find_horse_by_id(horse_id)
    if horse and "友道" in horse.trainer_name:
        friendly_horses.append(horse)

print(f"友道厩舎: {len(friendly_horses)} 頭")
```

## 🔍 トラブルシューティング

### インデックスが見つからない

```powershell
# インデックスファイルの確認
ls KeibaCICD.TARGET\data\horse_name_index.json

# なければ構築
python scripts/horse_id_mapper.py --build-index
```

### 馬が見つからない

1. **馬名が正確か確認**:
   ```python
   # 部分一致で検索
   horses = search_horses_by_name("ドウデ")
   for h in horses:
       print(h.name)
   ```

2. **抹消馬かチェック**:
   ```python
   horse = find_horse_by_id("2015100123")
   if horse.del_kubun == "1":
       print(f"抹消済み: {horse.del_date}")
   ```

3. **UM_DATAファイルが存在するか確認**:
   ```python
   from common.config import get_jv_data_root
   um_path = get_jv_data_root() / "UM_DATA"
   print(f"UM_DATAパス: {um_path}")

   # ファイル一覧
   from common.jravan.um_parser import get_um_files
   files = get_um_files()
   print(f"Found {len(files)} UM files")
   for f in files[:5]:
       print(f"  {f.name}")
   ```

### インデックス構築が遅い

約20ファイル（各100MB程度）を処理するため、1-2分かかります。

**進行状況を確認**:
```powershell
python scripts/horse_id_mapper.py --build-index
# => UM20261.DAT: 50000 records, +48234 new
# => UM20262.DAT: 50000 records, +1234 new
# => ...
```

## 📚 関連リソース

### プロジェクト内

- [horse_id_mapper.py](../../../scripts/horse_id_mapper.py) - 馬名→ID変換ツール
- [parse_jv_horse_data.py](../../../scripts/parse_jv_horse_data.py) - UM_DATAパーサー
- [ID変換](../ID_MAPPING.md) - ID変換の詳細仕様

### CLI使用例

```powershell
# 馬名で検索
python scripts/parse_jv_horse_data.py --search "ドウデュース"

# 馬IDで検索
python scripts/parse_jv_horse_data.py --horse-id 2019103487

# インデックス情報表示
python scripts/horse_id_mapper.py --info

# 馬名からID取得
python scripts/horse_id_mapper.py --name "ドウデュース"
```

### JV-Data仕様書

- [JV_UM_UMA 仕様](https://jra-van.jp/dlb/sdk/document.html)
- レコード長: 1609バイト
- レコード種別: `UM`

---

*最終更新: 2026-01-30*
