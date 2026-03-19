# ML実験ログ

> 各バージョンの特徴量エンジニアリング・ハイパラ調整の記録。
> 何が効いて何が効かなかったかを後から参照する。

---

## 障害v2.5b: 着差特徴量 (2026-03-19, Session 109)

### 背景
着順だけでは勝ち馬との実力差が見えない。horse_history_cacheにtime_behind_winner(秒)を追加し、
障害レースの着差ベース特徴量4つを追加。

### 新特徴量
- `obs_avg_tbw_last3`: 障害直近3走の平均time_behind_winner
- `obs_best_tbw_last5`: 障害直近5走のベストtbw
- `obs_tbw_trend`: 直近3走のtbw改善トレンド
- `obs_weighted_tbw_last3`: 指数減衰重み付きtbw(半減期2走)

### 結果 (v2.5→v2.5b)
| 指標 | v2.5 | v2.5b | 差分 |
|------|------|-------|------|
| P AUC | 0.7660 | 0.7657 | ±0 |
| W AUC | 0.7642 | 0.7697 | **+0.006** |
| W Top1勝率 | 38.8% | **45.0%** | **+6.2pt** |

着差はWモデル（勝てるか判定）に特に効く。obs_weighted_tbw_last3がP#3/W#4。

### インフラ変更
- build_horse_history.py: margin + time_behind_winner をcacheに追加（537K entries, 100% valid）

→ 詳細: `docs/ml-experiments/obstacle_v2.5_experience_curve.md`

---

## 障害v2.5: 経験曲線特徴量 (2026-03-19, Session 109)

### 背景
障害レースの経験曲線を分析し、初障害→2戦目で60.5%の馬が改善することを確認。
直近走を重視する指数減衰重み付き過去走特徴量を3つ追加。

### 新特徴量
- `obs_weighted_finish_last3`: 半減期2走の指数減衰重み付き障害着順比率
- `obs_improvement_rate`: 初障害→2戦目の着順比率改善幅
- `obs_debut_discount`: 初障害除外時の着順改善度

### 結果 (v2.4→v2.5)
| 指標 | v2.4 | v2.5 | 差分 |
|------|------|------|------|
| P AUC | 0.7608 | 0.7660 | +0.005 |
| W AUC | 0.7588 | 0.7642 | +0.005 |
| W Top1勝率 | 40.0% | 38.8% | -1.2pt |

**obs_weighted_finish_last3がP/W両方で重要度1位**。均等平均と共存してtier別使い分け。

### predict.py修正
障害v2.2以降の特徴量が推論パスに反映されていなかった問題も併せて修正。

→ 詳細: `docs/ml-experiments/obstacle_v2.5_experience_curve.md`

---

## v5.5: Bootstrap信頼区間 + 特徴量Pruning (2026-02-22, Session 44)

### 背景
- バックテストROIの信頼性を定量化するBootstrap CIを実装
- 低importance特徴量のpruningによるモデル軽量化を検証
- 「信頼性（悩み2）を解決せずに他の改善に取り組んでも効果判定不能」という戦略的判断

### 実装
- `calc_vb_bootstrap_ci()`: レース単位リサンプリング（1000回, 95% CI）
- `--prune-bottom N`: importance下位N%を前回結果JSONから自動除外
- bet_engineバックテストにもBootstrap CI追加

### ベースライン結果（v5.4.1, 114/92特徴量）
| Model | AUC | ECE | Iter |
|-------|-----|-----|------|
| A (好走 市場) | 0.8229 | 0.0046 | 247 |
| B (好走 独自) | 0.7835 | 0.0054 | 592 |
| W (勝利 市場) | 0.8371 | 0.1339 | 131 |
| WV (勝利 独自) | 0.7882 | 0.1230 | 350 |
| Reg B (チャクラ) | MAE=0.701 | - | 742 |

| Gap | Place ROI [95%CI] | Win ROI [95%CI] |
|-----|-------------------|-----------------|
| >=2 | 72.4% [68.2-76.5] | 84.4% [74.2-96.8] |
| >=3 | 73.7% [68.0-79.5] | 85.8% [69.5-103.9] |
| >=4 | 77.2% [68.4-85.6] | 88.6% [66.0-116.0] |
| >=5 | 81.8% [69.5-94.5] | **107.8% [71.6-147.4]** |

bet_engine: win_only 119.3% (366bet), conservative 108.0%, standard 99.0%

### Pruning 20%結果（92/74特徴量）
- WV AUC: 0.7882→0.7869 (**-0.0013**)
- Win VB gap>=5: 107.8%→**80.7%** (-27pp) — 大幅悪化
- bet_engine win_only: **110.9% [60.2-170.4]** — CI幅110pp以上

### 最重要の発見
- **win_only 95% CI = [60.2% - 170.4%]**: 366件では統計的判断が困難
- **バージョン間5-10ppの差は統計的にほぼ無意味**
- Pruning 20%はやりすぎ（コメントNLP+降格ローテを一括削除）
- dead features（importance=0）のみ削除がより安全

### 次のステップ
- dead features pruning（importance=0のみ除外）
- bet数増加でCI縮小（gap>=4緩和、margin閾値調整）
- 時系列Cross-validationでROI安定性確認

> 詳細レポート: `docs/ml-experiments/v5.5_bootstrap_ci_pruning.md`

---

## v5.4.1: IsotonicRegression横展 + Reg B統合 (2026-02-21, Session 39-41)

### 背景
- Win modelのECE=0.13がKelly fractionに悪影響
- 着差回帰モデル（Reg B）のmarginフィルターでbet精度向上

### 実装
- IsotonicRegression: valセットでfit → test/live適用。Win ECE 0.13→0.003 (-97%)
- bet_engine: Win=rule-based(gap+margin), Place=EV+Kelly(ECE良好)
- margin最適化: gap>=5でmargin<=1.2が最適（119.9%）

### 結果
- **win_only ROI 119.9%** (366bet, +7,060円)
- margin 1.2が最適: 1.0は厳しすぎ(107.7%), 1.5は緩すぎ(113.0%)
- Win-only > Win+Place: Place ROI<100%が足を引く

---

## 着差回帰実験 (2026-02-21, Session 40)

### 背景
- 二値分類(is_top3, is_win)ではなく、着差(time_behind_winner)を直接予測する回帰モデル
- LGBMRegressor + Huber loss (delta=2.0) + 5.0sキャップ
- ターゲット: race JSONのtimeフィールドから計算 (100%カバレッジ)

