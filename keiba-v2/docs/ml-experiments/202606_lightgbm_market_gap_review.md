# LightGBM市場ギャップ創出レビュー

**作成日**: 2026-06-11  
**対象**: polaris LightGBM 系ML、ML Report、analysis配下の既存分析  
**目的**: 現状のLightGBM手法をレビューし、市場評価とのギャップを作るために検証できる仮説を整理する。

---

## 1. 結論サマリー

現状の課題は「モデルの精度不足」だけではなく、**精度を上げるほど市場の序列に近づき、Value Betの源泉である乖離が薄くなる**ことにある。

既存実験でもこの構造は繰り返し観測されている。

- `v8.2 AR->W stacking` はAR/Wの不一致を減らしたが、Wが人気馬寄りになりValue Betが機能停止した。
- `v8.4 Selective` では、モデル信頼度を高めるフィルタより、`vb_gap` で市場乖離を強めるフィルタの方がROIを伸ばした。
- `v5.6 EV vs Gap` では、EV単独よりgapが強く、`gap + EV + margin` の併用で初めてCI下限100%超を達成した。
- `v5.4 Bayesian smoothing` では、平滑化率をVALUEに入れるとAUCは上がるがA-B乖離が縮小し、MARKET扱いに戻すとROIが改善した。

したがって次の改善軸は、LightGBMそのものの置き換えより先に、以下を優先するのがよい。

1. **MARKET/VALUE分類の再監査**: 市場に近い特徴量を独自モデルへ入れすぎていないか確認する。
2. **視点の独立性維持**: P/W/ARをスタッキングせず、乖離そのものをシグナルとして扱う。
3. **セグメント別運用**: 全レース一律ではなく、重賞、オッズ帯、頭数、距離、会場などで買う/買わないを分ける。
4. **analysis由来の非市場シグナル追加**: RPCI/33ラップ、ratingレベル差、千直専門性、出遅れ耐性、接戦騎手などを、gapとの交差で検証する。
5. **評価をAUC中心からROI/CI中心へ**: gain importanceやAUCだけでは採用判断しない。

---

## 2. 現状把握

### 2.1 ライブモデル

`data3/ml/models/polaris/live/meta.json` の確認結果。

| 項目 | 値 |
|---|---|
| live version | `2.3` |
| train | `2020 ~ 2025-03` |
| val | `2025-04` |
| test | `2025-05 ~ 2026-03` |
| `features_value` | 172 |
| `market_features` | 21 |
| P特徴量 | 152 |
| W特徴量 | 144 |
| AR特徴量 | 154 |
| `ar_stack` | false |
| `margin_mode` | adjusted |

現行は、古いA/B/W/WV/Reg Bの5モデル説明から進化し、実装上は主に以下の3軸へ整理されている。

| モデル | 目的 | ラベル/ターゲット | 主用途 |
|---|---|---|---|
| P | 3着内予測 | `is_top3` | 好走候補、VB候補抽出 |
| W | 1着予測 | `is_win` | 単勝候補、EV |
| AR | 着差回帰 | `target_margin` | 能力/余力、フィルタ |

### 2.2 重要なモデル別特徴量差分

`features_per_model` でP/W/ARは分離されている。

Pのみが持つ主な特徴量:

- コメントNLP
- スピード指数
- JRDB CID/LS
- JRDB不利/馬場差/ペースマッチ系

WのみがPより多く持つ主な特徴量:

- RPCI
- 33ラップ
- 脚質
- レース傾向適性

WのみがARより多く持つ主な特徴量:

- 騎手系4本: `jockey_win_rate`, `jockey_top3_rate`, `jockey_venue_top3_rate`, `jockey_close_win_rate`

ARのみがWより多く持つ主な特徴量:

- コメントNLP
- スピード指数

これは良い分離でもあるが、検証観点では次の疑いが残る。

- PにCID/LSを入れるとP Top1は改善しやすいが、人気順との相関も上がりやすい。
- Wに騎手系を入れると勝率は上がるが、人気馬寄りになりやすい。
- ARにコメント/スピードを入れると素能力軸としては有効だが、市場寄り指数を混ぜると独立性が落ちる可能性がある。

