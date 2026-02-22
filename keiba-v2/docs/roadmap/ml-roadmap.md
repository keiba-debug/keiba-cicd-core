# ML開発ロードマップ

モデル精度向上・新モデル構築・特徴量設計に関する開発候補の管理。

> **実装済み特徴量の詳細**: `knowledge/features.md`
> **実験ログ**: `ml-experiments/README.md`
> **特徴量拡張の詳細計画**: `knowledge/insights/model/next_features_and_targets.md`
> **Web機能の開発候補**: `roadmap/web-roadmap.md`

---

## 現在の到達点（v5.0 / 2026-02-15時点）

- **Model A** (Win): AUC 0.8241, ECE 0.0041
- **Model B** (Place/Value): AUC 0.7809, ECE 0.0047
- **Model WV** (Win-Value): 市場独立の勝率推定
- **特徴量数**: A=78, B=72（base/past/trainer/jockey/running_style/rotation/pace/speed/training）
- **VB戦略**: gap≥3で複勝ROI 117%, gap≥5で137%
- **単複Kelly配分**: 実運用中（FF CSV → TARGET連携）
- **収支実績**: 月間ROI 180.9%（2026-02-08時点）

---

## Sprint A: 特徴量追加（精度向上の即効性が高いもの）

### A-0. 血統特徴量の新規追加 ⭐最高優先（最大の構造的欠落）
- **現状**: 血統情報が**一切使われていない**（features.md評価: ★☆☆☆☆）
- **影響**: 若馬（キャリア2-3戦）は過去走特徴量がほぼNaN。血統が唯一の能力推定手段。2-3歳馬はフルフィールドの30-40%
- **候補特徴量**:
  - `sire_distance_top3_rate`: 父産駒の距離帯別複勝率
  - `sire_track_type_top3_rate`: 父産駒の芝/ダート別複勝率
  - `sire_track_cond_top3_rate`: 父産駒の馬場状態別複勝率
  - `broodmare_sire_top3_rate`: 母父産駒の全体複勝率
- **データ**: UM_DATAから血統コード取得済み。種牡馬別集計テーブルの事前構築が必要
- **モジュール**: `blood_features.py` 新規作成
- **難易度**: 中
- **参考**: `ml-experiments/review_ml_accuracy_and_betting_strategy.md` 2-1.A

### A-1. CK_DATA lapRank特徴量 ⭐高優先
- **概要**: JRA-VAN調教データの加速ラップ評価(SS/S+/A+/A/B+/B/C)をML特徴量化
- **現状**: WebViewer表示用のみ、ML未活用
- **実装先**: `training_features.py`
- **候補特徴量**:
  - `ck_best_lap_rank`: 直近N本の最高ラップランク（SS=7, S+=6, ...）
  - `ck_lap_rank_count_high`: SS/S+の本数
  - `ck_latest_lap_rank`: 直近1本のラップランク
- **期待効果**: 調教の質を直接評価。現在の`oikiri_*`より情報量が多い
- **難易度**: 低（training_summary.jsonにlapRank既存）

### A-2. ペース予測（脚質分布 + tenkai_data） ⭐高優先
- **概要**: レース内の逃げ馬頭数×脚質分布からペースを事前予測
- **候補特徴量**:
  - `predicted_pace`: レース内逃げ馬頭数ベースのペース予想値
  - `pace_advantage`: 脚質×予想ペースの有利度
  - `front_runner_count`: 同レースの逃げ脚質馬数
  - `tenkai_position`: keibabook展開予想の配置（逃げ/好位/中位/後方）
  - `tenkai_pace_forecast`: keibabook予想ペース（H/M/S）
  - `position_vs_style_match`: 予想ポジションと過去脚質の一致度
- **現状のギャップ**: 現行ペース特徴量は「過去レースのRPCI」。tenkai_dataは「今回のレースの展開」を直接予測した情報で質が異なる
- **期待効果**: Model Bの重要度トップがavg_finish_last3 → 展開系特徴量不足の解消
- **難易度**: 中