### 実装
- `ml/features/margin_target.py`: 共有ターゲット計算ユーティリティ
- `ml/experiment_regression.py`: 回帰 vs 二値分類 比較実験

### 回帰モデル精度
| Model | MAE | RMSE | R2 | Corr | Iter |
|-------|-----|------|-----|------|------|
| Reg A (All) | 0.668s | 0.907s | 0.414 | 0.643 | 815 |
| Reg B (Value) | 0.700s | 0.943s | 0.365 | 0.605 | 742 |

### NDCG比較（ランキング品質）
- Cls A > Reg A (0.5808 vs 0.5771 @1), Cls B > Reg B (0.5349 vs 0.5337 @1)
- 差は僅差、分類がわずかに優勢

### VB ROI比較（最重要指標）
| Gap | Cls B ROI | Reg B ROI | 差分 |
|-----|-----------|-----------|------|
| >=3 | 73.7% | 78.3% | **+4.6%** |
| >=4 | 77.0% | 84.6% | **+7.6%** |
| >=5 | 81.6% | 91.4% | **+9.8%** |

### 回帰→確率変換 (IsotonicRegression)
- AUCは分類が優位: Cls A=0.823 vs Reg A→iso=0.770 (is_top3)
- ECEは回帰→isoが良好（0.002-0.004）

### Top1 ROI
- **Reg B Win ROI 88.6%** > Cls B 85.0%（+3.6pp）
- Place ROI は互角（81.3% vs 80.3%）

### 特徴量重要度
- Reg A Top3: odds(676K), track_type(129K), distance(86K)
- Reg B Top3: track_type_top3_rate(213K), track_type(112K), distance(89K)
- 分類と比べてtrack_type, distanceが上位に（着差がコース特性に強く依存）

### 結論
- **回帰はVB ROIで分類を全Gap帯で改善**（着差スケールが市場乖離検出に有効）
- **ランキング/AUCは分類が優位**（確率推定の直接的な精度は分類が上）
- **次のステップ**: 分類ランキング + 回帰VBフィルターの併用、または着差特徴量として分類モデルに統合

---

## v5.4: ベイズ平滑化レート + career_stage (2026-02-21, Session 36)

### 背景
- **サマーゲール事件**: 東京2R ①サマーゲール（新馬戦快勝、キング騎手、AI指数264.4A）がV順=16（最下位）、Gap=-14で危険な人気馬判定
- **SHAP分析で原因特定**: `win_rate_all=1.0` → SHAP **-0.1856**（Model Bで最大のマイナス寄与）
- LightGBMが「勝率100%」を「1戦だけの少数サンプル」として大きくペナルティ
- `debug_features.py` 新規作成: `pred_contrib=True` でSHAP値を抽出する診断ツール

### 新特徴量（6個）
| 特徴量 | 説明 | 分類 |
|--------|------|------|
| `win_rate_smoothed` | ベイズ平滑化勝率 (α=1.0, β=12.0, prior≈7.7%) | **MARKET** |
| `top3_rate_smoothed` | ベイズ平滑化複勝率 (α=2.5, β=7.5, prior=25%) | **MARKET** |
| `venue_top3_rate_smoothed` | 場所別平滑化複勝率 | **MARKET** |
| `track_type_top3_rate_smoothed` | 馬場別平滑化複勝率 | **MARKET** |
| `distance_fitness_smoothed` | 距離適性平滑化 | **MARKET** |
| `career_stage` | キャリア段階 (0=debut,1=2戦,2=3-5,3=6-10,4=11+) | VALUE |

### MARKET分類の根拠（v5.4bで確認済み）
- **v5.4（全VALUE）**: Model B AUC 0.7858(+0.0018) だが Place VB gap≥5 ROI **121.5%**(-15.8pp)
- smoothed rateがModel Bの精度を上げすぎ → A-B乖離が縮小 → VB効果が消滅
- **v5.4b（smoothed=MARKET）**: Model B AUC 0.7841(≈v5.3) で Place VB gap≥5 ROI **148.2%**(+10.9pp)
- career_stageのみVALUEに残す = 「何戦目か」の構造情報は市場情報ではない

### 結果比較 (v5.4b = 採用版)
| 指標 | v5.3 | v5.4 | Delta |
|------|------|------|-------|
| Model A AUC | 0.8225 | **0.8230** | +0.0005 |
| Model B AUC | 0.7840 | 0.7841 | +0.0001 |
| Model W AUC | 0.8375 | 0.8374 | -0.0001 |
| Model WV AUC | 0.7876 | **0.7888** | **+0.0012** |
| Model B ECE | 0.0043 | 0.0053 | +0.0010 |
| Features A/B | 108/91 | 114/92 | +6/+1 |

### VB ROI比較
| Gap | v5.3 Place | v5.4 Place | v5.3 Win | v5.4 Win |
|-----|-----------|-----------|---------|---------|
| ≥2 | 102.4% | 105.8% (+3.4) | 91.5% | 88.5% |
| ≥3 | 116.1% | 118.3% (+2.2) | 93.3% | 90.7% |
| ≥4 | 124.2% | 127.4% (+3.2) | 100.2% | 89.1% |
| ≥5 | 137.3% | **148.2%** (+10.9) | 112.0% | 106.0% |

### 主な学び
- **ベイズ平滑化 = MARKET**: Model Aの精度向上に使いつつ、Model Bには入れない → A-B乖離拡大 → VB ROI最大化
- **career_stage = VALUE**: 少数走馬の構造情報。Model Bに「2戦目」「デビュー」の文脈を与える
- **Place VB gap≥5 ROI 148.2%は過去最高**: v5.0の147.7%を超えた
- **Win VB ROIは微減**: smoothed rateがModel Wに入ることで単勝側は微妙に悪化
- **SHAP診断ツールが有用**: `python -m ml.debug_features --race-id XXX --umaban N` で即座に特徴量貢献分析可能

### 変更ファイル
| ファイル | 変更内容 |
|---------|---------|
| ml/features/past_features.py | bayesian_rate() + 5 smoothed rates + career_stage |
| ml/experiment.py | PAST_FEATURES +6, MARKET_FEATURES +5 |
| ml/debug_features.py | 新規: SHAP診断ツール |

---