---

## 3. 現状の問題点

### 3.1 AUC改善とROI改善が一致していない

既存ログでは何度も、AUCが改善してもVB ROIが下がっている。

典型例:

- `v5.2b`: 降格ローテでModel B AUCは改善したが、VB ROIは低下。
- `v5.7`: dead features削除はAUC差が小さいがROIが大きく悪化。
- `v8.2`: W勝率は改善したが、平均人気が1.64まで寄り、ROIは悪化。

**レビュー判断**: 採用基準を「AUC/Gain上昇」ではなく、`gap分布`, `平均人気`, `ROI CI`, `累積P&L`, `セグメント安定性` に置くべき。

### 3.2 市場寄り特徴量の混入境界が曖昧

`MARKET_FEATURES` ではオッズ、人気、JRDB事前指数、新聞印、平滑化率などが除外されている。一方で、以下は独自モデル側にも入っている。

- `prev_race_popularity`
- `prev_grade_level`, `grade_level_diff`, `venue_rank_diff`
- CK調教ラップ系
- `kb_rating`
- JRDB過去IDM/上がり/テン指数
- CID/LSの一部はP専用

これらは「公開情報だが市場が完全には織り込めない」可能性もあるが、カテゴリによっては市場と近い。特に市場が同じ情報源を見ている場合、独自モデルに入れるほどgapが縮む。

### 3.3 Gain重要度だけでは採用判断が危険

ML Reportの特徴量重要度はLightGBM gainベース。gainは「モデル内でどれだけ分岐に使われたか」であり、以下を直接示さない。

- 市場との相関を増やしたか
- gap候補を増やしたか減らしたか
- ROIを改善したか
- 特定セグメントでだけ効くか
- 低importanceだが穴馬抽出に効くか

既存実験でもコメントNLPはimportance下位ながらROIに寄与し、逆に大きく効く特徴量が市場寄り化を招いた。

### 3.4 全レース一律のTop1/EV評価は弱い

`polaris_segments` では、P Top1とW Top1でセグメント差が大きい。

P Top1:

- G1 ROI 385.0%（20件）
- G3 ROI 264.6%（59件）
- Listed ROI 120.4%（56件）
- OP ROI 111.2%（634件）
- 新馬 ROI 75.9%
- 1勝クラス ROI 82.6%
- odds 5.1-10 ROI 111.1%
- 17頭以上 ROI 127.5%

W Top1:

- 全体は勝率が高いが、多くの月で単勝ROIが80%台。
- odds 5.1-10 ROI 122.9%、10.1-20 ROI 206.9%。
- 低オッズ帯は勝率が高くてもROIが低い。

**レビュー判断**: 「当たるモデル」ではなく「買ってよいセグメントだけを選ぶモデル運用」が必要。

### 3.5 乖離を消す改善は逆効果

`v8.2` でARをWへstackした結果、AR/W一致率は改善したが、Wが人気順へ寄りValueBetが壊れた。

この実験は極めて重要で、現在の問題への答えでもある。

**市場と違う判断をするモデル間の不一致は、欠陥ではなく収益源の候補**。  
P/W/ARは統合するより、差分を分析して買い条件に使う方がよい。

---

## 4. 市場ギャップを作るための設計原則

### 原則1: Model B/W/ARを「賢くしすぎる」方向に注意する

市場に近い公開情報を大量投入すると、モデルは正しく人気馬を選ぶようになる。これは的中率には効くが、ROIには逆風。

検証時は以下を見る。

- 平均オッズ
- favorite一致率
- `odds_rank` と `rank_p/rank_w/ar_rank` の相関
- gap>=Nの件数
- gap帯別ROI

### 原則2: 信頼度ではなく乖離を買う

`v8.4` で、モデル信頼度高フィルタはROIを半減させ、`vb_gap` フィルタはROIを伸ばした。

