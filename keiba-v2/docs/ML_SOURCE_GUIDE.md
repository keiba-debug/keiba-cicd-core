# ML期待値ベット抽出プロジェクト ソース解説

> JRA-VAN + 競馬ブック + JRDB データを活用し、機械学習で期待値の高いベットを抽出するプロジェクトのソースガイド。
> 開発中ソースや状況を正しく理解するための地図。

**最終更新**: 2026-06-13（Session 156 全面改訂 — 旧版 2026-02-22 は Model A/B・model_reg_b 時代の記述。
現行の P/W/AR + Stars/Nebula + model_registry 体系でコード裏取りして書き直した）

---

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [モデル体系（Stars / Nebula）](#2-モデル体系stars--nebula)
3. [ディレクトリ構成（ml/）](#3-ディレクトリ構成ml)
4. [日次の推論→買い目→投票フロー](#4-日次の推論買い目投票フロー)
5. [特徴量エンジニアリング](#5-特徴量エンジニアリング)
6. [実験・バックテスト・検証ハーネス](#6-実験バックテスト検証ハーネス)
7. [バージョン管理・ロールバック](#7-バージョン管理ロールバック)
8. [Web表示チェーン（表示更新漏れ防止）](#8-web表示チェーン表示更新漏れ防止)
9. [データの場所](#9-データの場所)
10. [関連ドキュメント一覧](#10-関連ドキュメント一覧)

---

## 1. プロジェクト概要

- **期待値ベースの馬券購入支援**: 市場が過小評価している馬（Value Bet）を検出する
- **VB gap**: 市場順位とモデル順位の直接乖離（experiment.py:3247）
  - `vb_gap = (odds_rank - pred_rank_p).clip(lower=0)` … 複勝系
  - `win_vb_gap = (odds_rank - pred_rank_w).clip(lower=0)` … 単勝系
- **EV 計算**（CLAUDE.md 準拠）: 単勝EV = `pred_proba_w_cal × 単勝オッズ`、複勝EV = `pred_proba_p_raw × 複勝最低オッズ`
- **検証の柱**: 的中率でなくキャリブレーション（ブライアスコア/ECE）と gap別ROIブートCI

### 技術スタック

| 領域 | 技術 |
|------|------|
| ML | LightGBM（P/W 分類 + AR 回帰）, IsotonicRegression（キャリブレーション） |
| 言語 | Python 3.11（venv: `keiba-v2/.venv`）, TypeScript |
| Web | Next.js 16, React 19, Tailwind 4 + shadcn/ui |
| データ | JRA-VAN (C:/TFJV), mykeibadb (MySQL オッズ), 競馬ブック, JRDB (8種DL済) |

---

## 2. モデル体系（Stars / Nebula）

`data3/ml/model_registry.json`（schema v2）が**唯一の真実**。`ml/model_loader.py` がロードを一元化。

### Stars系（馬単位: この馬が走るか）

| モデル | 中身 | ファイル | 出力 |
|--------|------|---------|------|
| **polaris** | 平地メイン。**P**(is_top3分類) / **W**(is_win分類) / **AR**(着差Huber回帰) の3本 + calibrators | `model_p.txt` / `model_w.txt` / `model_ar.txt` / `calibrators.pkl` | `pred_proba_p(_raw)`, `pred_proba_w_cal`, `pred_margin_ar`, `rank_p/w` |
| **enif** | 障害専用 (P/W) | `model_obstacle_*.txt` | 同上（障害レースのみ） |

### Nebula系（レース単位: このレースがどうなるか）

| モデル | 中身 | ファイル | 出力 |
|--------|------|---------|------|
| **eclipse** | 差し決着優勢レース判定（旧称 Closing） | `model_closing.txt` | `closing_race_proba` |

将来枠: sirius（激走/伏兵検出）、nova（残差/新興）、vega（血統）等 — `docs/` の各設計メモ参照。
**スタッキング禁止**: Stars/Nebula の視点独立性が ROI の収益源（AR→W スタッキングは失敗実証済み）。

### model_loader API

```python
from ml.model_loader import load_model, list_models, list_versions, get_active_version
bundle = load_model("polaris")            # live（registry の active_version）
bundle = load_model("polaris", "2.2")     # アーカイブ版
bundle.model_p / bundle.model_w / bundle.model_ar / bundle.calibrators / bundle.meta
```

パス解決: 新構造 `ml/models/{name}/live/` → 旧構造 `ml_dir` 直下（polaris は `model_meta.json`）の順でフォールバック。

---

## 3. ディレクトリ構成（ml/）

```
keiba-v2/ml/
├── 学習・実験
│   ├── experiment.py            # 本番実験CLI（P/W/AR学習・VB分析・バージョン保存）★中核
│   ├── experiment_obstacle.py   # enif（障害）実験
│   ├── experiment_closing.py    # eclipse 実験
│   ├── optuna_tuner(_obstacle).py
│   └── experiment_*.py          # lambdarank/regression 等の実験系列
├── 推論・運用（日次）
│   ├── predict.py               # polaris/enif 当日予測 → predictions.json ★中核
│   ├── predict_closing.py       # eclipse 追記
│   ├── generate_bets.py         # bet_engine で買い目 recommendations 追記
│   ├── vb_refresh.py            # オッズ更新+買い目再計算（task scheduler 定時実行）
│   ├── bet_engine.py            # 買い目エンジン（preset/EV/配分）★中核
│   ├── preflight.py             # predict smoke test
│   └── cache_freshness.py       # MLキャッシュ鮮度チェック（Session 152）
├── バージョン管理
│   ├── model_loader.py          # registry 一元ローダー ★中核
│   ├── restore_live.py          # archive→live ファイル復元（registry 不変）
│   ├── set_active.py            # active_version 正式切替
│   └── switch_model.py          # 旧式切替（--list/--current が便利）
├── 検証・分析
│   ├── backtest_bet_engine.py   # backtest_cache × bet_engine プリセット比較
│   ├── backtest_vb.py           # VB gap別 ROI
│   ├── extend_backtest_cache.py # backtest_cache に日付追加
│   ├── analyze/                 # 検証ハーネス・調査スクリプト群
│   │   ├── validate_live_predictions.py  # ★E-009 採否判定ハーネス（ROI+ブートCI+月別+--option）
│   │   ├── check_calibration.py / check_wp_separation.py
│   │   ├── backtest_*.py        # walkforward / templates / cliff 等
│   │   ├── bankroll_core.py + simulate_bankroll_character.py  # キャラ別複利sim
│   │   └── analyze_slow_start_edge.py 等（E-004 採否証跡）
│   ├── analyze_*.py（直下）     # 旧分析スクリプト群（teppan/wide/sanrentan 等）
│   ├── simulate_*.py / win5_*.py
│   └── compute_p_bootstrap.py / ci_power_analysis.py
├── 較正
│   └── calibration/             # odds_conditioned.py + build_oc_calibrator.py（案X系・oc_calib_*.pkl）
├── 特徴量
│   └── features/                # §5 参照（19モジュール）
├── 買い方戦略（買い目層・表示層の純関数群）
│   └── strategies/              # bet_templates, harville, kelly, synthetic_odds, role_split,
│                                #   quality_gate(E-002), jockey_close(E-003), slow_start,
│                                #   reason_tags(E-005), characters, bettype_*, freebudget_* 等
├── 自動投票（3軸目: 馬券購入エージェント）
│   ├── ai_marks/                # AI印付与（markSet）・buy_marks・DAT書出し
│   ├── target_clicker/          # IPAT自動投票（launcher/runner/auto_vote/notify）
│   └── purchase_ledger/         # 購入記録（改ざん防止・税務）+ settle_ledger.py
├── 共通
│   └── utils/                   # backtest_cache ローダー（唯一の真実）, roi, filters, atomic_write 等
└── tests/                       # pytest（quality_meta/quality_gate/reason_tags/strategies 系 等）
```

> ⚠ 既知のテスト負債: `tests/test_bet_engine.py` 7件が Session 90 時点の仕様のまま赤（実体が先に変わった）。
> bet_engine 改修前に要修正（2026-06 時点）。

---

## 4. 日次の推論→買い目→投票フロー

```bash
# 0. MLキャッシュ再構築（keiba-data-prep スキル ②-4.5 — 予測直前に毎回。凍結インシデント再発防止）
python -m builders.build_race_index
python -m builders.build_horse_history

# 1. 日次フル実行（各コマンドが predictions.json を順次追記）
python -m ml.predict          --date YYYY-MM-DD   # polaris/enif 予測
python -m ml.predict_closing  --date YYYY-MM-DD   # eclipse closing_race_proba 追記
python -m ml.generate_bets    --date YYYY-MM-DD   # recommendations（買い目）追記
python -m ml.vb_refresh       --date YYYY-MM-DD   # オッズ更新+再計算（scripts/vb_refresh_auto.bat で定時）
```

- 出力: `data3/races/YYYY/MM/DD/predictions.json`（model_version, created_at, odds_source 等のメタ付き）
- predict.py は registry の active_version を解決してロード（`--model-version` で一時上書き可）
- 自動投票層: ai_marks → target_clicker（IPAT）→ purchase_ledger 記帳 → notify（投票通知）
- 買い目層の方針: **新規介入はROIを動かさない/逆効果が実証済み（E-003/E-004）。
  分析シグナルの居場所は ①ML特徴量 ②表示・運用（reason_tags / FreshnessHeader）**

---

## 5. 特徴量エンジニアリング

### 定義場所

- 各グループは `ml/features/*.py` に `compute_xxx_features()` + `XXX_FEATURE_COLS` で定義
- experiment.py が `FEATURE_COLS_ALL` に集約（line ~228）:
  BASE / PAST / TRAINER / JOCKEY / RUNNING_STYLE / ROTATION / PACE / TRAINING / KB_MARK /
  SPEED / COMMENT / SLOW_START / PEDIGREE / BABA / **JRDB(53)** / **TRACK_BIAS(11)** + odds系

### 3つの特徴量セット（experiment.py:205-250）

| セット | 用途 | 注意 |
|--------|------|------|
| `FEATURE_COLS_ALL` | 全特徴量（市場系含む） | 差分検出・分析用 |
| `MARKET_FEATURES` | **VALUEから除外する市場系** | odds/popularity/印/平滑化率/JRDB事前指数6種（pre_idm, sogo, info, jockey, training, stable）— VB差別化を守るため意図的除外 |
| `FEATURE_COLS_VALUE` | P/W/AR の学習に使う非市場特徴量 | `P_ONLY_FEATURES`（不利補正・CID系等）は P にだけ追加 |

### 新特徴量の追加

手順・チェックリストは `docs/ml-debug-procedure.md` §4 を参照。
**experiment.py（学習側）と predict.py（ライブ側）は別経路** — 両方に配線しないとライブで全欠損になる。
JRDB 未活用フィールドの候補は `docs/jrdb_data_inventory.md`（v2, 6段パイプライン表）を見る。

---

## 6. 実験・バックテスト・検証ハーネス

### experiment.py（本番実験CLI）

```bash
python -m ml.experiment --version 2.5 ^
    --train-years 2020-2025.06 --val-years 2025.07 --test-years 2025.08-2026.05 ^
    --sire-cutoff 2025-07-31 --no-set-active
```

- 特徴量を変更すると `--version` 必須（差分検出で exit 1）
- `--sire-cutoff` 必須（E-008: 血統PITリーク防止。未指定/test開始以降/ファイル欠落は exit 2。
  明示オプトアウトは `--allow-sire-leak`）
- **実行プリフライト**（キャッシュ鮮度確認）を省略しない — `ml-debug-procedure.md` §0。
  凍結キャッシュだと test 期間が黙って切り詰められる（v8.4 で実証: 宣言2026-05まで→実データ2026-03止まり）

### バックテスト資産

| ツール | データ源 | 用途 |
|--------|---------|------|
| `backtest_cache.json` | experiment の OOS 予測ダンプ（`utils/backtest_cache.py` が唯一の真実） | フル学習なしの戦略比較全般 |
| `ml.backtest_bet_engine` | backtest_cache | bet_engine プリセット別 ROI |
| `ml.analyze.validate_live_predictions` | **predictions.json（ライブ実物）** | **E-009 採否ハーネス**: 単勝T-5実行価格/複勝確定配当の ROI + ブートCI + `--monthly` walk-forward + `--option` 前後比較 |
| `ml.analyze.check_calibration` | predictions + 結果 | W/P較正（ECE・帯別乖離） |

### 検証の原則（確立済み）

1. オッズ条件ゲートは確定オッズ判定だと後知恵 — predictions（直前オッズ）ソースで再検証必須
2. 点推定でなく**ブートCI**で採否判定。月別 walk-forward で「幸運な窓」を排除
3. ライブ予測の異常診断は「ライブvs再推論の同一馬join」が最強（Session 151 の手法）
4. 較正が悪く見えたらまずデータ鮮度を疑う（較正補正は対症療法）

---

## 7. バージョン管理・ロールバック

詳細手順は `ml-debug-procedure.md` §6。要点:

- **registry** (`model_registry.json`) の `active_version` が live を決める。ファイル実体は
  `ml_dir` 直下（旧）+ `models/polaris/live/`（新）の両方に保存される
- **experiment.py は実行のたびに live ファイルを上書きする**。`--no-set-active` は registry だけ守る
  → 実験後は `python -m ml.restore_live polaris <ver>`（ファイル復元・registry不変・レース中も安全）
- 昇格は `python -m ml.set_active polaris <ver>` → `python -m ml.preflight` で smoke test
- 上書き前の自動退避: `versions/v{old}/`（旧構造・冪等）+ `models/polaris/archive/v{prev}/`（新構造）
- 分析JSONのバージョニングは `core/versioning.py`（`archive_before_save` / `archive_flat`）

---

## 8. Web表示チェーン（表示更新漏れ防止）

### モデルバージョンが表示される場所

| 画面 | ファイル | 表示内容 |
|------|---------|---------|
| モデル一覧 `/models` | `web/src/app/models/page.tsx` | registry の active_version + 版履歴（AUC/features） |
| 予測 `/predictions` | `app/predictions/page.tsx` + `predictions-content.tsx` | predictions.json の `model_version` / `created_at` / 版セレクタ（`/api/ml/prediction-versions`） |
| レース詳細 `/races-v2/...` | `app/races-v2/[date]/[track]/[id]/page.tsx` | ML予測列 + race_confidence |
| 管理 `/admin` | `lib/admin/commands.ts` + `api/admin/execute` | ML予測/VB再計算等の実行アクション（SSE） |

### predictions.json にフィールドを追加したときのチェックリスト

1. **Python側**: predict.py（または strategies/ の純関数）で entry に付与
2. **型定義**: `web/src/lib/data/predictions-reader.ts` の `PredictionEntry`（オプショナル `?` で後方互換）
3. **races-v2 経路**: `web/src/lib/data/ml-prediction-reader.ts` の `MlHorsePrediction` + `convertV4Entry()`
4. **表示**: `app/predictions/components/vb-table.tsx` / `components/race-v2/HorseEntryTable.tsx`
5. **フィルタ/買い目に関与する場合**: `predictions-content.tsx` の state / `lib/bet-engine.ts`
6. **確認**: `npx tsc --noEmit`・古い predictions.json でも壊れない・動的ルートの `force-dynamic`

参考実装（Session 154-155 の配線パターン）:
- 理由タグ: `ml/strategies/reason_tags.py` → `PredictionEntry.reason_tags` → `components/analysis/ReasonTagBadges.tsx`
- データ鮮度: 分析JSON `coverage.to_date` → `lib/freshness.ts` → `components/analysis/FreshnessHeader.tsx`
  （**created_at でなく coverage.to_date で凍結検知** — 生成時刻が新しくてもデータが古い事故を捕まえる）

---

## 9. データの場所

| パス | 内容 |
|------|------|
| `data3/ml/` | live モデル・registry・各種キャッシュ（horse_history_cache 等）・実験結果JSON |
| `data3/ml/models/{name}/live\|archive/` | 新構造のモデル実体 |
| `data3/ml/versions/` | 旧構造アーカイブ（実験スナップショット多数） |
| `data3/indexes/` | race_date_index + **jrdb_{sed,kyi,kaa,cyb,cha,kka,ukc,joa,srb}_index.json**（9種） |
| `data3/races/YYYY/MM/DD/` | race JSON + predictions.json |
| `data3/analysis/` | 分析JSON（quality_meta/coverage 付き）+ versions/ |
| `data3/jrdb/` | JRDB raw/zip/docs（仕様書48ファイル） |

---

## 10. 関連ドキュメント一覧

| ドキュメント | 内容 |
|------|------|
| `docs/ml_experiment_log.md` | 実験ログ（バージョン別・新しい順）★実験したら必ず記録 |
| `docs/ml-debug-procedure.md` | 実験・デバッグ手順書（プリフライト/Notebook/バージョン管理） |
| `docs/jrdb_data_inventory.md` | JRDB全データ棚卸し v2（6段パイプライン・未活用フィールド） |
| `docs/ml-experiments/` | 実験詳細レポート（v{ver}_{名前}.md） |
| `docs/ml-experiments/202606_analysis_reuse/` | 分析再利用プロジェクト（E-001〜E-010 全done・E001品質メタ仕様 v1.2） |
| `docs/DOMAIN_MODEL.md` / `docs/DATA_SPEC.md` | ドメインモデル / JRA-VANデータ仕様 |
| `keiba-cicd-core/.claude/CLAUDE.md` | プロジェクト共通規約（ID体系・EV定義・コーディングルール） |
