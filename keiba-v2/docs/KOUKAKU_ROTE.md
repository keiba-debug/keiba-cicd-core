# 降格ローテ（Demotion Rotation）開発ドキュメント

> **実装バージョン**: v5.6 (Session 33, 2026-02-20)
> **理論出典**: 「降格ローテ 激走の9割は"順当"である」（とうけいば著, 2021）
> **理論まとめ**: `C:\KEIBA-CICD\競馬予想理論\降格ローテ理論まとめ.md`

---

## 1. 概要

### 降格ローテとは

同一クラス（例: 2勝クラス）内でも、レースごとにレベルが異なる。
**前走Hレベル戦で敗れた馬が、今走低レベル戦に出走する**ローテーションを「降格ローテ」と呼ぶ。

- 「激走」の大半は「相手が弱くなった結果の好走」＝ **順当**
- ファンが見落とす「相手弱化のローテーション」を定量的に検出する
- Value Betの「市場に織り込まれていないシグナル」と完全に合致

### 実装の2層構造

| レイヤー | 内容 | 市場織り込み |
|---------|------|------------|
| **レースレベル判定** | レイティングベースでH/M/L分類 | 部分的 |
| **条件ベース7パターン** | 競馬場ランク・性別・時期等の条件組合せ | **低い（=妙味あり）** |

書籍(Column 02)の教訓: タイムベースのレベル判定は市場に「バレやすい」。
条件ベースの判定こそがValue Betの源泉。

---

## 2. データ基盤

### 2-1. グレード序列 (`core/constants.py`)

```python
GRADE_LEVEL = {
    "G1": 1, "G2": 2, "G3": 3, "Listed": 4,
    "OP": 5, "3勝クラス": 6, "2勝クラス": 7, "1勝クラス": 8,
    "未勝利": 9, "新馬": 10,
}
```

数値が小さいほど上位クラス。`grade_level_diff = 今走 - 前走`で正=降級方向。

### 2-2. 競馬場ランク (`core/constants.py`)

```python
VENUE_RANK = {
    "阪神": "A", "京都": "A",   # 栗東馬比率最高 → 最もレベルが高い
    "小倉": "B", "中京": "B",
    "札幌": "C", "函館": "C",
    "新潟": "D", "福島": "D",
    "東京": "E", "中山": "E",   # 美浦馬のホーム → レベルが低い
}
VENUE_RANK_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
```

栗東馬の割合が高い＝レベルが高い。`venue_rank_diff = 今走 - 前走`で正=降格方向。

### 2-3. レースマスター拡張 (`core/models/race.py`, `core/jravan/sr_parser.py`)

race JSON (data_version 4.2) に追加されたフィールド:

| フィールド | 型 | 判定方法 |
|-----------|-----|---------|
| `is_handicap` | bool | `'ハンデ' in race_name` |
| `is_female_only` | bool | `'牝' in race_name` or 全出走馬が牝馬 |

**SR_DATAに関する重要な発見**: バイト632はJyuryoCD（斤量条件）ではなくJyokenCD7[0]であった。
ハンデ戦はrace_nameキーワードマッチのみで検出（年間約30レース）。

### 2-4. 馬戦績キャッシュ拡張 (`builders/build_horse_history.py`)

`horse_history_cache.json` の各エントリに追加:

```python
{
    "race_date": "2025-01-05",
    "distance": 1200,
    "track_type": "dirt",
    "finish_position": 1,
    ...
    "venue_name": "中山",        # NEW
    "grade": "未勝利",            # NEW
    "is_handicap": false,        # NEW
    "is_female_only": false,     # NEW
}
```

### 2-5. レースレベルインデックス (`analysis/rating_standards.py`)

`data3/indexes/race_level_index.json` — 各レースのレベル判定:

```json
{
  "2025010506010101": {
    "avg_rating": 48.3,
    "max_rating": 55.2,
    "num_rated": 14,
    "class_baseline": 45.0,
    "class_stdev": 5.2,
    "level_vs_class": 3.3,
    "level_rank": "H"
  }
}
```

- `level_vs_class = avg_rating - class_baseline`
- `level_rank`: `> +0.5σ` → "H", `< -0.5σ` → "L", else "M"
- **分布**: H:16.9% / M:67.2% / L:15.8%（8,991レース, 2020-2026）

### 2-6. 会場別統計 (`rating_standards.json` v4.0)