検証優先度:

1. `gap`
2. `dev_gap`
3. `gap + EV`
4. `gap + ARd`
5. `P/W/AR不一致パターン`

### 原則3: 特徴量追加は「全体AUC」ではなく「gap条件下ROI」で判定する

新特徴量の評価表には最低限以下を入れる。

| 観点 | 指標 |
|---|---|
| 精度 | P/W AUC, Brier, ECE |
| 市場乖離 | rank相関, favorite一致率, gap件数 |
| 回収 | gap×EV×ARd ROI, Bootstrap CI |
| 安定性 | 月別P&L, H1/H2, セグメント別 |
| 副作用 | 平均人気、低オッズ寄り化 |

---

## 5. 検証仮説

### H1. MARKET/VALUE自動分類の再監査

**仮説**: 現在VALUE側に残っている一部特徴量が市場寄りで、独自モデルを市場評価に近づけている。

候補:

- `prev_race_popularity`
- `prev_grade_level`, `grade_level_diff`, `venue_rank_diff`
- `kb_rating`
- CK調教ラップ系
- JRDB過去指数系
- CID/LS系

検証:

- 特徴量カテゴリごとに除外/追加アブレーション。
- `odds_rank` との相関、favorite一致率、gap件数を測る。
- AUCではなく `gap>=6 + EV>=1.2 + AR/margin条件` のROI CIを採用基準にする。

既存入口:

- `ml/experiment.py`
- `ml/compare_models.py`
- `docs/ml-experiments/v5.4_bayesian_smoothing.md`
- `docs/ml-experiments/v8.2_polaris2.2_ar_stack.md`

採用条件:

- AUCが同等以上で、gap候補数またはgap条件ROIが改善。
- AUCが下がっても、ROI CIと累積P&Lが改善するなら候補に残す。

### H2. P/W/AR乖離パターンの体系化

**仮説**: P/W/ARの不一致はノイズではなく、穴馬抽出の源泉である。

既存の `model_divergence_analysis.md` では、`ARd1位 & V低(>=5)` がROI 115.7%で唯一のプラス収支パターンとして記録されている。

検証:

- `P高・W低`
- `W高・P低`
- `AR高・W低`
- `AR高・P低`
- `P/W一致`
- `P/W/AR完全一致`

をパターン化し、単勝/複勝ROI、平均オッズ、月別P&Lを見る。

既存入口:

- `ml/analyze_divergence.py`
- `docs/model_divergence_analysis.md`
- `ml/analyze_shap.py`
- `ml/strategies/bettype_efficiency.py`

注意:

- 統合/stackingで乖離を消す方向は避ける。
- 乖離パターンを「買いルート」として別枠化する。

### H3. Selective戦略の再検証と本番プリセット化

**仮説**: 全レースTop1より、重賞/非人気/高gapだけを買うSelectiveの方が市場ギャップを保持できる。

根拠:

- `v8.4`: Selective baseline ROI 203.1%。
- `Sel_v3 gap>=4`: ROI 381.3%。
- OOS 2026-04~05でもv3系がbaselineを上回る方向。

検証:

- test期間を2025-05~2026-03から、最新まで延長。
- OOSを6か月以上蓄積。
- 重賞だけでなく、OP/List/未勝利/新馬を分けて再検証。

既存入口:

- `ml/strategies/selective.py`
- `data3/analysis/polaris_segments/*/summary.md`
- `docs/ml-experiments/v8.4_polaris2_segments_and_selective.md`

採用条件:

- 少数高ROIだけでなく、月別P&Lが極端に一発依存でないこと。
- CI下限が100%近辺以上、またはOOSでbaselineより継続優位。

### H4. RPCI/33ラップによる展開適性ギャップ

**仮説**: 市場はコース/馬の展開適性を単純化しやすく、RPCI/33ラップのタイプ適性でギャップが作れる。

既存知見:

- `v5.1`: 33ラップはWin予測に有効。
- `v5.2`: 余力ラップ8特徴量の一括追加はROI悪化。
- `analysis/rpci` は馬場別、頭数補正、v2 7分類を持つ。

