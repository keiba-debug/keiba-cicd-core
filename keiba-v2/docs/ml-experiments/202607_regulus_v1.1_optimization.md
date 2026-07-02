# Regulus v1.1 最適化・買い目シミュレーション (Session 183 / 2026-07-02)

3歳上 芝OP以上 専用モデル **Regulus** を対象に、①ML Report 専用ダッシュボード完成、
②モデル最適化(複数パターン)、③買い目シミュレーションを実施した記録。

> 前提: Regulus は「経験豊富な王者級馬の対決を軌跡/CID中核で読む専門家の第二意見」=
> **表示専用**(bet_engine 非配線)。OP+ 市場はシャープで払戻エッジは事前想定しない。
> 価値は本命精度・較正・ランキング品質。参照: `regulus-race-context-engine`,
> `calibration-edge-map`, `feedback_specialist_for_its_own_sake`。

対象データ: `data3/ml/nova/turf_op/splits/{train,val,test}.pkl`
(3歳上×芝×OP以上, test=2025.05-2026.05 = 611R / 7,961頭, sire_cutoff=2025-03-31)。

---

## 1. 出発点 (v1.0) の弱点

| | AUC | auc_val | ECE(cal) | Brier(cal) | best_iter | Top1 ROI |
|---|---|---|---|---|---|---|
| P (is_top3) | 0.7701 | 0.7497 | 0.0190 | 0.1476 | **38** | 81.5% |
| W (is_win)  | 0.7574 | 0.7989 | **0.0326** | 0.0694 | 186 | 79.9% |

- **early-stop/isotonic較正の val が 2025.04 の1ヶ月(47R/600頭)しかない** → P が
  best_iter=38 で早期停止(≒未学習)、W の較正 ECE=0.033 と不安定。
- v1.0 の Top1 ROI 81.5% は iter=38 のほぼ未学習モデルのノイズで、意味のある数字ではない。

---

## 2. 最適化 複数パターン比較 (`scratchpad/optimize_regulus.py`)

評価軸を ROI に限定せず「馬券購入成績につながる分析結果」= AUC / 較正(ECE,Brier) /
本命精度(Top1) / ランキング品質(MRR, winner_in_top3) で多軸評価。

### P (is_top3)
| config | AUC | auc_val | ECE | Brier | ROI% | win% | MRR | w_in_top3 | iter |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 0.7701 | 0.7497 | 0.0190 | 0.1476 | 81.5 | 27.7 | 0.4748 | 0.5686 | 38 |
| pruned(gain0除去) | 0.7736 | 0.7508 | 0.0244 | 0.1473 | 68.9 | 25.5 | 0.4625 | 0.5637 | 120 |
| hp_small1 | 0.7747 | 0.7531 | 0.0190 | 0.1469 | 69.7 | 25.4 | 0.4622 | 0.5670 | 198 |
| hp_small2 | 0.7694 | 0.7503 | 0.0168 | 0.1476 | 77.5 | 26.0 | 0.4667 | 0.5719 | 45 |
| bigval_base | 0.7715 | 0.7551 | 0.0220 | 0.1456 | 70.9 | 25.5 | 0.4633 | 0.5719 | 279 |
| **bigval_small1** | **0.7757** | **0.7559** | 0.0213 | **0.1443** | 74.8 | 26.5 | 0.4722 | 0.5686 | 326 |

### W (is_win)
| config | AUC | auc_val | ECE | Brier | ROI% | win% | MRR | w_in_top3 | iter |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 0.7574 | 0.7989 | 0.0326 | 0.0694 | 79.9 | 25.4 | 0.4436 | 0.5294 | 186 |
| hp_small2 | 0.7645 | 0.7817 | 0.0301 | 0.0691 | 75.9 | 24.2 | 0.4476 | 0.5474 | 191 |
| hp_mid | 0.7617 | 0.7720 | 0.0310 | 0.0692 | 83.3 | 25.9 | 0.4555 | 0.5588 | 206 |
| **bigval_base** | 0.7591 | 0.7606 | **0.0033** | **0.0658** | 73.2 | 23.9 | 0.4568 | **0.5768** | 165 |
| bigval_small1 | 0.7603 | 0.7509 | 0.0030 | 0.0663 | 74.8 | 24.9 | 0.4584 | 0.5605 | 96 |