### A-3. 前走レースレベル + クラス変動 ⭐高優先
- **問題**: 「G1の5着」と「未勝利の5着」が同じ `avg_finish_last3 = 5.0` になる
- **候補特徴量**:
  - `prev_race_avg_rating`: 前走出走メンバーのkb_rating平均
  - `prev_race_max_rating`: 前走メンバーのrating最高値
  - `prev_race_rating_rank`: 前走内での自馬rating順位
  - `class_change`: 前走クラスとの差（+1=昇級, -1=降級）
  - `class_time_gap`: 今走クラス基準タイム - 前走クラス基準タイム
- **期待効果**: 「降級ローテ」の自動検出 + 前走レベル考慮の着順評価
- **データ**: kb_ext_indexのratingフィールドは既にメモリ上にあり、引数追加のみで実装可能
- **難易度**: 低〜中

### A-4. 騎手/調教師 point-in-time化 + 直近フォーム ⭐高優先（リーク修正）
- **問題**: 現在のtrainers.json/jockeys.jsonは**全期間の累積成績**。2020年の予測に2025年の成績が混入するリーク構造
- **修正**: `race_date < prediction_date` で区切った時点成績を使用
- **追加特徴量**:
  - `jockey_recent_win_rate_30d`: 騎手の直近30日勝率
  - `trainer_recent_top3_rate_30d`: 調教師の直近30日複勝率
  - `jockey_form_trend`: 直近の上昇/下降トレンド
- **影響**: 修正するとAUCが下がる可能性あるが、**真の汎化性能**が見える
- **難易度**: 中（point-in-time統計の構築が必要）

### A-5. 自作スピード指数 ⭐中優先
- **概要**: keibabookスピード指数の重要度が低い(600-800) → 独自構築
- **計算式**: `(基準タイム - 走破タイム + 馬場補正 + ペース補正) × スケール`
- **データソース**: SE_DATA走破タイム + rating_standards基準タイム + ラップ + 馬場状態（全て取得済み）
- **メリット**: 補正ロジックが完全に透明、ML特徴量としても解釈可能
- **詳細**: `IDEAS_BACKLOG.md` の自作タイム指数セクション
- **難易度**: 高

---

## Sprint B: 組合せ馬券モデル（三連単への道）

### B-0. LambdaRank（ランキング学習）⭐高優先（三連単基盤技術）
- **現状**: `is_top3` の二値分類。「接戦の4着」と「大差の4着」が同じ負例。情報ロスが大きい
- **提案**: LightGBMの `objective='lambdarank'` でレース内順位を直接学習
- **relevanceスコア**: 1着=5, 2着=4, 3着=3, 4着=2, 5着=1, 6着以下=0
- **メリット**:
  - 着順の相対関係（1着>2着>...）を直接学習
  - 出力スコアをHarville公式で組合せ馬券確率に自然変換
  - **三連単EVエンジン(B-4)の最も現実的な基盤**
- **評価指標**: NDCG@3, NDCG@5
- **難易度**: 中（LightGBMのobjective変更のみ）
- **参考**: `ml-experiments/review_ml_accuracy_and_betting_strategy.md` 2-2.E

### B-1. 着順条件付き確率モデル ⭐最重要
- **概要**: P(2着B|1着A) × P(3着C|1着A,2着B) の推定
- **アプローチ候補**:
  - Harville近似: P(2着B|1着A) = P_B / (1 - P_A) — シンプルだがIIA仮定に問題あり
  - Henery修正: Harvilleのバイアスを補正する経験的手法
  - 専用モデル: 「A以外の中でのBの勝率」を直接学習
- **参考**: `knowledge/insights/market/harville_iia_critique.md`
- **前提**: 現在のModel A (Win確率) が基盤
- **難易度**: 高