検証:

- 余力ラップ8個ではなく、上位物理特徴だけ再実験。
  - `race_last1f_avg_last3`
  - `race_decel_l1f_avg_last3`
  - `prev_race_last1f`
- 既存の `avg_lap33_last3`, `prev_race_lap33`, `trend_versatility` と交差。
- `gap>=6` 条件下で、展開適性がある馬だけのROIを見る。

既存入口:

- `analysis/race_type_standards.py`
- `web/src/app/analysis/rpci/page.tsx`
- `ml/features/pace_features.py`
- `docs/ml-experiments/v5.1_lap33_trend.md`
- `docs/ml-experiments/v5.2_yoriki_lap.md`

採用条件:

- W/PのAUCより、`gap×race_type_match` でROI改善。
- 低importanceでも、gap条件下で効くなら採用候補。

### H5. Rating/BRレベル差の「前走強い負け」検出

**仮説**: 前走着順は市場に強く反映されるが、前走レースレベルや混戦度までは過小評価されやすい。

検証:

- `前走Hレベルで凡走 -> 今走L/通常レベル`
- `前走混戦で着順悪化 -> 今走メンバー弱化`
- `会場レベル差`
- `未勝利時期別レベル差`

をgap条件と交差させる。

既存入口:

- `analysis/rating_standards.py`
- `web/src/app/analysis/rating/page.tsx`
- `ml/features/rotation_features.py`
- `docs/ml-experiments/v5.2b_koukaku_rotation.md`

注意:

- 既存の降格ローテ一括追加はAUC改善/ROI低下だった。
- 単体特徴量として入れるより、`gap + ARd + level_drop` のフィルタとして検証する。

### H6. 新潟1000mなどニッチ専門モデル/オーバーレイ

**仮説**: 全体モデルでは市場に吸収されるが、特殊条件では専門知識が市場より強い。

候補:

- 新潟1000m
- 外枠/馬場/牝馬/血統/騎手厩舎の組み合わせ
- 千直経験が悪く見えるが条件が好転する馬

既存入口:

- `analysis/niigata1000/backtest_runner.py`
- `analysis/niigata1000/rules/v0_4.yaml`
- `analysis/niigata1000/predict_overlay.py`
- `docs/ml-experiments/v8.x_vega_niigata1000_phase*.md`

検証:

- polarisのP/W/ARに専門スコアをstackしない。
- overlayとして `specialist_score` を別ルートで表示/フィルタ。
- polarisが低評価、市場も低評価、専門スコアだけ高い馬を抽出。

採用条件:

- 全レース汎用モデルの特徴量に混ぜない。
- 特殊条件だけでOOS継続監視。

### H7. 出遅れ耐性・接戦騎手という「癖/技能」シグナル

**仮説**: 市場は単純な過去着順や騎手人気を織り込むが、出遅れ耐性や接戦処理能力までは粗い。

検証候補:

- 出遅れ率が高いが、出遅れ時の巻き返しが強い馬。
- 出遅れ癖がある人気馬の危険判定。
- 0.1秒以内の接戦に強い騎手。
- 接戦騎手の成長トレンド。

既存入口:

- `ml/features/slow_start_features.py`
- `builders/build_slow_start_analysis.py`
- `analysis/jockey_close_finish.py`
- `web/src/app/analysis/jockey-close-finish/page.tsx`

検証:

- まず特徴量投入ではなく、既存予測結果に後付けでクロス集計。
- `gap>=N` に対して改善するか、人気馬消しに効くかを見る。

### H8. 調教/CID/状態系の扱いを「P専用・W除外・AR除外」で再設計

**仮説**: 状態系は予測精度に強いが、市場にも織り込まれやすく、投入先を誤るとギャップを消す。

既存知見:

- JRDB CIDは精度を大きく改善した。
- ただしCID/LS系はW ROIを悪化させたためP専用へ移した経緯がある。
- CK_DATAは過去にMARKET扱いが妥当という結論があった一方、現行コードでは独自分析としてVALUE復帰している。