```json
{
  "venue_stats": {
    "阪神": {
      "turf": {"avg": 52.1, "std": 4.8, "count": 312},
      "dirt": {"avg": 49.3, "std": 5.1, "count": 285}
    },
    ...
  }
}
```

---

## 3. 降格ローテ7パターン

`ml/features/rotation_features.py` で実装。

### パターン一覧

| # | パターン | トラック | 前走条件 | 今走条件 | 実装状態 |
|---|---------|---------|---------|---------|---------|
| ① | 栗東馬割合 | ダート | 上位ランク会場 | 下位ランク会場 | `is_koukaku_venue` |
| ② | 性別×距離 | ダート | 牡牝混合1400m+ | 牝馬限定戦 | `is_koukaku_female` |
| ③ | 性別×開催時期 | ダート | 12-4月牡牝混合 | 5-9月牡牝混合 | `is_koukaku_season` |
| ④ | 馬齢 | 芝 | 3歳限定戦 | 3歳以上戦 | **TODO** (常時0) |
| ⑤ | 距離短縮 | 芝 | 1600m以上 | 1200m以下 | `is_koukaku_distance` |
| ⑥ | 芝→ダート | 両方 | 芝(3C10番手以下) | ダート | `is_koukaku_turf_to_dirt` |
| ⑦ | ハンデ戦 | 両方 | 非ハンデ戦 | ハンデ戦 | `is_koukaku_handicap` (要改善) |

### パターン④の実装課題

horse_history_cacheに`race_class`（例: "3歳未勝利"）が含まれていないため、
前走が「3歳限定戦」かどうかを判定できない。`grade`フィールドに"新馬"/"未勝利"はあるが
3歳限定かどうかの情報が欠落。

**対策案**: `sr_parser.py`の`_classify_age_class()`結果をhorse_historyに追加。

### パターン⑦の実装課題

ハンデ戦は`race_name`の「ハンデ」キーワードでのみ検出されるため、
条件戦のハンデ戦（レース名に「ハンデ」がないケース）を見逃す可能性がある。
SR_DATAにJyuryoCDフィールドが見つからなかったため、代替検出方法の調査が必要。

**検出実績**: 年間約30レース（2025年）。

### 実装コード（抜粋）

```python
def _compute_koukaku_features(result, last, current_grade, current_venue, ...):
    """降格ローテ7パターン + レベル差の特徴量を計算"""
    # パターン①: 栗東馬割合（ダート限定）
    if current_track_type == 'dirt' and cur_vr is not None and prev_vr is not None:
        is_koukaku = cur_vr > prev_vr
        result['is_koukaku_venue'] = 1 if is_koukaku else 0

    # パターン②: 性別×距離（ダート限定）
    if (current_track_type == 'dirt'
            and current_is_female_only
            and not prev_is_female_only
            and prev_track_type == 'dirt' and prev_distance >= 1400):
        result['is_koukaku_female'] = 1

    # パターン⑥: 芝→ダート（3コーナー10番手以下）
    if current_track_type == 'dirt' and prev_track_type == 'turf':
        corners = last.get('corners', [])
        corner3 = corners[2] if len(corners) >= 3 else 0
        if corner3 >= 10:
            result['is_koukaku_turf_to_dirt'] = 1

    result['koukaku_rote_count'] = koukaku_count  # 該当パターン合計
```

---

## 4. ML特徴量

### 特徴量リスト（11個）

| 特徴量 | 分類 | 説明 |
|--------|------|------|
| `prev_grade_level` | MARKET | 前走グレード序列(1-10) |
| `grade_level_diff` | MARKET | 今走-前走グレード差（正=降級方向） |
| `venue_rank_diff` | MARKET | 今走-前走会場ランク差（正=降格方向） |
| `is_koukaku_venue` | VALUE | パターン①: ダート会場ランク降格 |
| `is_koukaku_female` | VALUE | パターン②: ダート混合→牝馬限定 |
| `is_koukaku_season` | VALUE | パターン③: ダート冬春→夏 |
| `is_koukaku_age` | VALUE | パターン④: 芝3歳限定→古馬 (TODO) |
| `is_koukaku_distance` | VALUE | パターン⑤: 芝距離短縮1600+→1200- |
| `is_koukaku_turf_to_dirt` | VALUE | パターン⑥: 芝後方→ダート |
| `is_koukaku_handicap` | VALUE | パターン⑦: 非ハンデ→ハンデ |
| `koukaku_rote_count` | VALUE | 該当パターン合計数 |

### MARKET vs VALUE分類

