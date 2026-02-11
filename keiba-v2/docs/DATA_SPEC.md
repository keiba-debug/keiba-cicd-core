# JRA-VAN データ仕様書 (keiba-v2)

> TARGET経由で取得したJRA-VANバイナリデータの仕様。
> Shift-JIS エンコーディング、固定長レコード形式。

---

## ID体系

| 対象 | 桁数 | 形式 | 例 |
|------|------|------|-----|
| race_id | 16桁 | `YYYYMMDDJJKKNNRR` | `2026012406010208` |
| ketto_num (馬ID) | 10桁 | `YYYYNNNNNN` | `2019103487` |
| trainer_code | 5桁 | `NNNNN` | `01155` |
| jockey_code | 5桁 | `NNNNN` | `01018` |

### race_id構成
```
YYYY = 年 (2026)
MM   = 月 (01)
DD   = 日 (24)
JJ   = 場所コード (06=中山)
KK   = 回 (01)
NN   = 日 (02)
RR   = レース番号 (08)
```

---

## SE_DATA (成績データ) - 555 bytes/record

出走馬1頭=1レコード。レースごとに出走頭数分のレコードが存在。

| Offset | Length | Field | 備考 |
|--------|--------|-------|------|
| 0-3 | 4 | Year | |
| 4-5 | 2 | MonthDay(M) | |
| 6-7 | 2 | MonthDay(D) | |
| 8-9 | 2 | JyoCD (場所) | |
| 10-11 | 2 | Kai | |
| 12-13 | 2 | Nichi | |
| 14-15 | 2 | RaceNum | |
| 27 | 1 | Wakuban (枠番) | |
| 28-29 | 2 | Umaban (馬番) | |
| 30-39 | 10 | KettoNum (馬ID) | 10桁 |
| 40-75 | 36 | Horse Name | 全角18文字 |
| 78 | 1 | SexCD | 1=牡,2=牝,3=セ |
| 82-83 | 2 | Age | |
| 84 | 1 | TozaiCD | 1=美浦, 2=栗東 |
| 85-89 | 5 | TrainerCode | 5桁調教師コード |
| 90-97 | 8 | TrainerName | Shift-JIS略称 |
| 288-290 | 3 | Futan (斤量) | ×0.1 (例: 580→58.0kg) |
| 296-300 | 5 | JockeyCode | 5桁騎手コード |
| 306-313 | 8 | Jockey Name | Shift-JIS略称 |
| 324-326 | 3 | HorseWeight (馬体重) | kg |
| 327 | 1 | ZogenFugo (+/-) | |
| 328-330 | 3 | ZogenSa (増減) | |
| 334-335 | 2 | Finish Position (着順) | |
| 338-341 | 4 | Time (MSST) | M分S秒S.T (例: 2132→2:13.2) |
| 351-358 | 8 | Corners (通過順位) | 2桁×4コーナー |
| 359-362 | 4 | Odds (単勝オッズ) | ×0.1 |
| 363-364 | 2 | Popularity (人気) | |
| 387-389 | 3 | Last4F (上がり4F) | ×0.1秒 |
| 390-392 | 3 | Last3F (上がり3F) | ×0.1秒 |

### SE_DATAバイトオフセット確認状況
- Trainer Code (85-89): UM_DATAとのクロス検証で100%一致確認済み
- Jockey Code (296-300): バイトダンプで5桁コード抽出確認済み
- TozaiCD (84): 1=美浦, 2=栗東 確認済み

---

## SR_DATA (レースサマリー) - 1272 bytes/record

1レース=1レコード。ペース情報を含む。

| Offset | Length | Field | 備考 |
|--------|--------|-------|------|
| 697-700 | 4 | Distance | m |
| 705-706 | 2 | Track CD | 10=芝左,11=芝右,23=ダート左 等 |
| 883-884 | 2 | Runners (出走頭数) | |
| 888-889 | 2 | Baba (馬場状態) | 10=良,11=稍,12=重,13=不 |
| 969-971 | 3 | S3 (前半3F) | ×0.1秒 |
| 972-974 | 3 | S4 (前半4F) | ×0.1秒 |
| 975-977 | 3 | L3 (上がり3F) | ×0.1秒 |
| 978-980 | 3 | L4 (上がり4F) | ×0.1秒 |