検証:

- CK系をP/W/ARそれぞれでON/OFF。
- CID/LSをP専用、W専用、AR専用、全除外で比較。
- 状態系が「市場一致」か「穴検出」かをセグメント別に見る。

採用条件:

- Wの平均人気が下がりすぎない。
- `gap>=6` の件数とROIが維持/改善。

### H9. Placeモデルは馬券対象ではなく「候補発見器」に寄せる

**仮説**: 複勝は当たりやすいがオッズが低く、買うとROIを押し下げる。一方、Pモデルは単勝穴候補発見には使える。

根拠:

- `feature_engineering_strategy.md`: Place ROI < 100% が常態化。
- `v5.6`: gapはPlace modelベースでも単勝ROI改善に効く。
- `v8.4`: P Top1はW Top1よりROIが良いセグメントがある。

検証:

- Pモデルを「単勝候補抽出」に限定。
- 実際に買う条件は `gap + W EV + ARd + セグメント`。
- 複勝は原則買わず、危険馬/軸候補評価に使用。

### H10. レースセグメント別の買い分け

**仮説**: 全レースで同じ閾値を使うと、市場効率が高い領域に利益を食われる。

優先検証セグメント:

- 重賞/Listed/OP
- 新馬/1勝クラス
- odds 5.1-20
- 17頭以上
- 芝短距離、芝長距離
- venue 02/09/10などP Top1 ROIが高い会場
- 低ROIの騎手/厩舎Top1除外

既存入口:

- `ml/analyze_polaris_weakness.py`
- `data3/analysis/polaris_segments/*/summary.md`
- `web/src/app/analysis/polaris-segments/page.tsx`

採用条件:

- セグメントを増やしすぎない。
- まずは「買わない条件」を定義し、損失セグメントを削る。

### H11. odds/time-to-postの市場変化を活用する

**仮説**: 現在の事前オッズ特徴量/EVは市場の最終変化を十分に使えておらず、オッズ変動そのものにギャップがある。

検証:

- 予測時点オッズ、直前オッズ、確定オッズの差分。
- モデル高評価なのに直前で売れていない馬。
- 逆にモデル低評価なのに急に売れた人気馬の危険判定。

既存入口:

- `core/odds_db.py`
- `ml/predict.py`
- `ml/market_divergence_analysis.py`

注意:

- 確定オッズを学習に使うとリークになる。
- live運用では取得時刻を固定し、バックテストも同条件にする。

### H12. LightGBM objectiveの見直し

**仮説**: 二値分類AUC最適化では市場ギャップ最大化と目的がずれている。

候補:

- LambdaRank: レース内順位を直接学習。
- pairwise: 人気馬 vs 穴馬の相対勝負に寄せる。
- sample weight: 高オッズ的中、gap候補、低人気好走に重み。
- custom target: `market_residual = outcome - implied_prob` 的な市場残差を学習。

既存入口:

- `ml/experiment_lambdarank.py`
- `ml/experiment.py`
- `docs/ml-experiments/h21_track_split.md`

注意:

- 市場残差モデルはデータスヌーピングとキャリブレーション崩壊に注意。
- まずは現行P/W/ARとは別モデルで並列評価する。

---

## 6. 優先順位

### Tier 1: すぐ検証

| 優先 | 仮説 | 理由 |
|---:|---|---|
| 1 | H1 MARKET/VALUE再監査 | 現在の問題に最も直結。既存コードでアブレーション可能。 |
| 2 | H2 P/W/AR乖離パターン | 既存結果に強い示唆があり、実装より分析で進められる。 |
| 3 | H3 Selective再検証 | 既に高ROI候補があり、OOS延長で判断できる。 |
| 4 | H10 セグメント別買い分け | 既存 `polaris_segments` の結果を活用できる。 |
| 5 | H9 Placeを候補発見器化 | 戦略設計の見直しで、モデル再学習なしに試せる。 |