### LambdaRank (レース内group, is_top3で評価)
| config | AUC | ECE | ROI% | win% | MRR | w_in_top3 |
|---|---|---|---|---|---|---|
| lr_smallval | 0.7622 | 0.0291 | 76.9 | 27.5 | 0.4741 | 0.5768 |
| lr_bigval | 0.7610 | 0.0225 | 71.4 | 25.7 | 0.4657 | 0.5817 |

### 結論
- **val拡大 (1ヶ月→6ヶ月 2024.11-2025.04) が最大の効き目**。P は AUC+0.0056/Brier改善、
  W は **ECE 0.0326→0.0033 (≈10x)**・winner_in_top3 0.529→0.577。tiny-val の早期停止・
  較正不安定という構造問題を直接解消。
- P は小データ(≈36.5K)向けに正則化強め(num_leaves63/depth6/mcs80/α0.3/λ3.0)が最良。
- **LambdaRank は binary を上回らず**(AUC 0.762 < 0.776)、積極的な特徴量pruning は W で
  悪化(AUC 0.7574→0.7447)→ 両方不採用。lean_plus/binary 構成を維持するのが最良。

→ **v1.1 採用: bigval + P正則化強め。**(`ml/nova/train_regulus.py`)

---

## 3. グレード帯別 成績 (第二意見の得意条件マップ)

v1.1 の Top1(予測本命)単勝を帯別に集計(`meta.segment_analysis_p/w`, dashboardに表示)。

**P モデル Top1単勝** (bootstrap CI付, `scratchpad/regulus_betting_sim.py` A2):
| 帯 | R | AUC | 勝率 | 複勝率 | 単ROI | ROI 90%CI |
|---|---|---|---|---|---|---|
| 重賞(G1-G3) | 111 | 0.768 | 29.7% | 56.8% | **103.1%** | [75.2, 133.4] |
| **G1** | 24 | — | **50.0%** | **70.8%** | **140.0%** | [89.1, 191.3] |
| G2 | 36 | — | 30.6% | 75.0% | 100.3% | [59.7, 147.0] |
| G3 | 51 | — | 19.6% | 37.3% | 87.6% | [41.8, 142.4] |
| Listed | 51 | 0.742 | 23.5% | 51.0% | 68.2% | [39.4, 99.8] |
| OP | 449 | 0.778 | 26.1% | 60.4% | 68.5% | [58.9, 79.0] |

- **重賞、特に G1 で本命精度が突出**(G1 は Regulus本命が半分勝つ・複勝内7割)。
- Listed は弱点(AUC最低・ROI最低)。→ Regulus を信頼するなら重賞、Listed は割引。

---

## 4. 買い目シミュレーション (`scratchpad/regulus_betting_sim.py`)

W最適化モデルで 5系統 × bootstrap CI(2000, レースクラスタ)。**勝ち筋の有無を正直に判定**。

| 戦法 | n | 勝率 | ROI | 90%CI | 平均オッズ | 判定 |
|---|---|---|---|---|---|---|
| Top1単勝 全体 | 611 | 23.9% | 73.2% | [63,83] | 3.06 | ✗ 明確に負け |
| Top1単勝 重賞 | 111 | 23.4% | 88.6% | [62,117] | 3.78 | △ CIが100跨ぎ |
| Top1単勝 G1(W) | 24 | 41.7% | 127.5% | [77,184] | 3.06 | △ n過少 |
| EV≥1.3 (proba_w×odds) | 2800 | 3.0% | 77.0% | [56,99] | 25.4 | ✗ 長オッズ選抜で負け |
| gap≥2 (人気-W順位) | 1881 | 4.6% | 94.3% | [73,117] | 20.6 | △ CIが100跨ぎ |
| gap≥2 重賞 | 472 | 4.2% | 104.3% | [60,159] | 24.6 | △ CI広く非頑健 |
| gap≥5 全体 | 404 | 1.5% | 37.5% | [11,71] | 25.3 | ✗ 低クラスのgapエッジは非転移 |
| 逆張り(W本命&人気≥3) | 129 | 13.2% | 83.3% | [52,116] | 6.32 | △ CIが100跨ぎ |