### B-2. 馬連/ワイドEV計算 ⭐高優先（B-1の中間成果）
- **概要**: 2頭の組合せ確率 × オッズでEV算出
- **計算**: P(A∩B in top2) = P(A1着)×P(B2着|A1着) + P(B1着)×P(A2着|B1着)
- **データ**: mykeibadbに馬連/ワイドオッズテーブル確認必要
- **FF CSV**: 券種2(枠連), 3(馬連), 4(ワイド) 対応済み
- **難易度**: 中

### B-3. 三連複EV計算 ⭐中優先
- **概要**: 3頭の組合せ確率（着順不問）× オッズ
- **計算**: P(A,B,C all in top3) = Σ全着順パターンの確率
- **難易度**: 中（B-1があれば計算自体は直接的）

### B-4. 三連単EVエンジン ⭐最終目標
- **概要**: 全n(n-1)(n-2)通りの条件付き確率 × オッズでEV算出
- **詳細設計**: `knowledge/insights/market/market_structural_inefficiencies.md`
- **市場の歪み（利益源）**:
  - 均等配分バイアス: フォーメーション/ボックスの構造的問題
  - Favorite-Longshotバイアス: 大穴過剰人気
  - 条件付き確率の無視: 人間の認知限界
  - 着順入れ替えの軽視: A→B→CとA→C→Bの確率差
- **控除率**: 27.5%（最大）だが歪みが上回れば正のEV
- **計算量**: 18頭で4,896通り → Kelly配分で金額決定
- **難易度**: 高
- **前提**: B-1の着順条件付き確率モデル + 三連単オッズ取得

---

## Sprint C: モデルアーキテクチャ改善

### C-1. 芝/ダートモデル分離
- **詳細**: `knowledge/insights/model/model_separation_strategy.md`
- **現状**: 統合モデル（track_type特徴量で分岐）
- **期待**: 芝とダートで重要特徴量が異なる → 分離で精度向上
- **難易度**: 中

### C-2. 目的変数の拡張
- **詳細**: `knowledge/insights/model/alternative_target_variables.md`
- **候補**: 着差ベース（着順の連続値化）、着順分布予測（分位点回帰）
- **難易度**: 高

### C-3. Walk-Forward Validation
- **現状**: 固定3-way split（train:2020-23, val:2024, test:2025-26）
- **問題**: テスト期間1.5年で市場環境変化への耐性が未検証
- **提案**: 6ヶ月ウィンドウのローリング検証
- **メリット**: 各時期でのモデル安定性を確認、過学習の早期検出
- **難易度**: 中

### C-4. Stacking/Blending メタモデル
- **現状**: Model A/Bは独立。2モデルの組合せは `gap = odds_rank - value_rank` のみ
- **提案**: Model A/Bの予測を入力とする第3のメタモデル
- **期待**: 各モデルの強み（Aの精度、Bの市場独立性）を最適に統合
- **難易度**: 中

### C-5. Multi-target / Multi-task学習（長期）
- **提案**: is_top3 + is_win + 着差を同時学習（ニューラルネット）
- **根拠**: 現在の4モデル(A/B/W/WV)は独立学習。「勝てる馬は3着にも来やすい」の相関を未活用
- **前提**: PyTorch移行
- **難易度**: 高

### C-6. Transformer/Attention型モデル（長期）
- **提案**: 馬のキャリア全体をsequenceとして入力、Attentionで重要レースを自動選択
- **根拠**: 現在は「直近3走平均」「直近5走最高」の手動集約。Attentionなら「3走前のG1好走」と「直近の条件戦凡走」を自動重み付け
- **難易度**: 高

### C-7. SHAP予測インタビュー基盤
- **概要**: `pred_contrib=True` でSHAP値計算 → predict.pyに組み込み
- **詳細**: `knowledge/insights/model/prediction_interview_feature.md`
- **Phase 1**: 好材料/懸念材料 各3件をJSONに出力
- **Phase 2**: 特徴量名→日本語ラベル辞書
- **Phase 3**: Web連携（→ `web-roadmap.md` #3参照）
- **難易度**: 中

