# ドメインモデル (keiba-v2)

> JRA-VANネイティブIDベースのドメインエンティティ定義。
> v1のドメインモデルをv2アーキテクチャ（JRA-VAN中心）に適合。

---

## エンティティ一覧

### Race (レース)
```python
race_id: str          # 16桁 YYYYMMDDJJKKNNRR
date: str             # YYYY-MM-DD
venue_code: str       # 2桁 (01-10)
venue_name: str
kai: int
nichi: int
race_number: int
distance: int         # m
track_type: str       # "turf" / "dirt" / "obstacle"
track_condition: str  # "good" / "slightly_heavy" / "heavy" / "bad"
num_runners: int
pace: RacePace        # s3, l3, rpci, race_trend
entries: List[RaceEntry]
```

### RaceEntry (出走馬)
```python
umaban: int           # 馬番
wakuban: int          # 枠番
ketto_num: str        # 10桁馬ID
horse_name: str
sex_cd: str           # 1=牡, 2=牝, 3=セ
age: int
jockey_name: str
jockey_code: str      # 5桁 (構築予定)
trainer_name: str
trainer_code: str     # 5桁 (UM_DATAから)
futan: float          # 斤量 kg
horse_weight: int     # 馬体重 kg
horse_weight_diff: str  # "+4", "-2" 等
finish_position: int  # 着順
time: str             # "2:13.2"
last_3f: str          # "34.1"
odds: float           # 単勝オッズ
popularity: int       # 人気順
corners: List[int]    # コーナー通過順 [5, 5, 3, 2]
```

### HorseMaster (馬マスタ)
```python
ketto_num: str        # 10桁
name: str
sex_cd: str
tozai_cd: str         # 1=美浦, 2=栗東
trainer_code: str     # 5桁
trainer_name: str
```

### Training (調教)
```python
ketto_num: str        # 10桁
date: str             # YYYYMMDD
time: str             # HHMM
tresen: str           # 0=美浦, 1=栗東
type: str             # "slope" / "course"
time_4f: float        # 4F秒
time_3f: float
time_2f: float
time_1f: float
laps: List[float]     # ラップタイム
```

### KeibabookExtension (keibabook拡張)
```python
race_id: str          # 16桁
scraped_at: str
entries: Dict[str, KeibabookEntryExt]  # key = umaban (文字列)
```

### Prediction (予測)
```python
ketto_num: str
win_prob: float       # 勝率 (0.0-1.0)
place_prob: float     # 複勝確率 (0.0-1.0)
expected_value: float # prob × odds
confidence: float     # 信頼度 (0.0-1.0)
rank_a: int           # Model A順位
rank_b: int           # Model B順位
rank_gap: int         # rank_a - rank_b (Value Bet指標)
should_bet: bool      # EV > 1.0 AND confidence > threshold
```

---

## ドメインサービス

### TrainingEvaluationService
調教データ（HC/WC）を評価し、スコアを算出。

```python
# 評価基準
good_time_threshold = 52.9  # 秒 (坂路、美浦/栗東共通)
base_lap = 13.4             # 秒

# ラップクラス判定
S: base_lap - 1.5s 以下     # 13.4 - 1.5 = 11.9以下
A: base_lap - 0.5s 以下     # 12.9以下
B: base_lap ± 0s            # 13.4以下
C: base_lap + 0.5s 以下     # 13.9以下
D: それ以上

# SS昇格条件: good_time達成 かつ S+またはS=
# スコア: SS=1.0, S+=0.9, S==0.85, S-=0.8, A+=0.7 ...
# 最終スコア = 最終追い切り×0.6 + 一貫性×0.4
```

### ValueBetDetector
Model AとModel Bの予測乖離からValue Betを検出。

```python
# rank_gap = model_a_rank - model_b_rank
# gap > 0: 市場が過小評価（Model Bでは高評価だがModel Aでは低評価）

# 実績 (v2)
# gap >= 3: 複勝ROI 104.7%
# gap >= 4: 複勝ROI 112.1%
```

---

## データフロー

```
JRA-VAN Binary (C:\TFJV)
    │
    ├── SE_DATA → build_race_master → data3/races/{date}/race_{id}.json
    ├── SR_DATA ─┘
    ├── UM_DATA → build_horse_master → data3/masters/horses/{ketto_num}.json
    ├── HC/WC  → (将来) training builder
    │
    └── SE_DATA → build_trainer_master → data3/masters/trainers.json
        SE_DATA → build_jockey_master → data3/masters/jockeys.json

keibabook Scraping
    │
    └── ext_builder → data3/keibabook/{date}/kb_ext_{id}.json

ML Pipeline
    │
    ├── race JSON + horse_history → features → LightGBM → model_a/b
    └── predict → predictions_live.json → WebViewer
```

---

## 結合ルール

JRA-VANレースデータとkeibabook拡張データの結合:

```python
# 結合キー: umaban (馬番)
# keibabook拡張は任意。存在しない場合もJRA-VANデータのみで機能。

merged_entry = {
    **race_entry,                        # JRA-VAN (必須)
    **keibabook_ext.entries[umaban],     # keibabook (任意)
}
```

### Model A vs Model B
| | Model A (精度) | Model B (Value) |
|--|---------------|----------------|
| JRA-VAN特徴量 | 使用 | 使用 |
| keibabook特徴量 | 使用 | **使用しない** |
| 市場系特徴量 | 使用 | **使用しない** |
| 用途 | 精度最大化 | 市場乖離検出 |