## v5.3: コメントNLP特徴量 (2026-02-21, Session 35)

### 新特徴量（10個）
- `comment_stable_condition` / `comment_stable_confidence` — 厩舎談話のcondition/confidence
- `comment_stable_mark` (MARKET) — ◎=4, ○=3, △=1
- `comment_stable_excuse_flag` — 言い訳キーワード有無
- `comment_interview_condition` / `comment_interview_excuse_score` — 前走インタビュー
- `comment_memo_condition` / `comment_memo_trouble_score` — 次走メモ
- `comment_has_stable` / `comment_has_interview` — データ有無フラグ

### 辞書設計
- Python dict、部分文字列マッチ + 否定5文字ウィンドウ
- condition辞書: +3〜-3 (28エントリ), confidence辞書: +3〜-3 (19エントリ)
- カバレッジ: condition nonzero 32.4%, confidence nonzero 25.3%

### 結果
| Model | AUC | Brier | ECE | Features | Iter |
|-------|-----|-------|-----|----------|------|
| A (top3, all) | 0.8225 | 0.1281 | 0.0038 | 108 | 337 |
| B (top3, value) | 0.7840 | 0.1383 | 0.0043 | 91 | 487 |
| W (win, all) | 0.8375 | 0.0844 | 0.1278 | 108 | 78 |
| WV (win, value) | 0.7876 | 0.0887 | 0.1306 | 91 | 258 |

- **Place VB gap≥5 ROI: 137.3%** (v5.2b: 132.4%, +4.9pp)
- Win VB gap≥5: 112.0% (v5.2b: 120.4%, -8.4pp)
- Feature importance: Model B #72-91/91 (低いがVB ROIに寄与)

### v5.3b（辞書拡充版）— 不採用
- 辞書エントリ大幅追加（condition 44→52, confidence 19→31, etc.）
- カバレッジ: condition 48.3%, either 66.8%
- Place VB gap≥5: 136.1% (v5.3より-1.2pp)
- **教訓**: 曖昧な語の追加はノイズになり、VB ROI低下。精度の高い少数語が最適

---

## インフラ: モデルバージョニング (2026-02-20, Session 34)

### 概要
- **predict.py**: `load_model_and_meta(model_version)` でアーカイブからモデルロード可能に
- **predict.py CLI**: `--model-version 5.0` / `--list-versions` フラグ追加
- **experiment.py**: `--version 5.3` でバージョン文字列をCLI指定可能に（ハードコード廃止）
- **出力JSON**: `model_version`, `model_source`, `model_features_all/value`, `model_has_win` 追加
- **model_meta.json**: `"5.1"` → `"5.2b"` に修正（実態と一致させた）

### 利用可能モデル（5世代）
| Version | Features A/V | Win | 作成日 |
|---------|-------------|-----|--------|
| v5.2b (live) | 98/82 | Yes | 2/20 |
| v5.1 | 87/74 | Yes | 2/20 |
| v5.0 | 82/69 | Yes | 2/15 |
| v4.0 | 75/69 | No | 2/14 |
| v3.5 | 65/61 | No | 2/14 |

### 互換性メモ
- LightGBMモデルが内部に特徴量名リストを保持 → 古いモデルは古いmetaの特徴量だけ使う
- 特徴量**追加**のみなら後方互換OK。計算ロジック変更時は新名前を使う規約
- v3.5/v4.0はWinモデルなし → 後方互換でPlace予測のみ実行

---

## v5.2b (2026-02-20) — 降格ローテ + レースレベル特徴量

### 作業分類
- **特徴量エンジニアリング**: 降格ローテ系11個追加（MARKET 3個 + VALUE 8個）
- **データ基盤**: race_level_index.json新規、horse_history_cache拡張(grade/venue_name/is_handicap/is_female_only)
- **注意**: v5.2(ロールバック推奨)の上ではなくv5.1ベースで実装