### Tier 2: 小さく追加検証

| 優先 | 仮説 | 理由 |
|---:|---|---|
| 6 | H4 RPCI/33ラップ | 既に効果/失敗が両方あり、上位特徴だけ再検証する価値が高い。 |
| 7 | H5 Ratingレベル差 | 降格ローテ一括投入ではなく、gap交差なら再評価余地がある。 |
| 8 | H8 状態系の投入先再設計 | CID/CKの扱いが現在の市場寄り問題に関係しそう。 |
| 9 | H7 出遅れ/接戦 | 市場が粗く扱いそうな癖・技能で、後付け分析が可能。 |

### Tier 3: 中長期

| 優先 | 仮説 | 理由 |
|---:|---|---|
| 10 | H6 ニッチ専門overlay | 特殊条件で強いが、対象レースが限定される。 |
| 11 | H11 odds/time-to-post | ライブ運用とバックテスト条件の整備が必要。 |
| 12 | H12 objective見直し | 研究コストが高い。現行の評価基盤を固めてから。 |

---

## 7. 次に作るべき分析レポート案

### Report A: MARKET/VALUE監査

出力:

- 特徴量カテゴリごとのON/OFF結果
- AUC/ECE
- rank相関
- favorite一致率
- gap件数
- gap×EV×ARd ROI CI

対象カテゴリ:

- CK調教
- JRDB状態/CID
- JRDB過去指数
- speed
- comment
- rating/rotation
- jockey

### Report B: P/W/AR Divergence Map

出力:

- P/W/ARのrank相関
- 不一致パターン別ROI
- 平均人気/平均オッズ
- セグメント別の不一致ROI
- SHAP/gain差分

### Report C: Selective OOS更新

出力:

- 2026-04以降の解決済み成績
- baseline / not_fav1 / gap>=3 / gap>=4
- 月別P&L
- レースグレード別
- odds帯別

### Report D: analysis指標クロス

出力:

- `gap>=6` 候補に対するRPCI適性、level_drop、出遅れ耐性、接戦騎手のクロス集計
- 単体効果ではなく `gap` 条件内のliftを見る

---

## 8. 採用/不採用の判断基準

### 採用候補

- ROIが上がり、CI下限が改善する。
- 平均人気が過度に下がらない。
- gap候補数が維持/増加する。
- 月別P&Lが一発依存ではない。
- OOSでbaselineより優位。

### 不採用候補

- AUCは上がるが、favorite一致率が上がり、平均オッズが下がる。
- gap候補数が大幅に減る。
- W/P/ARの乖離を消す。
- 特定の高配当1件だけでROIが成立する。
- gain importanceは高いが、市場相関も高い。

---

## 9. 参照した主な資料

- `docs/ml_experiment_log.md`
- `docs/ML_SOURCE_GUIDE.md`
- `docs/models_and_features.md`
- `docs/feature_engineering_strategy.md`
- `docs/model_divergence_analysis.md`
- `docs/ml-experiments/README.md`
- `docs/ml-experiments/v5.6_ev_gap_analysis.md`
- `docs/ml-experiments/v8.1_polaris2_jrdb5_cid.md`
- `docs/ml-experiments/v8.2_polaris2.2_ar_stack.md`
- `docs/ml-experiments/v8.3_polaris2.3_margin_adjusted.md`
- `docs/ml-experiments/v8.4_polaris2_segments_and_selective.md`
- `data3/analysis/polaris_segments/polaris_2.0_v1/summary.md`
- `data3/analysis/polaris_segments/polaris_2.0_w_v1/summary.md`
- `data3/ml/models/polaris/live/meta.json`
- `analysis/niigata1000/*`
- `web/src/app/analysis/rpci/page.tsx`
- `web/src/app/analysis/rating/page.tsx`
- `ml/experiment.py`
- `ml/predict.py`
- `ml/market_divergence_analysis.py`
- `ml/analyze_market_signal.py`

---

## 10. 深掘りで出てきた疑問点（要確認）

### Q1. 「市場に近づいた」の定義は定量化できているか

