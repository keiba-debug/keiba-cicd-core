# コース辞典（`/demo/course`）見直しメモ（ML連携観点）

作成日: 2026-06-11  
対象:
- `web/src/app/demo/course/page.tsx`
- `web/src/data/course-data.ts`
- `web/src/lib/course-bias.ts`
- `ml/features/base_features.py`
- `ml/features/track_bias_features.py`

## 1. 先に結論（優先度順）

1. **コース辞典は“表示用静的データ”で、学習資産としては未接続**  
   `course-data.ts` の `innerAdvantage` / `styleAdvantage` が ML へ直接流れていない。
2. **更新性が弱い（手動更新前提）**  
   データソースは `2021-2026` 固定の記述で、再計算パイプラインがUIから見えない。
3. **信頼度メタが不足**  
   point推定中心で、CI・安定性・ドリフトがないため ML投入時の安全性が担保しづらい。
4. **型と実データにギャップ**  
   `kaisaiProgression` を型定義しているが実データは0件。開催進行バイアスがUIで活かされていない。

## 2. 現状確認（実データ・実装）

- `/demo/course` は `ALL_COURSES` を直接参照するクライアントページ。
- `course-data.ts` は静的配列ベタ持ち。
- 件数確認:
  - `course_rows`: 77
  - `conditionBias` 設定あり: 3コース
  - `kaisaiProgression` 設定あり: 0コース
- データコメント:
  - 「ソース: analyze_baba_report.py」
  - 「2021-2026, 229,343エントリ」

### ML側で既に使っているもの

- `first_corner_dist`（`ml/features/base_features.py`）
- `straight_distance`, `height_diff`（同上）
- 当日バイアス/前崩れ系（`ml/features/track_bias_features.py`, KAA/SED由来）

### ML側で使っていないもの

- `course-data.ts` の `innerAdvantage` / `styleAdvantage` / `conditionBias`（固定集計値）

## 3. 主な課題

### 3.1 辞典データの学習未接続

UIの主役である「コース固有バイアス強度」が学習特徴量に乗っていない。  
現在の ML はレース当日KAAや履歴SED中心で、辞典側の“長期コース事前分布”を使っていない。

影響:
- 画面で得た洞察がモデル改善に還元されない。
- 「見えるが使えない」状態になりやすい。

### 3.2 静的埋め込みによる陳腐化リスク

`course-data.ts` は手編集ベース。開催進行や改修（例: 京都改修、仮柵運用）に追従しにくい。

影響:
- UI表示と実際の最近傾向が乖離する可能性。
- ML入力に使う場合はリーク以前に“古い真実”問題が起きる。

### 3.3 不確実性の欠落

`innerAdvantage` や `styleAdvantage` に信頼区間がない。  
特にサンプル小のコース（数百件）で値を同列比較してしまう。

影響:
- ノイズをシグナルと誤認しやすい。
- 特徴量化時に過学習トリガーになりやすい。

### 3.4 開催進行情報の未活用

`CourseInfo` 型に `kaisaiProgression` があるが、実データが空。

影響:
- docsの主要知見（開催前半→後半のバイアス変化）がUI/ML両方で死蔵される。

## 4. ML接続の改善方針

## 4.1 フェーズ1（短期）: 辞典データの品質メタ追加

`course-data.ts`（または生成JSON）に次を追加:

- `innerAdvantage_ci95_low/high`
- `styleAdvantage_ci95_low/high`
- `stability_flag`（例: sample>=1200 など）
- `last_updated_at`

UIで:
- 低信頼コースに警告バッジ
- 並び替えに「効果量 × 信頼度」を追加

## 4.2 フェーズ2（中期）: 生成パイプライン化（静的TS脱却）

推奨構成:

1. `analyze_baba_report.py` 拡張で `course_bias_dictionary.json` を出力
2. `web` はJSON読込へ切替（TSベタ持ちを縮小）
3. 管理画面に「コース辞典再計算」導線追加

これでUIと分析ロジックを単一ソース化できる。

## 4.3 フェーズ3（中期）: PIT安全な学習特徴量へ接続

固定値をそのまま使わず、時点整合版を作る:

- `course_prior_inner_adv_t-1`
- `course_prior_style_adv_t-1`
- `course_prior_front_top3_t-1`
- `course_prior_condition_bias_{dry,std,wet}_t-1`

馬側との交差:

- `draw_group × course_prior_inner_adv_t-1`
- `running_style × course_prior_style_adv_t-1`
- `pace_prediction × course_prior_front_top3_t-1`

## 5. 実装チケット案

1. `ml/analyze_baba_report.py`
   - コース辞典用JSON出力とCI算出
   - 開催進行 (`kaisaiProgression`) をコース単位へ集約
2. `web/src/data/course-data.ts` → 生成物読込化
3. `web/src/app/demo/course/page.tsx`
   - 信頼度表示、更新時刻表示、開催進行パネル
4. `ml/features/`（新規または既存拡張）
   - PIT版コース事前分布特徴の導入

## 6. 最小実行セット（まず1スプリント）

最初は以下だけで十分:

- A. `course-data` に CI + 更新時刻 + stability を追加
- B. `/demo/course` に低信頼警告と開催進行表示を追加
- C. ML投入前に後付け検証  
  `gap>=k` 条件で `draw/style × course_prior_bias` のROI差分を確認

この順で進めると、UI改善とML接続の両方を低リスクで前進できる。