### RPCI計算
```python
rpci = (s3 / (s3 + l3)) * 100
# 50 = 平均ペース、>50 = スロー、<50 = ハイペース
```

---

## UM_DATA (馬マスタ) - 1609 bytes/record

1馬=1レコード。血統登録情報。

| Offset | Length | Field | 備考 |
|--------|--------|-------|------|
| 0-9 | 10 | KettoNum | 10桁馬ID |
| 16-51 | 36 | Horse Name | 全角18文字 |
| 261 | 1 | SexCD | 1=牡,2=牝,3=セ |
| 849 | 1 | TozaiCD | ※常に"0"→trainer_codeから推定 |
| 850-854 | 5 | Trainer Code | 5桁 |
| 855-890 | 36 | Trainer Name | 全角18文字 |

### TozaiCD推定ロジック
```python
# offset 849は常に"0"のため、trainer_codeの先頭2桁で推定
prefix = int(trainer_code[:2])
tozai = "2" if prefix >= 10 else "1"  # ≥10=栗東, <10=美浦
```

---

## HC_DATA (坂路調教) - 47 bytes/record

| Offset | Length | Field | 備考 |
|--------|--------|-------|------|
| 1 | 1 | Tresen | 0=美浦, 1=栗東 |
| 2-9 | 8 | Date (YYYYMMDD) | |
| 10-13 | 4 | Time (HHMM) | |
| 14-23 | 10 | KettoNum | |
| 24-27 | 4 | 4F Time | ×0.1秒 |
| 28-30 | 3 | Lap4 (800m-600m) | ×0.1秒 |
| 31-34 | 4 | 3F Time | ×0.1秒 |
| 35-37 | 3 | Lap3 (600m-400m) | ×0.1秒 |
| 38-41 | 4 | 2F Time | ×0.1秒 |
| 42-44 | 3 | Lap2 (400m-200m) | ×0.1秒 |
| 45-47 | 3 | Final 1F | ×0.1秒 |

---

## WC_DATA (コース調教) - 92 bytes/record

| Offset | Length | Field | 備考 |
|--------|--------|-------|------|
| 1 | 1 | Tresen | 0=美浦, 1=栗東 |
| 2-9 | 8 | Date | |
| 10-13 | 4 | Time | |
| 14-23 | 10 | KettoNum | |
| 24-25 | 2 | Course Code | 31=美浦D左 等 |
| 35-92 | 58 | Time Data | 10F〜1F (4桁total+3桁lap) |

---

## CK_DATA (調教データ) - 可変長

TARGETの調教関連ファイル。HC/WCデータのソース。
- ファイル数: 約17,210
- 形式: ファイル先頭にヘッダ、以降HC/WCレコード

---

## レース傾向5段階分類

```python
def classify_trend(rpci, l3, s3):
    if rpci >= 50 and is_long_sprint(s3, l3):
        return "long_sprint"       # ロンスパ戦
    elif rpci >= 51:
        return "sprint_finish"     # 瞬発戦
    elif rpci > 48:
        return "even_pace"         # 平均ペース
    elif l3 < threshold:
        return "front_loaded_strong"  # H後傾（前傾+速い上がり）
    else:
        return "front_loaded"      # H前傾
```

---

## 場所コード

| Code | Name | Code | Name |
|------|------|------|------|
| 01 | 札幌 | 06 | 中山 |
| 02 | 函館 | 07 | 中京 |
| 03 | 福島 | 08 | 京都 |
| 04 | 新潟 | 09 | 阪神 |
| 05 | 東京 | 10 | 小倉 |

## コースタイプ

| Code | Type |
|------|------|
| 10 | 芝左回り |
| 11 | 芝右回り |
| 12 | 芝直線 |
| 17 | 芝右外 |
| 18 | 芝右内→外 |
| 19 | 芝右外→内 |
| 20 | 芝左外 |
| 23 | ダート左 |
| 24 | ダート右 |
| 29 | 障害 |

## 馬場状態

| Code | State |
|------|-------|
| 10 | 良 |
| 11 | 稍重 |
| 12 | 重 |
| 13 | 不良 |