現状は「平均人気が下がる」「favorite一致率が上がる」で判断しているが、これだけだと粗い。

追加で必須化したい指標:

- `rank_p`, `rank_w`, `ar_rank` と `odds_rank` の Spearman 相関
- `dev_gap` 分布の平均/分散/歪度
- `gap>=N` の件数推移（月次）
- odds帯別の top1 選択偏り

判断の再現性を上げるため、**「市場寄り化スコア」**を1つ定義するのがよい。

### Q2. 仮説数が多い中で多重検定バイアスをどう抑えるか

本ドキュメントの仮説は有効だが、同時に多数検証すると「偶然当たり」を拾いやすい。

再考ポイント:

- Tier 1の中でも主仮説を2-3本に絞る。
- 事前に「採用基準」「失敗基準」を固定する。
- 検証期間Aで選び、期間B/OOSで再評価する。
- p値を使うなら FDR/BH か、最低でも Holm 補正を採用する。

### Q3. キャリブレーションは時系列で崩れていないか

`ml/analyze/check_calibration.py` はあるが、採用判断への組み込みがまだ弱い。

再考ポイント:

- W/Pともに odds帯別 ECE を毎月記録する。
- `cal_p`, `cal_w` の再学習タイミングを固定ルール化する（例: 四半期更新）。
- 校正改善がROI改善に繋がるかを別途追跡する（ECE改善だけで採用しない）。

### Q4. バックテスト期間分割は十分に「将来未知」を再現しているか

`ml/analyze/backtest_walkforward.py` があるのは強いが、全施策に標準適用されていない可能性がある。

再考ポイント:

- 全新施策で walk-forward を必須化。
- 月別中央値ROI・勝ち月率を主要指標にする。
- 1-2本の高配当に依存していないかを必ず確認する。

### Q5. liveでのオッズ取得時刻と検証時の整合は取れているか

`H11` で触れている通り、確定オッズや直前オッズ混在はリーク/過大評価の原因になる。

再考ポイント:

- 予測時刻（例: 発走30分前/10分前）を固定し、その時点オッズだけで評価する。
- backtestでも同時点オッズを使えるようにデータを保存する。
- 直前変化率は特徴量にするが、目的変数と時刻順が逆転しないようにする。

### Q6. セグメント戦略は「薄い高ROI」に偏っていないか

重賞や特定騎手などはROIが高く見えるが、低サンプルが多い。

再考ポイント:

- 最低件数（例: 80 bet以上）を満たさないセグメントは観測扱い。
- セグメント採用は `件数×CI幅×月次安定` の3軸で評価する。
- 「除外条件」は強いが、除外しすぎてbet機会が枯れないかも同時評価する。

---

## 11. 再考したほうが良いポイント（方針修正）

### 11.1 「特徴量追加」より「配当分布管理」を先に置く

現状の主要失敗は、当たりを増やしても低配当に寄ること。  
先に管理すべきは次の2点。

- 選択馬の odds帯分布
- 1人気/2人気集中率

提案:

- 施策ごとに「配当分布監視」を固定レポート化する。
- 低オッズ集中が一定閾値を超えたら自動で不採用フラグ。

### 11.2 P/W/ARの役割を明示分業し、混ぜない

`v8.2` の失敗が示す通り、統合すると収益源の乖離が消える。

提案:

- P: 候補抽出（広く拾う）
- W: 実際の勝ち確率評価
- AR: 能力・余力・危険度フィルタ
- 最終意思決定は「3モデルの一致」ではなく「ズレの構造」で行う

### 11.3 低importance特徴量を機械的に削らない

既存知見で `importance低いがROI寄与` があるため、gain下位削除は危険。

提案:

- feature dropは単体ではなく「カテゴリ単位」か「市場相関単位」で行う。
- 削除実験は必ず複数期間で再現確認する。

### 11.4 「高ROI戦略」ではなく「運用可能戦略」を評価する

高ROIでも件数が少なすぎると現場運用で再現しにくい。

