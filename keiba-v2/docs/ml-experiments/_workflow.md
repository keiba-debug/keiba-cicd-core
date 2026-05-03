# ML実験の標準ワークフロー (Session 119)

`jrdb_pace_match` 死特徴量の見落とし、Optuna list 固定による新特徴量の暗黙除外、
旧モデルの上書き消失の事故をきっかけに整備した運用手順。

---

## ① 学習前 (preflight)

```bash
python -m ml.preflight                 # 最新日のレースで smoke test
python -m ml.preflight --no-smoke      # 高速チェックのみ (試走なし)
```

### チェック内容

| Step | 内容 | 警告対応 |
|---|---|---|
| 1 | `FEATURE_COLS_ALL` vs active モデルの diff | 大きく差分があれば feature 追加・削除を意図確認 |
| 2 | Optuna 済み feature list との照合 | **Optuna list 外の新特徴量は P_ONLY_FEATURES に追加するか `--use-optuna` を外す** |
| 3 | 新特徴量の値分布 (NaN率/unique/Top5) を直近1日の試走で取得 | NaN率>90% / unique<=1 / 1値に70%張り付き → **死特徴量化リスク** |

### よくある対応

- **新規特徴量がOptuna list外** → `experiment.py` の `P_ONLY_FEATURES` に追加するか、学習時に `--use-optuna` を外す。後者だと長時間化注意。
- **値分布が偏ってる** → `jrdb_features.py` などの計算ロジックを見直し、修正後 preflight 再実行。

---

## ② 学習

```bash
python -m ml.experiment \
  --train-years 2020-2025.03 \
  --val-years 2025.04 \
  --test-years 2025.05-2026.03 \
  --time-decay 2.0 \
  --use-optuna \
  --version 2.2-pace-fix
```

実行時にコンソールへ出る `[Archive] live(vXXX) → ...` を確認。
**experiment.py は学習結果を `live/` に書く前に、既存 live を `archive/v{prev_version}/` に自動退避する** (Session 119 で追加)。

### バックグラウンド実行する場合

```bash
python -m ml.experiment ... > /c/tmp/polaris_X.X.log 2>&1 &
```

---

## ③ 学習後 (比較レポート)

```bash
python -m ml.compare_models --base 2.1b --new 2.2-pace-fix --top 20
python -m ml.compare_models --base 2.1b --new 2.2 --watch jrdb_pace_match jrdb_pace_mismatch_avg
```

出力:
- 全体 metrics (P/W AUC, AR MAE, Brier)
- 特徴量数の差
- 追加/削除された特徴量
- importance Top N の差分 (← OUT, ← NEW のマーク)
- `--watch` 指定特徴量の rank/gain 並列表示

---

## ④ 採否判断

### 採用基準の目安

| 観点 | 良し悪し |
|---|---|
| AUC 改善 | P AUC +0.005 以上、W AUC 維持 |
| プリセット ROI | tansho_ippon / intersection の純益が向上 (CI 95% で重複あり) |
| 重要度 | 期待した新特徴量が Top50 入り or 既存死特徴量が蘇生 |

### 不採用なら速攻ロールバック

```bash
python -m ml.set_active polaris 2.1b
```

archive から `v2.1b/` を `live/` にコピー、現 live は archive にバックアップ後に上書きされる。

---

## ⑤ よくある事故と対策

| 事故 | 原因 | 対策 |
|---|---|---|
| 新特徴量の効果が出ない | Optuna list 固定で除外された | preflight Step 2 で警告 → P_ONLY追加 or `--no-optuna` |
| 死特徴量を放置 | importance を見ていない | 月1で `compare_models --base live --new live` で死特徴量レポート (将来) |
| ロールバックできない | live が上書きされた、archive 不在 | experiment.py 自動退避 (✅修正済) + `set_active.py` |
| AUC変化が乱数か新特徴量効果か区別できない | seed/optuna/time-decay 条件が混在 | **base と new で変える条件は1つだけ**にする |

---

## 関連ファイル

| ファイル | 役割 |
|---|---|
| `ml/preflight.py` | 学習前チェック |
| `ml/compare_models.py` | 学習後比較 |
| `ml/set_active.py` | バージョン切替 |
| `ml/experiment.py` | 学習本体 (line 3326〜 で archive自動退避) |
| `data3/ml/models/polaris/live/` | 現役モデル |
| `data3/ml/models/polaris/archive/v{ver}/` | 過去モデル (ロールバック元) |