### 結論(正直に)
- **頑健な払戻エッジは無い**。全戦法で ROI<100% か、CI が 100% を跨ぎ break-even と区別不能。
  → 事前想定(OP+市場はシャープ)を実データで確認。`calibration-edge-map` と整合。
- 低クラスで効いた **gap≥5 単勝エッジは OP+ に転移しない**(gap≥5全体 ROI 37.5%)
  = OP+ 市場は極端gap馬も正しく織り込んでいる。
- EV≥閾値 は平均オッズ18-29倍の長オッズ馬を選抜して負け = モデル過信 (favorite-longshot)。
- **最有望セル**(G1 Top1 140%/n=24, gap≥2重賞 104%/n=472)も CI が 100 を跨ぎ、賭けるには
  サンプル不足。**shadow 監視に留める**(`payout-ceiling-strategy`, `feedback_odds_gate_hindsight`)。

→ **Regulus は表示専用のまま。**payout ではなく較正/本命精度(特に重賞)が価値。

---

## 5. 本番反映

- `ml/nova/train_regulus.py` → **v1.1**: bigval reslice + P正則化強め + `segment_analysis_*` を
  meta に追記。`--set-active` で registry active_version=1.1(1.0 は履歴保持)。
- 生成物: `data3/ml/models/regulus/live/{model_p.txt,model_w.txt,meta.json,calibrators.pkl}`。
  `predict_regulus` は features を meta から読むため無改修で v1.1 対応(2026-06-28: 7R/85頭で確認)。
- **ML Report 専用ダッシュボード**: `web/src/app/analysis/ml/tabs/RegulusTab.tsx`(P/W metrics・
  ROI・帯別 segment table・最適化ノート・特徴量重要度) と `EclipseTab.tsx`(閾値別 precision/recall・
  PR-AUC・特徴量) を新設。生JSONダンプ表示を廃止。`ModelSelector` に crown アイコン追加。

## 7. 追加検証: 汎用比較 / 条件スコープ / アンサンブル → v1.2 (同 S183)

### 7.1 Polaris(汎用) vs Regulus(専用) — 芝OP+ に絞っても (`scratchpad/gen_vs_spec.py`)
リーク回避で両者 held-out 新規学習(差は学習スコープのみ)。3歳上芝OP+ test 611R:
| | AUC | ECE | 重賞勝率 | 重賞ROI |
|---|---|---|---|---|
| P GEN_lean(汎用) | 0.7770 | 0.0080 | 26.1 | 96.1 |
| P SPEC=Regulus | 0.7757 | 0.0213 | **29.7** | **103.1** |
| P GEN_market(≈本物Polaris) | **0.7945** | 0.0094 | 25.2 | 76.0 |
| W GEN_market(≈本物Polaris) | **0.8028** | 0.0091 | 27.0 | 78.9 |

- **総合AUCは汎用 ≥ 専用(芝OP+に絞っても)**。学習データ量(22万 vs 3.6万)が専用化を上回る。市場特徴量あり(≈本物Polaris)は AUC 0.79-0.80 で決定的に上。
- **ただし重賞(G1-G3)の本命精度だけ Regulus が汎用を上回る**(P Top1 勝率29.7% vs 25-26%)= 設計で狙った"王者級の対決"ニッチ。[[feedback_specialist_for_its_own_sake]] の見立て通り。

### 7.2 G3以上(重賞)に絞って学習すると? → 悪化 (`scratchpad/regulus_g3.py`)
訓練スコープ ALL/OP+/G3+ を重賞test 111Rで比較。訓練量: ALL 22万 / OP+ 3.6万 / **G3+ わずか480R**。
- **G3+絞りは全変種で最下位**(P AUC 0.7683→0.7584, W 0.7684→**0.7117**急落, best_iter 32-40 で即過学習)。データ痩せが専用化利得を食い潰す。