- **MARKET** (3個): `prev_grade_level`, `grade_level_diff`, `venue_rank_diff`
  → 出馬表を見れば明らかな情報 → Model A (精度モデル) にのみ使用
- **VALUE** (8個): `is_koukaku_*`, `koukaku_rote_count`
  → 条件の組み合わせは見えにくい → Model A + Model B 両方に使用

### ML v5.2b実験結果

| モデル | AUC | v5.1比 | 特徴量数 |
|--------|-----|--------|---------|
| Model A (top3, all) | 0.8240 | -0.0001 (=) | 98 |
| **Model B (top3, value)** | **0.7843** | **+0.0010** | 82 |
| Model W (win, all) | 0.8378 | -0.0005 (=) | 98 |
| **Model WV (win, value)** | **0.7873** | **+0.0013** | 82 |

**Value系モデルのAUCが改善** — 降格ローテは市場に織り込まれにくい信号。

### Feature Importance

| 特徴量 | Model A (98) | Model B (82) |
|--------|-------------|-------------|
| `prev_grade_level` | #42 (1,174) | — (MARKET) |
| `venue_rank_diff` | #48 (947) | — (MARKET) |
| `grade_level_diff` | #63 (671) | — (MARKET) |
| `koukaku_rote_count` | #83 (210) | #69 (1,335) |
| `is_koukaku_venue` | #86 (137) | #73 (761) |
| `is_koukaku_female` | #82 (230) | #74 (670) |
| `is_koukaku_distance` | #95 (18) | #75 (356) |
| `is_koukaku_season` | #91 (44) | #76 (292) |
| `is_koukaku_turf_to_dirt` | #90 (64) | #77 (279) |
| `is_koukaku_age` | #96 (0) | #80 (0) |
| `is_koukaku_handicap` | #97 (0) | #81 (0) |

