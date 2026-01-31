# UM_DATA 馬データ仕様

## 概要

JRA-VAN JV-DataのUM（競走馬マスタ）データ形式を解説します。

TARGET frontier JVでは `Y:/UM_DATA/` に保存されます。

## ファイル構造

### ディレクトリ構造

```
Y:/UM_DATA/
├── {年}/
│   ├── UM{年}{半期}.DAT   # 馬データ本体
│   ├── UD{年}{半期}.IDX   # インデックスファイル
│   ├── UR{年}.IDX         # レース参照インデックス
│   ├── UR{年}0.DAT        # レース成績データ
│   ├── SK2{年}{半期}.DAT  # 産駒データ
│   └── SK2{年}{半期}.IDX  # 産駒インデックス
└── BC{年}.LOG             # バックアップログ
```

### ファイル命名規則

- `UM{YYYY}{H}.DAT`: 馬データ本体
  - YYYY: 西暦4桁
  - H: 半期（1=上半期, 2=下半期）
  - 例: `UM20242.DAT` = 2024年下半期の馬データ

## レコード構造 (JV_UM_UMA)

固定長レコード: **1609バイト**

エンコーディング: **Shift-JIS**

### フィールド定義

| Offset | Length | Field | 説明 |
|--------|--------|-------|------|
| 1-11 | 11 | head | レコードヘッダー |
| 12-21 | 10 | KettoNum | **血統登録番号（馬ID）** |
| 22 | 1 | DelKubun | 競走馬抹消区分 |
| 23-30 | 8 | RegDate | 競走馬登録年月日 (YYYYMMDD) |
| 31-38 | 8 | DelDate | 競走馬抹消年月日 (YYYYMMDD) |
| 39-46 | 8 | BirthDate | 生年月日 (YYYYMMDD) |
| 47-82 | 36 | Bamei | **馬名** (全角18文字) |
| 83-118 | 36 | BameiKana | 馬名半角カナ |
| 119-178 | 60 | BameiEng | 馬名欧字 |
| 179 | 1 | ZaikyuFlag | JRA施設在きゅうフラグ |
| 180-198 | 19 | Reserved | 予備 |
| 199-200 | 2 | UmaKigoCD | 馬記号コード |
| 201 | 1 | SexCD | **性別コード** |
| 202 | 1 | HinsyuCD | 品種コード |
| 203-204 | 2 | KeiroCD | 毛色コード |
| 205-849 | 644 | Ketto3Info[14] | 3代血統情報 (46bytes×14) |
| 850 | 1 | TozaiCD | 東西所属コード |
| 851-855 | 5 | ChokyosiCode | **調教師コード** |
| 856-863 | 8 | ChokyosiRyakusyo | 調教師名略称 |
| ... | ... | ... | (以下省略) |

### 性別コード (SexCD)

| Code | 説明 |
|------|------|
| 1 | 牡 |
| 2 | 牝 |
| 3 | セン |

### 東西所属コード (TozaiCD)

| Code | 説明 |
|------|------|
| 1 | 美浦 (東) |
| 2 | 栗東 (西) |

## インデックスファイル (UD*.IDX)

馬IDから本体ファイルのバイトオフセットを高速検索するためのインデックス。

### 構造 (推定)

各エントリは以下の情報を含む:
- 血統登録番号 (10バイト)
- 馬名の一部 (参照用)
- バイトオフセット (4バイト)

## 使用例

### Python での読み込み

```python
import struct

def read_um_record(data: bytes, offset: int = 0) -> dict:
    """UM レコードをパース"""
    RECORD_LEN = 1609
    record = data[offset:offset + RECORD_LEN]
    
    # Shift-JIS でデコード
    def decode(b: bytes) -> str:
        return b.decode('shift_jis', errors='replace').strip()
    
    return {
        'ketto_num': decode(record[11:21]),        # 血統登録番号
        'birth_date': decode(record[38:46]),       # 生年月日
        'name': decode(record[46:82]).replace('\u3000', ''),  # 馬名
        'name_kana': decode(record[82:118]),       # 馬名カナ
        'sex_cd': decode(record[200:201]),         # 性別コード
        'trainer_code': decode(record[850:855]),   # 調教師コード
    }

def search_horse_by_id(horse_id: str, data_path: str) -> dict:
    """馬IDでデータを検索"""
    with open(data_path, 'rb') as f:
        data = f.read()
    
    RECORD_LEN = 1609
    num_records = len(data) // RECORD_LEN
    
    for i in range(num_records):
        offset = i * RECORD_LEN
        ketto_num = data[offset + 11:offset + 21].decode('shift_jis')
        if ketto_num == horse_id:
            return read_um_record(data, offset)
    
    return None
```

## 関連ファイル

- `UR*.DAT`: 馬毎レースデータ（過去成績）
- `SK2*.DAT`: 産駒データ
- `Y:/DE_DATA/`: 出馬表データ（当日情報）
- `Y:/SE_DATA/`: 成績データ

## 参考

- JRA-VAN Data Lab. SDK Ver4.9.0.2
- JV-Data構造体 (JVData_Struct.cs)
- TARGET frontier JV ヘルプ