### 7.3 学習≠適用条件でよい / 幅広学習+重み (`scratchpad/regulus_weight.py`)
序列: **ハード絞り込み(最悪) << sample_weight ≈ 幅広学習(最良)**。重賞を weight=3/5 で強調しても効果は ±0.005 AUC=ノイズ(重み過大で W は iter37 崩壊)。理由=grade特徴量で木が内部的に区別済。
→ **教訓を独立メモリ [[feedback_train_scope_not_match_eval]] に記録**。狙いへの寄せ方の優先順: ①条件を特徴量化 > ②適用時に絞る/強調 > ③sample_weight > ④ハード絞り学習(最終手段)。

### 7.4 seedアンサンブル + P/Wブレンド → v1.2 採用 (`scratchpad/regulus_ensemble.py`)
36K小データの単一seed分散を 5seed平均で低減:
| | 単一seed | 5seedアンサンブル |
|---|---|---|
| P AUC / ECE / winner_in_top3 | 0.7743 / 0.0213 / 0.5686 | 0.7759 / **0.0150** / **0.5833** |
| W AUC / winner_in_top3 | 0.7567 / 0.5768 | **0.7624** / **0.5866** |

- **P/Wブレンド本命**(ens5 prob, top1 by score): `0.5P+0.5W` が総合最良(勝率26.7%)、`rankavg` が重賞最良(勝率29.7%/ROI107.8%)。P単独/W単独より良い本命が取れる。
- **→ v1.2 本番採用**: `train_regulus.py` が 5seed を学習・平均raw較正して `model_{p,w}.txt`(primary)+`model_{p,w}_ens{1..4}.txt` を保存。`predict_regulus.py` は全メンバー平均 + `rank_blend`/`blend_score` を `regulus_scores.json` に追記。`meta.ensemble_seeds` 記録。registry active=1.2。predict実機確認(P×5 W×5, 2026-06-28)。

**v1.2 最終 (3歳上芝OP+ test 611R)**: P AUC 0.7763 ECE 0.0205 / W AUC 0.763 ECE 0.0034 / 重賞AUC P0.769・W0.774。

## 8. B' = クラス相対の軌跡 → 検証済 **NO-GO** (`scratchpad/regulus_bprime{,2}.py`)
「残る唯一の有望方向」だった B'(過去走の IDM をクラス中央値/z-scoreで相対化しトレンド化)を実装・測定。
狙い=モデルは `jrdb_idm_avg3` と `avg_race_level_last3` を別々の周辺集計でしか見ず、過去走ごとの
(IDM,クラス)共変を捉えられない→クラス相対IDM軌跡が新情報になりうる、という仮説。
- データ: SED idm × history grade を join(2020+ 99.7%被覆)、リークフリー(bisect)、class baseline凍結。
- 結果(held-out test 611R, +0.005ゲート): 3変種すべて未達。**P は毎回フラット〜−0.0018**、
  **W は +0.0026〜+0.0032 止まり**(z版は重賞AUCがむしろ低下・リーン部分集合は W −0.0052 と符号反転)。
  既存 idm_avg3/idm_trend との corr=0.65〜0.83 = **大部分が冗長**。
- 結論: **NO-GO**。S177 A(生front_ratio≒0)・S178 B(絶対IDM文脈掃除=NO-GO)に続く3度目の確認で、
  **JRDB IDM + 既存race-level特徴量が既にクラス文脈シグナルをほぼ拾い切っている**。OP+ は情報天井近く、
  更なる伸びは特徴量再エンジニアリングでなく**新しいデータ入力**が要る([[feedback_long_term_right_way]])。