### 新特徴量
| 特徴量 | 分類 | Model A | Model B |
|--------|------|---------|---------|
| `prev_grade_level` | MARKET | 1,174 (#42/98) | — |
| `venue_rank_diff` | MARKET | 947 (#48/98) | — |
| `grade_level_diff` | MARKET | 671 (#63/98) | — |
| `koukaku_rote_count` | VALUE | 210 (#83/98) | 1,335 (#69/82) |
| `is_koukaku_venue` | VALUE | 137 (#86/98) | 761 (#73/82) |
| `is_koukaku_female` | VALUE | 230 (#82/98) | 670 (#74/82) |
| `is_koukaku_distance` | VALUE | 18 (#95/98) | 356 (#75/82) |
| `is_koukaku_season` | VALUE | 44 (#91/98) | 292 (#76/82) |
| `is_koukaku_turf_to_dirt` | VALUE | 64 (#90/98) | 279 (#77/82) |
| `is_koukaku_age` | VALUE | 0 (#96/98) | 0 (#80/82) |
| `is_koukaku_handicap` | VALUE | 0 (#97/98) | 0 (#81/82) |

### 結果比較 (vs v5.1)
| 指標 | v5.1 | v5.2b | 変化 |
|------|------|-------|------|
| Model A AUC | 0.8241 | 0.8240 | -0.0001 (=) |
| Model B AUC | 0.7833 | **0.7843** | **+0.0010** |
| Model W AUC | 0.8383 | 0.8378 | -0.0005 (=) |
| Model WV AUC | 0.7860 | **0.7873** | **+0.0013** |
| 特徴量数 A/B | 87/74 | 98/82 | +11/+8 |

### VB ROI比較
| Gap | v5.1 Place | v5.2b Place | v5.1 Win(VB内) | v5.2b Win(VB内) |
|-----|-----------|-------------|---------------|-----------------|
| ≥2 | 105.1% | 101.9% (-3.2) | 93.3% | 91.7% (-1.6) |
| ≥3 | 119.4% | 114.5% (-4.9) | 96.8% | 96.0% (-0.8) |
| ≥4 | 131.4% | 127.0% (-4.4) | 113.0% | **107.0%** (-6.0) |
| ≥5 | 142.8% | 132.4% (-10.4) | 134.9% | **120.4%** (-14.5) |

### 分析
- **Value系モデル(B/WV)のAUCが改善**: 降格ローテはmarketに見えにくい信号→VB哲学と合致
- **VB ROIは低下**: gap≥5で-10〜-15pt。ただしv5.1とテスト期間が同一のため、特徴量追加による影響
- **Dead features**: is_koukaku_age(常時0=TODO), is_koukaku_handicap(30レースのみで0)
- **MARKET特徴量**: prev_grade_level(#42)はそこそこ有用、grade_level_diff(#63)は低重要度
- **VALUE特徴量の重要度は全体的に低い**: Model Bでもkoukaku_rote_count(#69/82)が最高
- **判断**: AUC改善は確認できるがROI低下があるため、降格ローテ特徴量の取捨選択が必要。koukaku_rote_count + is_koukaku_venue + is_koukaku_female の上位3つのみ残すことを検討

### 変更ファイル
| ファイル | 変更内容 |
|---------|---------|
| core/constants.py | GRADE_LEVEL, VENUE_RANK, VENUE_RANK_ORDER |
| core/jravan/sr_parser.py | is_handicap/is_female_only + JyuryoCDデッドコード削除 |
| core/models/race.py | is_handicap/is_female_only |
| builders/build_race_master.py | 新フィールド出力 + entries-based is_female_only |
| builders/build_horse_history.py | grade/venue_name/is_handicap/is_female_only |
| analysis/rating_standards.py | race_level_index.json + venue_stats |
| ml/features/rotation_features.py | 降格ローテ11特徴量 |
| ml/experiment.py | ROTATION_FEATURES +11, MARKET_FEATURES +3 |
| ml/predict.py | 降格ローテ情報出力 |
| web/predictions-content.tsx | 降格ローテバッジ |
| web/predictions-reader.ts | koukaku型追加 |
| web/analysis/rating/page.tsx | 会場別統計テーブル |

---

## v5.2 (2026-02-20) — 余力ラップ(ch7) + race_trend カテゴリ特徴量

### 作業分類
- **特徴量エンジニアリング**: 余力ラップ系5個 + race_trendカテゴリ系3個 = 8個追加
- **データ基盤**: RPCI方向修正済みのrace_*.jsonを使用（v5.1と同一）

### 新特徴量
| 特徴量 | 狙い | Model A | Model B |
|--------|------|---------|---------|
| `race_last1f_avg_last3` | 直近3走のレースラスト1F平均 | 2,476 | **6,828 (#16)** |
| `race_decel_l1f_avg_last3` | ラスト1F減速度3走平均 | 2,325 | **6,727 (#17)** |
| `prev_race_last1f` | 前走のレースラスト1F | 1,724 | **5,563 (#21)** |
| `yoriki_score_last5` | 余力基準クリア数(5走,3着内限定) | ~1,500 | 3,040 (#36) |
| `trend_switch_count_last5` | 5走のtrend変化回数 | ~1,100 | 2,089 (#43) |
| `dominant_trend_v2_enc` | 最頻trend_v2(整数enc) | ~1,000 | 1,284 (#58) |
| `prev_race_trend_v2_enc` | 前走trend_v2(整数enc) | ~1,000 | 1,229 (#59) |
| `fast_finish_top3_rate` | 速い上がりレースでの好走率 | ~800 | 917 (#64) |

### 結果比較
| 指標 | v5.1 | v5.2 | 変化 |
|------|------|------|------|
| Model A AUC | 0.8241 | 0.8239 | -0.0002 (=) |
| Model V AUC | 0.7833 | 0.7833 | = |
| Model A ECE | 0.0033 | 0.0042 | +0.0009 (worse) |
| Model V ECE | 0.0044 | 0.0046 | +0.0002 (=) |
| Model W AUC | 0.8383 | 0.8382 | -0.0001 (=) |
| Model WV AUC | 0.7860 | 0.7854 | -0.0006 |
| Model W ECE | 0.1278 | 0.1324 | +0.0046 (worse) |
| Model WV ECE | 0.1315 | **0.1228** | **-0.0087 (better)** |
| 特徴量数 A/B | 87/74 | 95/82 | +8/+8 |

### VB ROI比較
| Gap | v5.1 Place | v5.2 Place | v5.1 Win(VB内) | v5.2 Win(VB内) |
|-----|-----------|-----------|---------------|---------------|
| ≥2 | 105.1% | 101.7% (-3.4) | 93.3% | 91.1% (-2.2) |
| ≥3 | 119.4% | 111.5% (-7.9) | 96.8% | 93.2% (-3.6) |
| ≥4 | 131.4% | 123.2% (-8.2) | 113.0% | 100.1% (-12.9) |
| ≥5 | 142.8% | 129.4% (-13.4) | 134.9% | 123.1% (-11.8) |

### 分析
- **AUCはほぼ横ばい**: 新特徴量は予測の順序精度に大きな影響を与えていない
- **VB ROIが全gap帯で低下**: 複勝-3〜-13pt、単勝(VB内)-2〜-13pt
- **ECEが3/4モデルで悪化**: Model A ECE 0.0033→0.0042。キャリブレーション精度低下
- **Model WV ECEのみ改善**: 0.1315→0.1228 (-0.0087)
- **余力ラップ系3特徴量はModel B Top25**: race_last1f(16位)、decel(17位)、prev_last1f(21位)
- **race_trendカテゴリ系は低重要度**: dominant/prev_trend_v2_enc は58-59位

### 判断: **v5.1にロールバック推奨**
- 新特徴量はシグナルを持つ（特に余力ラップ上位3つ）が、8特徴量まとめて追加したことでModel Vのノイズが増加した可能性
- ROI低下幅がサンプリングノイズ(-4〜5pt)を超えている（-13ptはシグナル的）
- **次のアプローチ**: 上位3特徴量のみで再実験、または低重要度の5つを除外して再検証

### 変更ファイル
| ファイル | 変更内容 |
|---------|---------|
| ml/features/pace_features.py | 余力ラップ5 + race_trendカテゴリ3 = 8特徴量追加 |
| ml/experiment.py | PACE_FEATURES +8、version 5.2 |

---

## v5.1 (2026-02-20) — 33ラップ + レース傾向適性特徴量

### 作業分類
- **特徴量エンジニアリング**: 33ラップ系2個 + レース傾向適性系3個 = 5個追加
- **分類基盤**: `race_classifier.py`新規（7分類v2 + 33ラップ算出 + 3シグナル統合）
- **データ基盤**: 全20,415レースJSON再ビルド + race_type_standards v5.0

### 新特徴量
| 特徴量 | 狙い | Model A | Model B | Model WV |
|--------|------|---------|---------|----------|
| `prev_race_lap33` | 前走の瞬発/持続度合い | 3,482 (#10) | **9,830** | **22,270** |
| `avg_lap33_last3` | 直近3走の平均33ラップ | 3,261 (#11) | **8,205** | **21,026** |
| `trend_versatility` | 傾向別top3率の標準偏差 | 1,719 | 5,756 | 12,643 |
| `worst_trend_top3_rate` | 最も苦手な傾向でのtop3率 | 1,113 | 3,321 | 8,312 |
| `best_trend_top3_rate` | 最も得意な傾向でのtop3率 | 1,032 | 3,481 | 7,013 |

### 結果比較
| 指標 | v5.0 | v5.1 | 変化 |
|------|------|------|------|
| Model A AUC | 0.8243 | 0.8241 | -0.0002 (=) |
| Model B AUC | 0.7837 | 0.7833 | -0.0004 (=) |
| Model A ECE | 0.0040 | **0.0033** | **-0.0007 (better)** |
| Model B ECE | 0.0056 | **0.0044** | **-0.0012 (better)** |
| Model W AUC | 0.8376 | **0.8383** | **+0.0007** |
| Model WV AUC | 0.7851 | **0.7860** | **+0.0009** |
| Model W ECE | 0.1346 | **0.1278** | **-0.0068 (better)** |
| Model WV ECE | 0.1334 | **0.1315** | **-0.0019 (better)** |
| 特徴量数 A/B | 82/69 | 87/74 | +5/+5 |

### VB ROI比較
| Gap | v5.0 Place | v5.1 Place | v5.0 Win(VB内) | v5.1 Win(VB内) |
|-----|-----------|-----------|---------------|---------------|
| ≥2 | 107.8% | 105.1% (-2.7) | 91.2% | **93.3%** (+2.1) |
| ≥3 | 121.1% | 119.4% (-1.7) | 92.1% | **96.8%** (+4.7) |
| ≥4 | 128.8% | **131.4%** (+2.6) | 100.1% | **113.0%** (+12.9) |
| ≥5 | 147.7% | 142.8% (-4.9) | 122.6% | **134.9%** (+12.3) |

### MARKET_FEATURES判定
- **結論: 5特徴量全てModel A+B両方に残す**
- 理由: Model WVでの高重要度（prev_race_lap33=22,270）、ECE全モデル改善、Place VB単勝ROI大幅改善
- 33ラップはコース構造由来の物理特性 → 市場が完全に織り込んでいるとは考えにくい

### 主な学び
- **ECE改善が最大の成果**: 全4モデルでキャリブレーション向上。33ラップが確率推定の精度を底上げ
- **Win モデルに特に有効**: W AUC +0.0007、WV AUC +0.0009。勝ち馬予測に33ラップの物理情報が効く
- **Model WVでの重要度が突出**: prev_race_lap33=22,270、avg_lap33_last3=21,026。市場除外モデルで最も輝く特徴量
- **Place VB 単勝ROI大幅改善**: gap≥4で+12.9pt、gap≥5で+12.3pt → VB候補内の勝ち馬特定精度向上
- **Place VB 複勝ROIは微減**: gap≥5で-4.9pt。サンプルサイズ(564件)を考慮すると統計的ノイズの可能性
- **AUC横ばい、ECE改善**: 予測の順序精度は変わらないが、確率の絶対値がより正確に

### 変更ファイル
| ファイル | 変更内容 |
|---------|---------|
| analysis/race_classifier.py | 新規: 7分類v2 + compute_lap33() + classify_race_v2() |
| core/models/race.py | RacePace: lap33, race_trend_v2, trend_detail追加 |
| core/jravan/sr_parser.py | to_pace_dict()でlap33算出 |
| builders/build_race_master.py | v2分類統合、data_version 4.1 |
| analysis/race_type_standards.py | course_lap33_average + trend_v2_distribution追加、重複削除 |
| ml/features/pace_features.py | 5新特徴量（33ラップ2 + 適性3） |
| ml/experiment.py | pace_index拡張、PACE_FEATURES +5、version 5.1 |
| web/src/types/race-data.ts | TrendDetail型、LapsData拡張 |
| web/src/lib/data/rpci-utils.ts | v2型定義 + getLap33Interpretation() |
| web/src/lib/data/v4-race-adapter.ts | v2フィールド転送 |
| web/src/components/race-v2/RaceResultSection.tsx | RaceTrendCard追加 |
| web/src/components/horse-v2/HorsePastRacesTable.tsx | v2バッジ対応 |
| web/src/lib/data/race-trend-reader.ts | v2優先lookupに書き換え |

---

## v5.0 (2026-02-15) — Win/Placeデュアルモデル + 正確なEV計算

### 作業分類
- **モデルアーキテクチャ**: 4モデル体系（Place 2 + Win 2）
- **EV計算修正**: P(top3)×単勝オッズ → P(win)×単勝オッズ + P(top3)×複勝オッズ
- **データ基盤**: DB複勝オッズ取得（batch_get_place_odds）

### 重大発見
- **旧EV計算は理論的に不正確だった**: `pred_proba_v × winOdds` = P(top3) × 単勝オッズ
- 既存の Model A/B は両方とも `is_top3`（3着以内）が目的変数
- `is_win`（1着）列はデータセットに存在するがROI分析にのみ使用されていた

### 新モデル体系
| モデル | 目的変数 | 特徴量 | 用途 |
|--------|---------|--------|------|
| Model A | is_top3 | 全82 | 複勝精度 |
| Model V | is_top3 | 69(市場除外) | 複勝バリュー |
| **Model W** | **is_win** | 全82 | **単勝精度** |
| **Model WV** | **is_win** | 69(市場除外) | **単勝バリュー** |

### ハイパーパラメータ
- `scale_pos_weight=5.0` for Win models（is_win ~6.5% 不均衡対応）
- 完全バランスは1/0.065≈15だが、LightGBM AUC最適化は不均衡に強いため控えめに5.0

### 結果
| モデル | AUC | Brier | ECE | Iter |
|--------|-----|-------|-----|------|
| Model A (top3, all) | 0.8243 | 0.1276 | 0.004 | 272 |
| Model V (top3, value) | 0.7837 | 0.1384 | 0.0056 | 537 |
| Model W (win, all) | **0.8376** | 0.0894 | 0.1346 | 140 |
| Model WV (win, value) | **0.7851** | 0.0898 | 0.1334 | 250 |

Place VB ROI: gap>=5 → 147.7%
Win VB ROI: gap>=5 → 92.3%（100%未満 — 単勝はVB gap単独では不十分）

### 主な学び
- **Win AUC > Place AUC**: 1着は明確なシグナルで識別しやすい（0.8376 vs 0.8243）
- **Win ECEが高い（0.13）**: scale_pos_weightがキャリブレーションを崩す。predict.pyのレース内正規化で実用上は問題ない
- **Win VB ROIは低い**: 単勝はVB gap戦略だけでは利益が出ない。単勝EVフィルタなど複合条件が必要
- **複勝EVが新たに計算可能に**: DB複勝オッズとP(top3)で正確な期待値が出せるようになった

### 変更ファイル
| ファイル | 変更内容 |
|---------|---------|
| ml/experiment.py | Win モデル2つ追加、VB分析拡張、meta version 5.0 |
| core/odds_db.py | batch_get_place_odds() 追加 |
| ml/predict.py | 4モデル予測、複勝オッズ、新フィールド出力 |
| web/.../predictions-reader.ts | 新フィールド型定義追加 |
| web/.../predictions-content.tsx | EV表示分離（単EV/複EV/頭%） |

---

## v3.4 (2026-02-13) — DB事前オッズ統合 + date_indexバグ修正

### 作業分類
- **データ基盤**: mykeibadb v3.61 時系列オッズ統合（MySQL 96M records）
- **バグ修正**: date_index構造の不整合修正（build_dataset/build_pace_index/build_kb_ext_index）
- **インフラ**: odds_db.py（バッチオッズ取得）、batch_speed_scrape.py（スピード指数バッチ）

### 新インフラ
| ファイル | 内容 |
|---------|------|
| `core/db.py` | MySQL接続ユーティリティ |
| `core/odds_db.py` | mykeibadb時系列オッズ取得（バッチ対応） |
| `keibabook/batch_speed_scrape.py` | スピード指数バッチスクレイパー |
| `keibabook/parsers/speed_parser.py` | 競馬ブックスピード指数パーサー |
| `_iter_date_index()` | date_index新旧形式対応ヘルパー（experiment_v3.py内） |

### 変更点
- **Model A**: テストデータ(2025-2026)で事前オッズ使用（確定オッズからの切替）
- **訓練データ(2020-2024)**: DBにオッズなし → 従来通り確定オッズ
- **date_indexバグ**: `{date: {tracks: [{races: [{id}]}]}}` を `{date: [race_id]}` と誤解していた問題を修正

### 結果比較
| 指標 | v3.3 | v3.4 | 変化 |
|------|------|------|------|
| Model A AUC | 0.8247 | 0.8246 | -0.0001 |
| Model B AUC | 0.7823 | **0.7826** | +0.0003 |
| Model A Iter | 304 | 343 | +39 |
| Model B Iter | 575 | 512 | -63 |
| VB gap>=2 ROI | 103.2% | 102.6% | -0.6% |
| VB gap>=3 ROI | 113.0% | **114.7%** | **+1.7%** |
| VB gap>=4 ROI | 127.2% | **128.5%** | **+1.3%** |
| VB gap>=5 ROI | 139.0% | 138.8% | -0.2% |
| 特徴量数 A/B | 60/56 | 65/61 | +5/+5 |
| Train entries | 218,785 | 218,785 | 同 |
| Test entries | - | 49,509 | 3,570 races |
| DB Odds (test) | - | 3,570/3,570 | 100% |

### DB事前オッズのカバレッジ
- 訓練(2020-2024): 0/15,904 races（DBに2025以前のオッズなし）
- テスト(2025-2026): **3,570/3,570 races（100%）** — 全て時系列オッズ

### 主な学び
- **訓練データに事前オッズがない制約**: 訓練=確定オッズ、テスト=事前オッズの不整合がある
- **それでもVB gap>=3-4で改善**: 事前オッズによるModel Aの微妙な変化がVB判定にプラス影響
- **Model Bは微増**: 0.7823→0.7826、事前オッズ直接使用しないがデータセット差異の影響
- **今後の改善ポイント**: mykeibadbでオッズ蓄積後、訓練データも事前オッズで統一すれば本来の効果が出る

---

## v3.3 (2026-02-11) — 詳細調教データ統合

### 作業分類
- **データ基盤**: cyokyo_parser v2（HTML全セッション構造化）+ cyokyo_enricher（10,641件補強）
- **特徴量エンジニアリング**: 調教特徴量8個追加（追い切りタイム・脚色・併せ馬・セッション数等）

### 新インフラ
| ファイル | 内容 |
|---------|------|
| `keibabook/cyokyo_parser.py` | HTML→全セッション構造化パーサー (BeautifulSoup) |
| `keibabook/cyokyo_enricher.py` | debug HTML→kb_ext JSONにcyokyo_detail追加バッチ |

### 新特徴量
| 特徴量 | 狙い | Model B重要度 |
|--------|------|--------------|
| `oikiri_5f` | 追い切り5Fタイム | 低〜中 |
| `oikiri_3f` | 追い切り3Fタイム（末脚指標） | 低〜中 |
| `oikiri_1f` | 追い切り1Fタイム（瞬発力） | 低〜中 |
| `oikiri_intensity_code` | 脚色コード (0-4) | 低 |
| `oikiri_has_awase` | 併せ馬有無 | 低 |
| `training_session_count` | 調教セッション数 | 低 |
| `rest_weeks` | 休養週数 | 低〜中 |
| `oikiri_is_slope` | 坂路コースか | 低 |

**所感**: 個々の特徴量重要度は高くないが、Model B AUC +0.0046はv3.1からの大幅改善。VB gap≥5 ROI 139%到達。追い切りタイムはコース・馬場状態による正規化が未実装（改善余地大）。

### 結果比較
| 指標 | v3.1 | v3.3 | 変化 |
|------|------|------|------|
| Model A AUC | 0.8245 | 0.8247 | +0.0002 |
| Model B AUC | 0.7777 | **0.7823** | **+0.0046** |
| Model A Iter | 315 | 304 | -11 |
| Model B Iter | 492 | 575 | +83 |
| VB gap>=2 ROI | 100.0% | **103.2%** | +3.2% |
| VB gap>=3 ROI | 110.2% | **113.0%** | +2.8% |
| VB gap>=4 ROI | 122.6% | **127.2%** | +4.6% |
| VB gap>=5 ROI | 128.3% | **139.0%** | +10.7% |
| 特徴量数 A/B | 51/47 | 60/56 | +9/+9 |

### Model B 特徴量重要度 Top 10
1. `avg_finish_last3` (131,612)
2. `jockey_venue_top3_rate` (103,655)
3. `prev_race_popularity` (80,125)
4. `trainer_venue_top3_rate` (49,789)
5. `track_type_top3_rate` (41,347)
6. `recent_form_trend` (27,438)
7. `entry_count` (25,362)
8. `best_finish_last5` (20,721)
9. `entry_count_change` (20,612)
10. `days_since_last_race` (19,147)

### 主な学び
- **追い切りタイムは正規化なしでも効果あり**: コース別・馬場別の補正で更に向上の余地
- **Model B iterが575に延伸**: 調教データが新しい学習シグナルを提供、過学習していない
- **VB全ギャップでROI向上**: gap≥2ですら103%、実運用でベット機会が最大化
- **cyokyo_detail構造**: sessions[], oikiri_summary, rest_period をkb_extに埋め込み → predict.pyからも利用可能

---

## v3.1 (2026-02-11) — 特徴量エンジニアリング + 軽いハイパラ調整

### 作業分類
- **特徴量エンジニアリング**: 19個追加（脚質8 + ローテ5 + ペース6）
- **ハイパーパラメータ調整**: Model A/B別パラメータ分離

### 新特徴量の狙いと結果

#### 脚質特徴量 (8個) `running_style_features.py`
| 特徴量 | 狙い | Model B重要度 |
|--------|------|--------------|
| `avg_first_corner_ratio` | 先行力（0=逃げ,1=追い込み） | 中 |
| `avg_last_corner_ratio` | 直線入口位置 | 中 |
| `position_gain_last5` | 追い上げ力 | 中 |
| `front_runner_rate` | 逃げ馬率 | 低 |
| `pace_sensitivity` | 逃げ損ね崩壊度 | 低 |
| `closing_strength` | 末脚力 | 中 |
| `running_style_consistency` | 脚質安定度 | 低 |
| `last_race_corner1_ratio` | 最新の先行度合い | 低 |

**所感**: Top10には入らず。corners正規化(÷num_runners)は妥当だが、コース形状（2コーナー vs 4コーナー）による差を考慮していない。改善余地あり。

#### ローテ・コンディション特徴量 (5個) `rotation_features.py`
| 特徴量 | 狙い | Model B重要度 |
|--------|------|--------------|
| `futan_diff` | 斤量増の影響 | 低〜中 |
| `futan_diff_ratio` | 相対的斤量変化 | 低 |
| `weight_change_ratio` | 体調シグナル | 低 |
| `prev_race_popularity` | 消耗した人気馬の検出 | **3位** |
| `popularity_trend` | 人気変動 ※MARKET除外 | (Model Bでは非使用) |

**所感**: `prev_race_popularity`が重要度3位に。「前走人気だった馬」のシグナルがModel Bの市場非依存予測で強く効いている。凡走予測仮説（前走人気馬の消耗）が実証された形。

#### ペース特徴量 (6個) `pace_features.py`
| 特徴量 | 狙い | Model B重要度 |
|--------|------|--------------|
| `avg_race_rpci_last3` | 経験ペース傾向 | 低 |
| `prev_race_rpci` | 直近のペース負荷 | 低 |
| `consumption_flag` | 凡走フラグ(RPCI<=46 & 21日以内) | 低 |
| `last3f_vs_race_l3_last3` | 末脚の相対評価 | 低 |
| `steep_course_experience` | 坂経験 | 低 |
| `steep_course_top3_rate` | 坂適性 | 低 |

**所感**: 個々の重要度は低いが、全体的にModel B AUCを+0.0031押し上げた。consumption_flagは発火頻度が低い（前走RPCI<=46 AND 21日以内は稀）。条件緩和（28日以内等）を検討。

### ハイパーパラメータ変更

| パラメータ | v3.0 | v3.1 Model A | v3.1 Model B | 変更理由 |
|-----------|------|-------------|-------------|----------|
| `num_leaves` | 63 | 63 | **127** | 市場系除外で表現力不足 |
| `learning_rate` | 0.03 | 0.03 | 0.03 | 変更なし |
| `feature_fraction` | 0.7 | **0.8** | **0.8** | 51特徴量に増加、各木がより多く参照 |
| `min_child_samples` | 30 | 30 | **50** | 過学習防止 |
| `reg_lambda` | 1.0 | 1.0 | **1.5** | 過学習防止 |
| `max_depth` | 7 | 7 | **8** | num_leaves増に対応 |

**所感**: Model Bのiterationは494（v3.0も類似）。early stoppingが効いており、過学習の兆候はない。Model Aはiter 315で安定（v3.0の46から大幅改善、odds支配が緩和された可能性）。

### 結果比較

| 指標 | v3.0 | v3.1 | 変化 | 評価 |
|------|------|------|------|------|
| Model A AUC | 0.8241 | 0.8245 | +0.0004 | 維持 |
| Model B AUC | 0.7746 | 0.7777 | +0.0031 | 改善 |
| Model A Iter | ? | 315 | - | 安定 |
| Model B Iter | 494 | 492 | -2 | 安定 |
| VB gap>=2 ROI | 93.3% | **100.0%** | +6.7% | 初の100%超 |
| VB gap>=3 ROI | 109.2% | 110.2% | +1.0% | 改善 |
| VB gap>=4 ROI | 117.2% | 122.6% | +5.4% | 改善 |
| VB gap>=5 ROI | 130.3% | 128.3% | -2.0% | 微減(誤差) |

### Model B 特徴量重要度 Top 10
1. `avg_finish_last3` (141,333)
2. `jockey_venue_top3_rate` (96,432)
3. **`prev_race_popularity` (75,630)** ← NEW
4. `trainer_venue_top3_rate` (48,955)
5. `track_type_top3_rate` (47,538)
6. `recent_form_trend` (27,005)
7. `entry_count` (25,704)
8. `best_finish_last5` (20,796)
9. `jockey_top3_rate` (19,464)
10. `entry_count_change` (19,330)

### 主な学び
- **prev_race_popularityが効く**: 市場系を除外したModel Bで「前走の人気順」がValue Bet検出に強く寄与
- **pace特徴量は単体では弱い**: ただし集団的にAUC底上げには貢献
- **脚質特徴量は期待ほど効かない**: コーナー通過順だけでは脚質の本質を捉えきれない？
- **gap>=2がROI 100%超え**: Value Bet対象の広がり → 実運用でベット機会増
- **feature_fraction 0.7→0.8**: 特徴量増加時は上げた方がよい（各木が新特徴量を拾える）

### 追加のインフラ作業
- `build_pace_index()`: 全レースJSON → {race_id: {rpci, s3, l3, ...}} 辞書
- `predict.py`もv3.1対応済み（pace_index注入、3特徴量モジュール呼び出し）

---

## v3.0 (2026-02-10) — JRA-VANネイティブ移行

### 作業分類
- **データ基盤移行**: keibabook依存 → JRA-VAN直読み
- **特徴量エンジニアリング**: trainer/jockey特徴量をJRA-VAN 5桁コードで100%マッチ

### v2→v3 主要変更
- trainer_top3_rate: 0.5%マッチ → 100%マッチ（JRA-VAN 5桁コード）
- jockey特徴量: 新規追加（win_rate, top3_rate, venue_top3_rate）
- 過去走カバレッジ: 17,335頭 → 36,008頭
- keibabookデータ（rating, mark等）: v3では未使用（Phase3で追加予定）

### 結果
| 指標 | v2 | v3.0 |
|------|-----|------|
| Model A AUC | 0.7944 | 0.8241 (+0.0297) |
| Model B AUC | 0.7635 | 0.7746 (+0.0111) |
| 特徴量数 A/B | 32/27 | 32/29 |
| VB gap>=3 ROI | 104.7% | 109.2% |
| VB gap>=5 ROI | 99.9% | 130.3% |

### 主な学び
- **JRA-VAN IDでの100%マッチが最大の改善要因**: AUC +0.03は非常に大きい
- **jockey_venue_top3_rateがModel B重要度2位**: 騎手の場所適性は市場に織り込まれにくい
- **過去走カバレッジ倍増**: デビュー馬以外ほぼカバー

---

## v2 (2026-02-09) — デュアルモデル + 前走成績

### 作業分類
- **アーキテクチャ変更**: 単一モデル → デュアルモデル（精度/Value）
- **特徴量エンジニアリング**: 前走成績15個追加

### v1→v2 主要変更
- Model A（全特徴量）+ Model B（市場系除外）のデュアルモデル導入
- 前走成績特徴量15個追加（avg_finish_last3, venue_top3_rate等）
- Value Bet戦略: odds_rank vs Model B rankの乖離

### 結果
| 指標 | v1 | v2 |
|------|-----|------|
| Model A AUC | 0.7936 | 0.7944 |
| Model B AUC | - | 0.7635 |
| VB gap>=3 ROI | - | 104.7% |

### 主な学び
- **Value Bet戦略が有効**: 精度モデルと市場独立モデルの乖離がROI向上の鍵
- **デュアルモデル設計が正解**: Model Bで「市場が見落としている実力馬」を検出

---

## 今後の実験候補

> 詳細な戦略・課題・悩みは `feature_engineering_strategy.md` を参照

### Tier 1: 低コスト・高期待値
- [x] ~~**特徴量pruning**~~: v5.5で実験。20%は悪化、dead features(=0)のみが安全
- [x] ~~**障害レース除外**~~: sr_parserレベルで既にフィルタ済み（TRACK_TYPESに障害コード無し）
- [ ] **MARKET/VALUE自動分類テスト**: 特徴量1つずつModel Bに追加してA-B乖離への影響を測定
- [x] ~~**バックテストROI信頼区間**~~: v5.5で実装。win_only CI=[60-170%]、366件では判断困難

### Tier 2: 中コスト・中期待値
- [ ] **mykeibadb TIME_SA着差**: チャクラ訓練データの精度向上。まずカバレッジ確認
- [ ] **margin正規化**: コース×距離別z-score化（芝1200m vs ダート2400mの着差分布差）
- [ ] **marginのKelly統合**: 現在のboolフィルタ → 連続値としてKellyに組み込む
- [ ] 余力ラップ再実験: race_last1f_avg_last3 + prev_race_last1f + race_decel_l1f_avg_last3 の上位3のみ
- [ ] 降格ローテ精選: koukaku_rote_count + is_koukaku_venue + is_koukaku_female の上位3のみ残す

### Tier 3: 高コスト・不確実
- [ ] 外部指数（ウマニティ能力指数/SP指数）: スクレイピング+特徴量化
- [ ] 展開負けスコア(Phase 4): hidden_perf_score, agari_rank_vs_finish
- [ ] 条件付き能力予測: ペース×隊列×馬場のシナリオ別能力推定

### 保留・完了済み
- [x] ~~33ラップ + レース傾向適性特徴量~~ → v5.1で完了
- [x] ~~余力ラップ(ch7) + race_trendカテゴリ~~ → v5.2で実験、ROI低下。上位3のみ再実験を検討
- [x] ~~降格ローテ~~ → v5.2bで実験、AUC改善だがVB ROI低下。精選を検討
- [x] ~~keibabookデータ統合（training_arrow）~~ → v3.2で完了
- [x] ~~詳細調教データ（追い切りタイム等）~~ → v3.3で完了
- [x] ~~DB事前オッズ統合~~ → v3.4で完了
- [ ] 追い切りタイムのコース別・馬場別正規化（坂路 vs ウッド vs CW、良 vs 重）
- [ ] 騎手×馬の相性（過去走の騎手一致率と成績）
- [ ] is_koukaku_age実装（race_class情報が必要）
- [ ] 訓練データの事前オッズ統一（mykeibadbオッズ蓄積後）
- [ ] 凡走確率専用モデル: 人気馬の凡走予測

### ハイパーパラメータ・アーキテクチャ
- [ ] Optunaによる体系的探索
- [ ] Cross-validation（時系列5-fold）でROI分散を測定（Bootstrap CIで不確実性の大きさを確認済み）
- [ ] XGBoost/CatBoostとの比較
- [ ] Place戦略の最終判断: 全廃 or 超厳格化 or 検出専用