提案:

- ROIだけでなく、月間bet数、最大DD、連敗長、資金変動も必須指標にする。
- `ml/ci_power_analysis.py` の観点を通常レポートへ統合する。

---

## 12. さらなる改善提案（本ドキュメント追記版）

### P1. Market Proximity Score（MPS）を導入する

目的: 「市場寄り化」を主観でなく数値で監視する。

案:

- 入力: `corr(rank_x, odds_rank)`, favorite一致率, 平均odds, gap>=N件数
- 出力: 0-100のスコア（高いほど市場に近い）

使い方:

- 新施策採用時にMPS変化を必ず記録。
- MPS悪化かつROI改善なしなら自動不採用。

### P2. 仮説ごとのプリレジ（事前登録）テンプレートを作る

目的: 後付け解釈と多重検定の抑制。

テンプレ要素:

- 仮説ID
- 変更点（feature/strategy）
- 主要評価指標（1-2個）
- 副作用監視指標（2-4個）
- 採用基準
- 不採用基準
- 検証期間A/B

保存先案:

- `docs/ml-experiments/hypothesis_registry.md`

### P3. 「否定できる実験」を先に設計する

目的: 成功ケースだけ拾うバイアスを避ける。

提案:

- 施策ごとに「これが起きたら失敗」を先に定義。
- 例:
  - favorite一致率 +10pt以上
  - gap>=6件数 -25%以上
  - 月次中央値ROI < 100
  - CI幅が基準を超える

### P4. セグメント戦略を2層化する

目的: 過剰条件化で件数が枯れる問題を避ける。

2層案:

- Layer A（安定土台）: 広い条件（例: gap>=6,m<=0.8）
- Layer B（高配当上乗せ）: Selective/not_fav1/gap>=4など

運用:

- 予算をA/Bで固定比率配分し、Bの暴れを制御。
- Aのみでも破綻しない設計にする。

### P5. 予測確率より「順位差の確率化」を検討する

目的: gapを閾値ルールから確率評価へ進化させる。

案:

- `P(gap>=k | features)` を二値モデルで学習
- `P(undervalued | features)` を別ヘッドで学習

効果:

- gap閾値固定の硬さを緩和し、レースごとに柔軟化できる。

### P6. オッズ時系列特徴量は「先行取得済み範囲」のみ採用

目的: 漏洩なくH11を実装する。

案:

- t-60, t-30, t-10 の3点スナップショット
- 変化率、加速度、出来高代理指標（取得可能なら）を作る
- 学習時も推論時も同じ時刻窓に限定

### P7. 改善施策の標準レポートを固定フォーマット化

目的: レビュー品質を毎回一定化。

必須ブロック:

1. 変更内容
2. AUC/ECE
3. MPS（新規）
4. gap分布
5. odds分布
6. ROI + CI
7. 月次推移
8. セグメント寄与
9. 採用/不採用判定

---

## 13. 直近2週間の実行提案（最小実行セット）

### Week 1（分析中心）

1. `H1` のMARKET/VALUE監査をカテゴリ単位で実行  
2. `H2` のP/W/AR乖離パターンを再算出  
3. `MPS` を試験実装し、過去3バージョンで比較  
4. `walk-forward` で月次中央値ROIを算出

### Week 2（戦略中心）

1. Layer A/Bの2層セグメント戦略をバックテスト  
2. Selective v3のOOS更新（最新月まで）  
3. odds時刻固定の検証雛形を作成（t-30基準）  
4. 採用判定会: 「ROIだけでなくMPSと安定性」で意思決定

---

## 14. 追記後の要約

本レビューの方向性（乖離重視）は妥当。  
追加で最も重要なのは次の3点。

1. **市場寄り化の定量監視（MPS）**
2. **多重検定・探索バイアスを抑える運用設計**
3. **ROIだけでなく再現性（walk-forward、月次中央値、CI幅）を採用基準へ固定化**

これを入れることで、「当たった実験を選ぶ」から「再現できる改善を積む」へ移行できる。
