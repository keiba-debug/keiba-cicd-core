# 1番人気裏切り予想 プロジェクト構想 (favorite-betrayal)

ステータス: 構想記録 (Session 141) / 本格着手は次セッション以降 / 関連: [[niche-specialist-strategy]], [[feedback_betting_philosophy]], [[course-bias-alert]], 22_AI_MARKS_DESIGN.md, niigata-1000m-project
発端: Session 141。AI印 Step2 実機 apply → 自動投票が「危(過剰人気)」かつ「穴注目」が同時点灯した京都11R①(しかも勝った)をふくだが指摘 → 現行「危」マークの矛盾発覚 → ふくだ「危険は作り直したい。展開・枠・コース適性で人気を裏切る馬を見つける機能に」「単独プロジェクトとして1番人気裏切りモデルを作るのもあり」。

---

## 0. 何を作るか (ビジョン)

**「1番人気(過剰人気馬)が飛ぶ」を、具体的な理由とともに予測する**独立プロジェクト。

現行の「危」マーク (web `HorseEntryTable.tsx` isDanger = odds≤8 & ARd<53 & P%<15) は **単なる数値フィルタ**で、ふくだの求める「危険」と本質的にずれている:
- 現行: 「人気なのに能力指標が低い」= ただの過剰人気の機械判定。
- ふくだの「危険」: **人気を裏切る具体的な文脈的理由**があるのに市場が織り込めていない馬。
  - 例1 (脚質×隊列): いつも逃げて強い馬が、今回は逃げ馬が多くて逃げられそうにない。
  - 例2 (枠×コース適性): 内枠が苦手な馬が内枠に入っているのに過剰人気。

賭け哲学整合 ([[feedback_betting_philosophy]]): 「自分にできない買い方=人が見落とす材料を拾う」。1番人気の崩壊は**最も妙味が大きい領域**(人気の逆を突く)。Themis/確率論の本流。[[niche-specialist-strategy]] のニッチ特化と同系統。

## 0.1 なぜ現行「危」を直さず新プロジェクトにするか
- 現行「危」と「穴注目」(market_signal) が**同じ「オッズ下落=人気化」を真逆に解釈**して矛盾(危=過剰人気/消し、穴注目=スマートマネー/買い)。対症療法では筋が悪い。
- 「人気を裏切る理由」は脚質・隊列・枠・コース適性など**多要因**。単一フィルタでなく、要因を積み上げる/モデル化する器が要る → 独立プロジェクトが適切。

---

## 1. 進め方 (ふくだ確定: 分析フェーズから)

**いきなりモデル化しない。まず「裏切りの実態」をデータで見る。** (メモリ教訓: 小サンプル×多条件分け=疑似科学。何が効くか先にデータで)

| Phase | 中身 | 成果物 |
|---|---|---|
| **P0 実態分析 (次セッション最初)** | 過去データで「1番人気が3着外(飛んだ)」レースを集計。脚質代理・距離・コース・頭数・ARd・odds_move 等で裏切り率がどう変わるか。ふくだ2構想(脚質×隊列, 枠×コース)のどの要因が裏切りを予兵するか検証 | 裏切り率ベースライン + 要因別クロス集計レポート |
| **P1 ルールベース検出** | P0で効いた要因をルール化し「裏切り候補」を抽出。web/印で可視化。説明可能・すぐ動く | `betrayal_features.py` 相当 + 表示 |
| **P2 ML化 (任意)** | 「1番人気が3着外」を目的変数に LightGBM 分類器。Stars/Nebula 体系の新モデル。walk-forward + キャリブレーション | `model_betrayal` 相当 |
| **P3 馬券/印連動** | 裏切り検出を AI印(消し材料)・hole_seeker の軸除外・券種選択に統合 | 自動投票への接続 |

---

## 2. データ資産棚卸し (Session 141 Explore 調査結果: 既存70% / 新規30%)