### C-8. マルチモデル/スペシャリストモデル ⭐中優先（将来）
- **概要**: 汎用モデル1本ではなく、条件別の専門モデルを複数保持。人間がレースごとに最適なモデルを選択して予測
- **パターン**:
  1. **スペシャリストモデル**: 新馬戦専用、障害戦専用、重馬場特化、短距離特化等
  2. **バージョン共存**: v3.5とv4.0を並行運用し、条件によって使い分け
  3. **並列実行比較（推奨）**: 全モデルを並列実行し、人間がレース条件を見て判断して選択
- **候補モデル**:
  - `maiden_model`: 新馬戦専用（血統特徴量重視、過去走特徴量なし前提。A-0血統特徴量が前提）
  - `steeplechase_model`: 障害戦専用（平地とは異なる適性・騎手評価）
  - `heavy_track_model`: 重馬場特化（馬場適性の重み増大）
  - `sprint_model`: 短距離特化（枠順・ゲート・テン3Fの重要度が高い）
- **運用フロー**:
  1. predict.py が全モデルを並列実行
  2. WebViewerで各モデルの予測を並列表示
  3. 人間がレース条件を見て「このレースは新馬戦モデルで」と選択
  4. 選択理由を事前記録 → レース後に事後検証（確証バイアス対策）
- **リスク**: 確証バイアス（自分の好みに合うモデルを選びがち）、サンプルサイズ不足（専門モデルは学習データが少ない）、メンテナンスコスト
- **対策**: モデル選択の記録 + 事後的に「全モデルの中で選んだモデルが本当に最良だったか」を自動検証
- **前提**: A-0（血統）、C-1（芝/ダート分離）の知見が基盤
- **難易度**: 高

---

## 検証が必要な仮説

| # | 仮説 | 検証方法 | 関連Sprint |
|---|------|----------|-----------|
| H1 | 三連単の本命決着組合せはEVが高い | 1-3番人気の三連単オッズ×的中確率 | B-4 |
| H2 | 着順入れ替えでEVが変わる | A→B→CとA→C→Bのオッズ比vs確率比 | B-4 |
| H3 | 多頭数レースほどEVが高い | 出走頭数別の回収率計算 | B-4 |
| H4 | 芝/ダート分離でAUC向上 | 分離モデルvs統合モデルのAUC比較 | C-1 |
| H5 | CK_DATA lapRankはML精度に寄与する | 追加前後のAUC/ROI比較 | A-1 |
| H6 | 血統特徴量は若馬の予測精度を大幅に改善する | 2-3歳馬のみのサブセットでAUC比較 | A-0 |
| H7 | point-in-time化でAUCは下がるがROIは上がる | 修正前後の比較 | A-4 |
| H8 | LambdaRankはis_top3二値より着順推定精度が高い | NDCG@3比較 | B-0 |
| H9 | gap≥2まで広げると分散ドラッグ減少で複利成長が向上 | バックテスト: gap別の対数リターン計算 | 戦略 |
| H10 | 複勝+三連単の低相関ポートフォリオはROI分散を下げる | 馬券種間相関の実測 | 戦略 |
| H11 | 新馬戦専用モデルは汎用モデルより若馬AUCが高い | 新馬戦サブセットでAUC/ROI比較 | C-8 |
| H12 | 人間のモデル選択は無選択（汎用モデル固定）より成績が良い | モデル選択記録の事後検証 | C-8 |

---

## 実装済み（アーカイブ）

- ✅ v3.1: 脚質8特徴量 + ローテ6特徴量 + ペース7特徴量
- ✅ v3.3: 調教12特徴量（KB印含む）
- ✅ v3.5: スピード指数5特徴量 + 3-way split + Brier/ECE評価
- ✅ v4.0: base追加(month/nichi) + past追加(finish_std/comeback) + rotation追加(jockey_change)
- ✅ v5.0: Win/Placeデュアルモデル + Model WV + EV計算
- ✅ Kelly Criterion資金配分（1/4 Kelly）
- ✅ VB戦略のバックテスト（芝→単勝、ダート→複勝）

---

**最終更新**: 2026-02-15