## 9. 本命 shadow トラッカー + Web配線 (S183 後続)
- **rank_blend を Web 出馬表(predictions race-card)の「Reg」列に配線**: 上段=P/W合成本命順位(◎=本命)、下段=polaris比delta。`predictions-reader.ts` RegulusScore型に rank_blend/blend_score 追加。
- **`ml/nova/regulus_shadow.py`(新)**: 各 `regulus_scores.json` の Regulus本命(blend/P/W)を確定結果(race_*.json finish/odds)と突合し、グレード帯別 単複ROI+bootstrap CI を集計→`models/regulus/shadow_ledger.json`。日次prep後に再実行で n 蓄積。**賭けなし・純追跡**。
- **★配線バグ発見・修正**: predict_regulus の track_type フィルタが `"芝"` 決め打ち→旧世代 predictions.json は `"turf"`(英)で**2025held-out全域が0件で沈黙脱落**([[gap-grade-raceday-blindspot]]再来)。`in ("芝","turf")` に修正→backfill で shadow が 139→**630レース**に。
- **shadow 結果(2025-05〜2026-06, held-out 630R)**: 全体OP+ ROI 73% CI[64,82]=**払戻エッジ無し確定**(市場シャープ・n630でCI締まる)。**G1 が特異**: P本命 単勝**50.0%(13/26)**・ROI 131% CI[89,175]・複勝65%(blend/W本命も42%勝率/ROI122-128%)。重賞(116R)複勝53-56%。Listedは弱点(単16-18%)。→ **払戻の頑健エッジは無いが、G1本命精度は本物の予想品質シグナル**。CI下限89でまだ100未達=あと1シーズンで跨ぐ可能性、shadow継続。
- 注意(正直): G1本命の的中平均odds 2.6=概ね人気馬。「Regが市場人気を超えて当ててる」か「単に人気を選んでる」かの分離(vs市場favorite比較)は未検証=次の精査点。

## 10. Eclipse(差し決着) にレシピ移植 → v2.1 (S183 後続)
Regulus v1.2 の手法を Eclipse に移植。精査で **liveが stale(train~2024-06止まり)**・val は既に6ヶ月=bigvalは効きにくい と判明→効くのは **データ更新 + seedアンサンブル**。ネックは experiment_closing が毎回 dataset をゼロ再構築(キャッシュ無し)。
- **`experiment_closing.py` に datasetキャッシュ + 5seedアンサンブル追加**(既定 fresh: train 2020-2024.12 / val 2025.01-06 6ヶ月 / test 2025.07-2026.06)。初回12分→**キャッシュ後8秒**で反復可能に。`predict_closing.py` は全メンバー平均に対応。
- **結果(test 2025.07-2026.06 3233R)**: **アンサンブルAUC 0.6948 vs seed42単体0.6888 = +0.006(同test・クリーンなアンサンブル効き)**。PR-AUC 0.1717、ECE(cal)0.0225。モデルは 2024-12 まで学習=**stale解消**(旧liveは2024-06/AUC0.6873だが別test期間で厳密比較不可)。registry active=closing-v2.1。predict実機確認。
- 距離別: Long(2400+) AUC 0.879 が突出=長距離は差し決着が読みやすい。
- **★配線トラップ修正**: experiment_closing は legacy root(`model_closing*.txt`)に保存するが、model_loader/predict_closing は標準スキーム `models/eclipse/live/` を読む(Apr-3の旧v2.0コピーが残存)=**再学習してもlive推論に反映されない split-brain**。experiment_closing に `models/eclipse/live/`(model_p.txt/model_p_ens*/calibrators.pkl/meta.json)への同期を追加、predict_closing の ens ロードを model_dir 基準に修正。predict実機で 5モデル/closing-v2.1 ロード確認。ML Report は root meta_file を読むので root も維持([[ml-report-model-registry-meta-file]] と同系のトラップ)。

## 11. 残課題
- G1本命精度 vs 市場favorite の分離検証(shadowを人気ランク別に切る)。shadow を Web ページ化(現状JSON台帳)。
- Regulus のモデル側チューニングは概ね出尽くし(構造→v1.1・アンサンブル→v1.2 が本命、他は marginal/NO-GO)。Eclipse も同様(fresh+アンサンブル=v2.1 で一巡)。