### ✅ 既存で足りる
| 領域 | 資産 | 場所 |
|---|---|---|
| 脚質判定 | `running_style_features.py` (front_runner_rate, avg_first_corner_ratio, closing_strength, pace_sensitivity, position_gain_last5) | `keiba-v2/ml/features/` |
| ペース/隊列 | `pace_features.py` (RPCI, dominant_trend_v2_enc), `closing_race_features.py` | 同上 |
| 枠順バイアス | `course-bias.ts` getDrawGroup/getCourseBiasAlert [Session113], niigata1000 verify_01_frame.py (枠別3着内率集計の汎用フレーム) | web/src/lib, analysis/niigata1000 |
| コース事典 | `course-data.ts` ALL_COURSES (全100+コース innerAdvantage / styleAdvantage / babaAnalysis) | web/src/data |
| 隊列パターン | niigata1000 4象限分類(テン速遅×末脚速遅) | analysis/niigata1000/verify_02_running_style.py |

### ❌ 新規に要る
1. **馬の「枠順適性」スコア**: 過去走の内枠成績 vs 外枠成績 (inner_frame_affinity)。最低5-10走の枠別サンプル。集計先 `data3/masters/frame_affinity_*.json` 候補。
2. **隊列パターンの汎用化**: niigata1000 は直線専用(pre_2f)。corners がある全コースで「逃げやすさ=先行馬密度×ペース圧力」を定量化。
3. **KYI「展開予想脚」パーサー**: JRDB KYI に展開予想脚フィールド(詳細仕様未確認)。あれば公式予測値が使える。`core/jravan/kyi_parser.py` 候補。

### ⚠️ 重要な制約 (Session 141 確認済)
- **predictions.json に出力されている脚質特徴量は `avg_first_corner_ratio` と `closing_strength` のみ**。front_runner_rate 等の充実特徴量は **features モジュールにはあるがモデル内部で消費され predictions に書き出されていない**。P0分析や P1検出で使うには **predictions への書き出し追加 or 再計算が要る**。
- **枠番(wakuban)は predictions に無い**。個別 race JSON (`race_{rid}.json`) の entry に `wakuban` あり → race_id で join 可能。
- popularity は朝の確定前は 0。**1番人気判定は `odds_rank` を使う**(odds_rank=1)。

---

## 3. P0 分析の足場 (次セッションがすぐ動ける状態)

- **データ取得方法**: `ml.utils.race_io.load_race(day_dir, rid)` で結果(finish_position)を取得し predictions と突合 (`analyze_market_signal.py` collect_data() と同パターン)。障害除外は `ml.utils.filters.is_obstacle`。
- **サンプル規模 (Session 141 確認)**: 2026年 predictions 46日 / **1423レース** / 1番人気(odds_rank=1)が各レース一意に取れる(同オッズ重複ゼロ)。裏切り分析の母数 ≈ 1423。
- **既に書いた足場スクリプト**: `keiba-v2/ml/analyze/backtest_danger_alert.py` (現行「危」ロジックの実成績 backtest。「危=飛ぶか」「危∩穴注目の矛盾はどちらが正しかったか」「odds_move改善案」を出す)。**未実行**。P0 の最初にこれを回すと現行危のベンチマークが取れる。
- **P0 で見るべきクロス集計**:
  - 1番人気の裏切り率(3着外率)ベースライン。
  - 距離別 / コース別 / 頭数別 / track_type別。
  - avg_first_corner_ratio (脚質代理) 別: 逃げ・先行タイプの1番人気は隊列次第で飛びやすいか。
  - odds_move 別: スマートマネーが入った1番人気 vs 見限られた1番人気。
  - ARd / closing_strength / num_runners の裏切りとの相関。

---

## 4. コードネーム候補 (Stars/Nebula 天体名体系 [[multi-model-naming]])
- 「過剰人気の崩壊/恒星の終焉」を連想させる名前を提案予定。候補: **supernova** (超新星=明るく見えた星の爆発的終焉), **collapse**, **icarus** (高く飛びすぎて墜ちる)。次セッションでふくだと確定。

---

## 5. 次セッションのスタート手順
1. P0 実態分析を回す: まず `python -m ml.analyze.backtest_danger_alert` で現行危のベンチ → 新規に1番人気裏切り率の要因別集計スクリプトを書く。
2. 「何が裏切りを予兵するか」をデータで確定してから P1 ルール設計。
3. コードネーム確定 → モデル命名体系に登録。

## 6. 本セッションで保留した関連タスク
- **AI印⇔買い軸連動 (markSet=8)**: 案C(新markSet・軸+相手・ledger起点)でシズネ CONDITIONAL_GO 済。設計は `23_AI_MARK_VOTE_SYNC_DESIGN.md`。本プロジェクトとは別だが、裏切り検出は将来「買い軸の除外材料」として接続しうる。
