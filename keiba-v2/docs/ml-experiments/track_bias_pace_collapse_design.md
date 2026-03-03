# トラックバイアス × 前崩れ分離基盤 設計

## 背景

「外差し」と「前崩れ」は一見似た結果（差し・追込好走）を生むが、原因が全く異なる。

| 現象 | 原因 | データソース | 予測可能性 |
|------|------|------------|-----------|
| **外差し** (Track Bias) | 開催後半の内荒れ馬場 | KAA (馬場状態) | 当日=高、過去走=確定 |
| **前崩れ** (Pace Collapse) | ハイペースで先行馬が止まる | SED (race_pace, corner4→fp) | 当日=中(メンバー依存)、過去走=確定 |

## 分析結果 (SED 20,685レース + KAA 1,783開催日)

### 前崩れ率 全体
- 全体: 23.7% (4,910/20,685)
- 芝: 31.8% > ダート: 17.5%
- Hペース: 30.0% > Mペース: 23.7% > Sペース: 19.0%

### 外差し × 前崩れ クロス (芝)
| 条件 | 前崩れ率 | 解釈 |
|------|---------|------|
| Hペース + バイアスなし | 37.9% | **純粋ペース崩壊** |
| Hペース + 外差しバイアス | 39.8% | 複合型 |
| Sペース + バイアスなし | 24.0% | 通常レース |
| Sペース + 外差しバイアス | 26.0% | **純粋トラックバイアス** |

→ バイアスの有無で+2pt差、ペースで+14pt差 → ペースの影響が支配的だが独立した現象

### 前崩れ定義
4角3番手以内の馬の平均着順 > 頭数/2

## 活用方針

### 1. 過去走IDM補正 (jrdb_features.py)

**概念**: 馬の過去走IDMを「レース質に恵まれたか/不利だったか」で補正

```
idm_adjusted = idm - race_quality_adjustment
```

| 状況 | 補正 | 例 |
|------|------|-----|
| 外差しバイアスで差して好走 | IDMを割引 (-3~-5) | 新潟5月外差しで追込4着→実力は低め |
| 外差しバイアスで逃げて好走 | IDMを割増 (+3~+5) | 内荒れで逃げて3着→実力高い |
| 前崩れで差して好走 | IDMを割引 (-2~-3) | Hペースで差し2着→展開恵まれ |
| 前崩れで逃げて好走 | IDMを割増 (+3~+5) | Hペースで逃げ粘り3着→実力相当 |
| 内有利で外枠から好走 | IDMを割増 (+2~+3) | 開幕京都で外枠差し3着→実力高い |

### 2. Closingモデル改善 (closing_race_features.py)

**新規特徴量候補**:

#### A. KAA由来 (トラックバイアス)
| 特徴量 | 説明 | 型 |
|--------|------|-----|
| kaa_turf_inner | 芝内回り状態 (1-4) | int |
| kaa_turf_outer | 芝外回り状態 (1-4) | int |
| kaa_bias_direction | 内外差 (inner-outer, 正=外差し有利) | int |
| kaa_straight_bias | 直線馬場差 (最内-大外, 正=外有利) | int |
| kaa_is_outer_bias | 外差しバイアス flag | bool |

#### B. SED由来 (ペース・展開)
| 特徴量 | 説明 | 型 |
|--------|------|-----|
| pace_collapse_rate_venue | 同コース過去の前崩れ率 | float |
| avg_front3f_runners | 出走馬のテン指数平均 | float |
| speed_variance | 出走馬のテン指数のばらつき | float |
| front_runner_count | 脚質=逃/先の出走頭数 | int |

### 3. 当レース予測への応用 (将来)

KAA + KYI(pred_pace, kyakushitsu) を組み合わせて:
- 当日の「外差し確率」をKAAから推定
- 当日の「前崩れ確率」をメンバー構成+KYI pred_paceから推定
- 各馬が「レース質に合うか」を判定

### 4. bet_engine連携 (将来)

- closing_race_proba >= 18% かつ脚質=差/追 → VBスコア加算
- 外差しバイアス高 かつ外枠 かつ差し脚質 → VBスコア加算
- 前崩れリスク高 かつ逃げ脚質 → VBスコア減算

## データフロー

```
KAA index (1,783日) ──┐
                      ├─→ race_quality 特徴量 ─→ Closingモデル / P/W/ARモデル
SED index (286K馬走) ─┘
                      ├─→ 過去走IDM補正 ─→ jrdb_features.py

KYI index (286K馬走) ──→ 当日ペース予測 ─→ Closingモデル
```

## 実装順序

1. **Phase 1**: KAA特徴量をClosingモデルに追加（kaa_bias_direction等）
2. **Phase 2**: 過去走IDM補正（外差し/前崩れ発生時のIDM割引/割増）
3. **Phase 3**: P/W/ARモデルにレース質特徴量追加
4. **Phase 4**: bet_engineとの連携

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `jrdb/parser.py` | KAA/SED/KYIパーサー（既存） |
| `builders/build_jrdb_index.py` | インデックス構築（既存、SED拡張済み） |
| `ml/features/track_bias_features.py` | **新規**: KAA + SED由来のトラックバイアス/前崩れ特徴量 |
| `ml/features/jrdb_features.py` | 既存: IDM統計 → Phase 2でIDM補正追加 |
| `ml/features/closing_race_features.py` | 既存: Phase 1でKAA特徴量追加 |