**所見**:
- MARKET特徴量 (`prev_grade_level` #42) は中位の重要度
- VALUE特徴量は全体的に低重要度だが非ゼロ（`koukaku_rote_count` #69がベスト）
- Dead features: `is_koukaku_age`(未実装), `is_koukaku_handicap`(30レースのみ)

### VB ROI

| Gap | Place ROI | Win ROI |
|-----|-----------|---------|
| ≥2 | 101.9% | 91.7% |
| ≥3 | 114.5% | 96.0% |
| ≥4 | 127.0% | 107.0% |
| ≥5 | 132.4% | 120.4% |

Place VB gap≥3以上、Win VB gap≥4以上でプラス収支を維持。

---

## 5. Web UI

### 5-1. 出馬表 — 降格ローテバッジ (`predictions-content.tsx`)

VBテーブルおよびレースカードテーブルの馬名セル内に表示:

```tsx
{(entry.koukaku_rote_count ?? 0) > 0 && (
  <span className="ml-1 text-[9px] px-1 py-0.5 rounded
    bg-orange-100 text-orange-700
    dark:bg-orange-900/30 dark:text-orange-300"
    title={getKoukakuDetail(entry)}>
    降格{count > 1 ? `×${count}` : ''}
  </span>
)}
```

- オレンジ色バッジ
- 複数パターン該当時は `降格×2` のように表示
- ツールチップで該当パターン詳細を表示

### 5-2. レイティング分析 — 会場別統計 (`analysis/rating/page.tsx`)

| 追加コンテンツ | 内容 |
|---------------|------|
| 会場別レイティング統計テーブル | 10会場×芝/ダートの平均/標準偏差/サンプル数 |
| 競馬場ランクバッジ | A(赤)〜E(青)のカラーバッジ |
| 降格ローテ理論解説カード | 書籍要約 + VB哲学との関連 |

### 5-3. predict.py出力

```json
{
  "entries": [
    {
      "umaban": 1,
      "koukaku_rote_count": 1,
      "is_koukaku_venue": 1,
      "is_koukaku_female": 0,
      "is_koukaku_season": 0,
      "is_koukaku_distance": 0,
      "is_koukaku_turf_to_dirt": 0,
      "is_koukaku_handicap": 0,
      ...
    }
  ],
  "grade": "2勝クラス",
  "is_handicap": false,
  "is_female_only": false,
  ...
}
```

---

## 6. 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `core/constants.py` | GRADE_LEVEL, VENUE_RANK, VENUE_RANK_ORDER 定数追加 |
| `core/jravan/sr_parser.py` | SrRecordにis_handicap/is_female_only追加、JyuryoCDデッドコード削除 |
| `core/models/race.py` | RaceMasterにis_handicap/is_female_only追加 |
| `builders/build_race_master.py` | 新フィールド出力、entries-based牝馬限定検出 |
| `builders/build_horse_history.py` | grade/venue_name/is_handicap/is_female_only追加 |
| `analysis/rating_standards.py` | build_race_level_index(), analyze_venue_stats(), v4.0 |
| `ml/features/rotation_features.py` | 降格ローテ11特徴量（_compute_koukaku_features） |
| `ml/experiment.py` | ROTATION_FEATURES +11, MARKET_FEATURES +3 |
| `ml/predict.py` | 降格ローテ情報出力 |
| `web/src/lib/data/predictions-reader.ts` | PredictionEntry/PredictionRace型拡張 |
| `web/src/app/predictions/predictions-content.tsx` | 降格ローテバッジ（VB+レースカード） |
| `web/src/app/analysis/rating/page.tsx` | 会場別統計テーブル + 降格ローテ解説 |

---

## 7. 生成データ

| ファイル | サイズ | 内容 |
|---------|--------|------|
| `data3/races/` (20,415 JSON) | ~170MB | data_version 4.2（is_handicap/is_female_only追加） |
| `data3/ml/horse_history_cache.json` | 103.6 MB | 36,271馬（grade/venue_name等追加） |
| `data3/indexes/race_level_index.json` | ~2MB | 8,991レースのH/M/L判定 |
| `data3/analysis/rating_standards.json` | ~50KB | v4.0（venue_stats追加） |

---

## 8. 既知の制限事項と今後の改善案

### 制限事項

1. **パターン④(馬齢)が未実装**: horse_historyにrace_class（3歳限定 vs 古馬）情報がない
2. **パターン⑦(ハンデ戦)の検出率が低い**: race_nameキーワードのみ（年間30レース）
3. **SR_DATAのJyokenCDオフセットが1バイトずれている可能性**: @617→@616（要検証）
4. **レースレベル判定はレイティングベース**: 書籍のタイムランク方式とは異なる（馬場差補正未実装）
5. **40倍フィルタ未適用**: 書籍では「単勝40倍以下」に限定するが、ML特徴量では全馬に適用

### 改善案

| 優先度 | 内容 | 期待効果 |
|--------|------|---------|
| 高 | パターン④実装（race_class追加） | is_koukaku_ageの活性化 |
| 高 | 低重要度特徴量の除外実験 | VB ROI改善（ノイズ除去） |
| 中 | 昇格ローテ（逆パターン）の検出 | 「危険な人気馬」検出強化 |
| 中 | 自作タイムランク（馬場差補正付き） | 書籍のレベル判定に近づく |
| 低 | ハンデ戦検出強化（DB or JyuryoCD調査） | パターン⑦の完成度向上 |
| 低 | 降格ローテ×VBバックテスト | 降格ローテ馬のROI定量化 |

---

## 9. 参考：書籍の降格ローテ早見表

### 降格ローテ（狙い目）

| # | パターン | トラック | 前走 → 今走 |
|---|---------|---------|------------|
| ① | 栗東馬割合 | ダート | 上位ランク会場 → 下位ランク会場 |
| ② | 性別×距離 | ダート | 牡牝混合1400m+ → 牝馬限定戦 |
| ③ | 性別×時期 | ダート | 12-4月牡牝混合 → 5-9月牡牝混合 |
| ④ | 馬齢 | 芝 | 3歳限定戦 → 3歳以上戦 |
| ⑤ | 距離短縮 | 芝 | 1600m以上 → 1200m以下 |
| ⑥ | 芝→ダート | 両方 | 芝(3C10番手以下) → ダート |
| ⑦ | ハンデ戦 | 両方 | 非ハンデ → ハンデ |

### 昇格ローテ（危険な人気馬）

| # | パターン | トラック | 前走 → 今走 |
|---|---------|---------|------------|
| ① | 栗東馬割合 | ダート | 下位ランク会場 → 上位ランク会場 |
| ② | 性別×距離 | ダート | 牝馬限定戦 → 牡牝混合1400m+ |
| ③ | 性別×時期 | ダート | 5-9月牡牝混合 → 10-2月牡牝混合 |
| ⑤ | 距離延長 | 両方 | 1200m以下 → 1600m以上 |
| ⑥ | ダート→芝 | 芝 | ダート(3C10番手以下) → 芝 |
| ⑦ | ハンデ戦 | 両方 | ハンデ → 非ハンデ |

> **全パターン共通**: 単勝オッズ40倍以下の馬が対象
