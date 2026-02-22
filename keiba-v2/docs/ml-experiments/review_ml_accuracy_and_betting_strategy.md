# ML精度向上レビュー & 買い目・金額自動計算 将来構想

**日付**: 2026-02-15
**種別**: 現状レビュー + 将来アイデア集
**対象バージョン**: v4.1（82特徴量 / Model A AUC 0.8243 / VB gap>=3 PlaceROI 121.1%）

---

## Part 1: 現状ML機能の総合レビュー

### 1-1. アーキテクチャ評価

#### Dual Model設計（Model A / Model B）

**設計**: Model A（全82特徴量）とModel B（市場独立69特徴量）の2モデルでValue Betを検出する。

**評価**: **優秀**。市場効率仮説と情報の非対称性を巧みに利用した設計。

| 強み | 根拠 |
|------|------|
| 情報分離が明確 | MARKET_FEATURES定義で市場依存/独立を厳密に管理 |
| VB検出の理論基盤 | gap = odds_rank - value_rank は「市場が見落とした価値」の直接的指標 |
| CK_DATA分離判断（v4.1） | 調教情報が市場に織り込み済みと判明→Model A限定。ROI+0.9pt |
| ECE < 0.005 | 確率予測が実際の発生率とほぼ一致→EV計算の信頼性が高い |

| 改善余地 | 詳細 |
|----------|------|
| Model Bの上限 | AUC 0.7837は市場情報なしの限界に近い。特徴量追加だけでは大幅改善は困難 |
| 2モデルのみ | Stacking/Blendingで第3のメタモデルを検討する余地あり |
| 芝/ダート統合 | 現在は1つのモデルで芝・ダートを処理。分離モデルの検討が未実施 |

---

#### 特徴量エンジニアリング

**現状**: 9カテゴリ82特徴量。JRA-VAN + keibabook + CK_DATA + MySQLオッズの4データソース統合。

**評価**: **良好〜優秀**。主要な競馬ドメイン知識が網羅されている。

| カテゴリ | 数 | 完成度 | コメント |
|----------|-----|--------|----------|
| base（基本） | 15 | ★★★★★ | 必要十分。month/nichi追加(v4.0)で季節性もカバー |
| past（過去走） | 16 | ★★★★☆ | 安定度・盛り返し追加済。着差ベースの特徴量が未実装 |
| trainer/jockey | 7 | ★★★☆☆ | point-in-time未対応（時間的リーク懸念）。条件別細分化の余地 |
| running_style | 8 | ★★★★☆ | v3.1で大幅強化。マクリ率・出遅れ率が未実装 |
| rotation | 6 | ★★★★☆ | 騎手乗替(v4.0)追加済。quality_diffが未実装 |
| pace | 7 | ★★★★☆ | RPCI + 消耗フラグ。展開予想（tenkai_data）未活用 |
| training | 19 | ★★★★★ | KB+CK_DATA統合完了(v4.1)。セッション詳細は未使用 |
| speed | 5 | ★★★☆☆ | keibabook依存。自前指数・成長曲線が未実装 |
| 血統 | 0 | ☆☆☆☆☆ | **完全未実装**。若馬の予測精度に直結するため最大の欠落 |

---

#### 評価基盤

**評価**: **優秀**（v3.5改革後）。

| 項目 | 状態 | 評価 |
|------|------|------|
| 3-way split | train(2020-23)/val(2024)/test(2025-26) | ★★★★★ テスト汚染解消済 |
| キャリブレーション | Brier Score + ECE | ★★★★★ ECE<0.005は業界水準で優秀 |
| VBバックテスト | gap×EV×確率×オッズ帯×トラックの多軸 | ★★★★☆ 網羅的だがWalk-Forward未導入 |
| 特徴量重要度 | LightGBM gain | ★★★☆☆ SHAPが未導入 |

---

#### 予測パイプライン

| 項目 | 状態 | 評価 |
|------|------|------|
| ID解決 | ketto_numバグ修正済(v3.5)。99.8%解決率 | ★★★★★ |
| NaN処理 | LightGBMネイティブ（fillna(-1)廃止） | ★★★★★ |
| オッズ取得 | DB時系列 + JSONフォールバック | ★★★★☆ TARGETオッズ未連携 |
| リアルタイム性 | 事前バッチ。当日オッズ変動の反映が限定的 | ★★★☆☆ |

---

### 1-2. パフォーマンスサマリー（v4.1）

#### 予測精度

| 指標 | Model A | Model B | 評価 |
|------|---------|---------|------|
| AUC (test) | 0.8243 | 0.7837 | A=優秀, B=良好 |
| Brier Score | 0.1277 | 0.1392 | 両方良好 |
| ECE | 0.0041 | 0.0047 | 両方優秀（<0.005） |
| Top1 正答率 | 32.9% | 27.3% | ランダムの2-3倍 |

#### VB戦略ROI（テストセット: 2025-2026）

| Gap | ベット数 | 複勝Hit率 | 複勝ROI | 単勝ROI | 判定 |
|-----|---------|-----------|---------|---------|------|
| >=2 | 2,823 | 52.0% | 107.8% | 85.0% | 複勝のみ有効 |
| **>=3** | **1,720** | **53.1%** | **121.1%** | 83.0% | **コア戦略** |
| >=4 | 1,033 | 55.8% | 128.8% | 100.1% | 単勝もブレイクイーブン |
| >=5 | 591 | 58.7% | 147.7% | 122.6% | 高確信・高ROI |

---

### 1-3. バージョン推移と改善軌跡

```
v2   (AUC B: 0.764, ROI: 104.7%) → Dual Model基盤
v3.0 (AUC B: 0.775, ROI: 109.2%) → JRA-VAN 100% ID match
v3.1 (AUC B: 0.778, ROI: 110.2%) → 脚質+ペース +9特徴量
v3.3 (AUC B: 0.782, ROI: 113.0%) → 調教統合 +12特徴量
v3.5 (AUC B: 0.781, ROI: 117.0%) → 3-way split, ketto_num修正（真の性能）
v4.0 (AUC B: 0.784, ROI: 120.2%) → KB印/安定度/末脚 +11特徴量
v4.1 (AUC B: 0.784, ROI: 121.1%) → CK_DATA Model A限定 +7特徴量
```

**v2→v4.1で ROI +16.4pt（104.7%→121.1%）**。改善は主に特徴量追加とバグ修正に起因。

---

## Part 2: ML精度向上のためのアイデア

### 2-1. 短期（次スプリント） — 既存データ活用

#### A. 血統特徴量の新規追加 [期待効果: 高]

**現状**: 血統情報が一切使われていない。これは最大の構造的欠落。

**提案**:
```
sire_distance_top3_rate    — 父産駒の距離帯別複勝率
sire_track_type_top3_rate  — 父産駒の芝/ダート別複勝率
sire_track_cond_top3_rate  — 父産駒の馬場状態別複勝率
broodmare_sire_top3_rate   — 母父産駒の全体複勝率
```

**根拠**: 若馬（キャリア2-3戦）は過去走特徴量がほぼNaN。血統特徴量が唯一の能力推定手段。2歳戦・3歳春はフルフィールドの30-40%を占める。

**工数**: 中。種牡馬別集計テーブルの事前構築が必要。UM_DATAから血統コード取得。

---

#### B. 前走レースレベル [期待効果: 高]

**現状**: 「G1の5着」と「未勝利の5着」が同じ `avg_finish_last3 = 5.0` になる。

**提案（Phase 1: レーティング版）**:
```
prev_race_avg_rating   — 前走出走メンバーのkb_rating平均
prev_race_max_rating   — 前走メンバーのrating最高値
prev_race_rating_rank  — 前走内での自馬rating順位
class_change           — クラス変動（昇級=1/同級=0/降級=-1）
```

**根拠**: IDEAS_BACKLOGの「降格ローテ検出」、next_features_and_targets.mdのB-9で最重要項目として明記済み。kb_ext_indexのratingフィールドは既にメモリ上にあり、引数追加のみで実装可能。

---

#### C. 展開予想データ活用（tenkai_data） [期待効果: 中]

**現状**: keibabookの展開予想（逃げ/好位/中位/後方の配置図）が完全に未使用。

**提案**:
```
num_front_runners      — 同レース逃げ予想馬の数
pace_forecast          — 予想ペース（H/M/S）
position_vs_style_match — 予想ポジションと過去脚質の一致度
```

**根拠**: 現行ペース特徴量は「過去レースのRPCI」であり、当該レースのペース予想ではない。tenkai_dataは「今回のレースの展開」を直接予測した情報で、質が異なる。

---

#### D. 調教師/騎手のpoint-in-time化 [期待効果: 中]

**現状**: trainers.json/jockeys.jsonは全期間の累積成績。2020年の予測に2025年の成績が混入するリーク構造。

**提案**: `race_date < prediction_date` で区切った時点成績を使用。

**根拠**: 考察マスターの柱4「過学習の徹底回避」、IDEAS_BACKLOG「[基盤] point-in-time統計」で既に問題認識済み。現状のリークはModel BのAUCを楽観方向に歪めている可能性がある。

---

### 2-2. 中期（Sprint 3以降）— 新モジュール構築

#### E. LambdaRank（ランキング学習） [期待効果: 高]

**現状**: is_top3の二値分類。「1着と2着の差」「3着と4着の差」を学習できない。

**提案**: LightGBMの `objective='lambdarank'` でレース内順位を直接学習。

```python
# 着順→relevanceスコア
# 1着=5, 2着=4, 3着=3, 4着=2, 5着=1, 6着以下=0
params = {'objective': 'lambdarank', 'metric': 'ndcg'}
```

**根拠**:
- 二値分類では「接戦の4着」と「大差の4着」が同じ負例。情報ロスが大きい
- ランキングモデルの出力をHarville公式で組合せ馬券確率に変換可能
- 三連単展開時の基盤技術になる

---

#### F. 芝/ダート分離モデル [期待効果: 中]

**現状**: 単一モデルで芝・ダートを処理。`track_type` 特徴量で暗黙的に分離。

**提案**: 芝専用Model + ダート専用Modelの構築を検証。

**判断基準**:
```
分離すべき条件:
  - 芝/ダートでtop特徴量の順位が大幅に異なる
  - 分離モデルの合算AUCが統合モデルを上回る
  - サンプルサイズ: 芝≈60%, ダート≈40%。双方十分

維持すべき条件:
  - 統合モデルで芝/ダートの交互作用を学習できている
  - 分離による改善がAUC +0.002未満
```

**根拠**: vb_backtest_track_strategy.mdでトラック別ROIに差異が確認されている。ダートはgap>=5で単勝ROI有効、芝は複勝中心という異なる特性が示唆されている。

---

#### G. 自前スピード指数エンジン [期待効果: 高（長期）]

**現状**: keibabookスピード指数に依存。ブラックボックス。

**提案**:
```
raw_speed_index = (基準タイム - 走破タイム + 馬場補正 + ペース補正) × 係数

必要データ（全て取得済み）:
  - SE_DATA走破タイム
  - rating_standards基準タイム
  - ラップ（race JSON）
  - 馬場状態（race JSON）
```

**根拠**: IDEAS_BACKLOGの「自作タイム指数」で詳細設計済み。馬場差推定が最大のボトルネックだが、同日同コースの全レースタイムから回帰分析で推定可能。keibabook指数との乖離自体が新しい特徴量にもなる。

---

### 2-3. 長期（v5.0以降）— アーキテクチャ刷新

#### H. Multi-target / Multi-task学習

**提案**: is_top3 + is_win + 着差を同時学習するニューラルネットワーク。

**根拠**: 現在の4モデル（A/B/W/WV）は独立学習。タスク間の相関（「勝てる馬は3着にも来やすい」）を活用できていない。PyTorch移行が前提。

---

#### I. Transformer/Attention型モデル

**提案**: 馬のキャリア全体をsequenceとして入力し、Attentionで重要レースを自動選択。

**根拠**: 現在は「直近3走平均」「直近5走最高」などの手動集約。Attentionなら「3走前のG1での好走」と「直近の条件戦凡走」を自動的に重み付け可能。

---

#### J. 条件付き確率モデル（三連単基盤）

**提案**: Harvilleの独立仮定を緩和し、「Aが1着のとき、Bが2着になる確率」を明示的にモデル化。

**根拠**: harville_iia_critique.mdで理論的問題点を分析済み。三連単EVの正確な計算には条件付き確率が必須。Thurstone型モデルやコプラ関数が候補。

---

### 2-4. 精度向上の優先度マトリクス

| アイデア | 期待効果 | 実装工数 | データ準備 | 優先度 |
|----------|----------|----------|------------|--------|
| A. 血統特徴量 | ★★★★ | 中 | 要テーブル構築 | **1位** |
| B. 前走レースレベル | ★★★★ | 低〜中 | kb_ext既存 | **1位** |
| C. 展開予想データ | ★★★ | 低 | kb_ext既存 | 2位 |
| D. point-in-time化 | ★★★ | 中 | 既存データ | 2位 |
| E. LambdaRank | ★★★★ | 中 | 不要 | 3位 |
| F. 芝/ダート分離 | ★★ | 中 | 不要 | 3位 |
| G. 自前スピード指数 | ★★★★★ | 高 | 既存データ | 4位（基盤構築） |
| H. Multi-task | ★★★ | 高 | 不要 | 5位 |
| I. Transformer | ★★★ | 高 | 不要 | 5位 |
| J. 条件付き確率 | ★★★★ | 高 | 不要 | 5位（三連単時） |

---

## Part 3: 買い目・金額自動計算機能の構想（投資戦略視点）

### 3-1. 現状の購入判断ロジック

#### Value Bet検出

```
gap = odds_rank - value_rank
is_value_bet = (gap >= 3) AND (odds_rank > 0)
```

#### 馬券種推奨（predictions-content.tsx）

```
芝: 単勝中心 (gap>=5=強, gap>=4=通常)
ダート: 複勝中心 (gap>=5 & odds>=10 → 単勝, それ以外 → 複勝)
```

#### 課題

| 課題 | 詳細 |
|------|------|
| 金額計算なし | 「買い」の判定のみ。いくら賭けるかは人間判断 |
| 馬券種が限定的 | 単勝/複勝のみ。ワイド・馬連・三連複/単の組合せ未対応 |
| バンクロール非連動 | 残高に応じた購入額調整がない |
| レース選別なし | 全レースを均等に扱っている |
| 税務考慮なし | 税引後EVでの判断ができていない |

---

### 3-2. 自動購入金額計算エンジン設計

#### Phase 1: ケリー基準ベースの金額計算

```python
class BettingEngine:
    """ケリー基準による最適賭け額計算"""

    def __init__(self, bankroll: float, safety_factor: float = 0.25):
        self.bankroll = bankroll
        self.safety_factor = safety_factor  # フラクショナルケリー

    def kelly_fraction(self, pred_prob: float, odds: float) -> float:
        """ケリー基準の賭け割合を計算"""
        # f* = (p * odds - 1) / (odds - 1)
        edge = pred_prob * odds - 1
        if edge <= 0:
            return 0.0
        f = edge / (odds - 1)
        return f * self.safety_factor

    def calculate_bet(self, pred_prob: float, odds: float,
                      min_bet: int = 100, max_bet_ratio: float = 0.05) -> int:
        """推奨購入金額を計算"""
        f = self.kelly_fraction(pred_prob, odds)
        raw_bet = self.bankroll * f
        # 上限: バンクロールの5%
        max_bet = self.bankroll * max_bet_ratio
        bet = min(raw_bet, max_bet)
        # 100円単位に丸め
        bet = max(int(bet // 100) * 100, 0)
        if bet < min_bet and raw_bet > 0:
            bet = min_bet  # 最低賭け額
        return bet
```

**設計原則**:
- フラクショナルケリー（25%）で破産リスクを指数関数的に低減
- 1レースあたりバンクロールの5%上限（過剰ベット防止）
- 100円単位の丸め（JRA最低購入単位）

---

#### Phase 2: 同一レース内相関を考慮したポートフォリオベット

```python
class RacePortfolioBetting:
    """同一レース内の馬券相関を考慮した金額配分"""

    def calculate_race_budget(self, bankroll: float,
                              race_confidence: float) -> float:
        """レース単位の予算を計算

        race_confidence: RaceScoreのconfidence値 (0-100)
        """
        base_ratio = 0.03  # バンクロールの3%/レースが基本
        confidence_multiplier = 0.5 + (race_confidence / 100) * 1.0
        # confidence=50 → 1.0倍, confidence=100 → 1.5倍
        return bankroll * base_ratio * confidence_multiplier

    def allocate_within_race(self, race_budget: float,
                             bets: list[dict]) -> list[dict]:
        """レース予算内で個別馬券に配分

        同一馬に依存する馬券の合計を制限
        """
        # 馬番ごとの依存度を計算
        horse_exposure = {}
        for bet in bets:
            for horse_num in bet['horses']:
                horse_exposure[horse_num] = (
                    horse_exposure.get(horse_num, 0) + bet['raw_amount']
                )

        # 最大依存馬がレース予算の40%を超えないよう調整
        max_exposure = race_budget * 0.40
        for bet in bets:
            scaling = 1.0
            for horse_num in bet['horses']:
                if horse_exposure[horse_num] > max_exposure:
                    scaling = min(scaling,
                                  max_exposure / horse_exposure[horse_num])
            bet['adjusted_amount'] = int(bet['raw_amount'] * scaling // 100) * 100

        return bets
```

**根拠**: bankroll_management_principles.md 10-1で指摘された「同一レース内の賭け同士の相関問題」への対応。1番馬が飛ぶと3つのワイドが全滅するリスクを定量管理。

---

#### Phase 3: マルチ馬券種EV計算

```python
class MultiTicketEV:
    """複数馬券種のEV計算エンジン"""

    def compute_place_ev(self, pred_top3_prob: float,
                         place_odds_low: float) -> float:
        """複勝EV"""
        return pred_top3_prob * place_odds_low

    def compute_win_ev(self, pred_win_prob: float,
                       win_odds: float) -> float:
        """単勝EV"""
        return pred_win_prob * win_odds

    def compute_wide_ev(self, prob_a_top3: float, prob_b_top3: float,
                        joint_prob: float, wide_odds: float) -> float:
        """ワイドEV（2頭が両方3着以内になる確率 × オッズ）

        joint_prob: P(A in top3 AND B in top3)
        条件付き確率で計算: P(A∩B) = P(A) * P(B|A)
        簡易版: P(A) * P(B) * correlation_factor
        """
        return joint_prob * wide_odds

    def compute_exacta_ev(self, prob_a_win: float, prob_b_second_given_a: float,
                          exacta_odds: float) -> float:
        """馬連EV（条件付き確率）"""
        joint_prob = prob_a_win * prob_b_second_given_a
        return joint_prob * exacta_odds

    def recommend_ticket_types(self, horse_predictions: list[dict],
                                bankroll_scale: str) -> list[str]:
        """バンクロール規模に応じた馬券種推奨

        bankroll_scale: 'small'(<50万), 'medium'(50-200万),
                        'large'(200-1000万), 'xlarge'(>1000万)
        """
        # bankroll_management_principles.md のフレームワーク
        base = ['fukusho']  # 複勝は常に
        if bankroll_scale in ('medium', 'large', 'xlarge'):
            base.extend(['wide', 'wakuren'])
        if bankroll_scale in ('large', 'xlarge'):
            base.append('sanrenpuku')
        if bankroll_scale == 'xlarge':
            base.append('sanrentan')
        return base
```

---

### 3-3. レース選別エンジン（RaceScore改良）

#### 現状のRaceScore

```typescript
// prediction.ts に定義済み
interface RaceScore {
    data_completeness: number;   // データ充足度
    predictability: number;      // 予測可能性
    confidence: number;          // 確信度
    total_score: number;         // 総合スコア(0-100)
    recommendation: '高' | '中' | '低' | '不可';
}
```

#### 改良提案: 多次元レース評価

```python
class RaceSelector:
    """投資対象レースの選別"""

    def score_race(self, race_data: dict) -> dict:
        # 1. データ充足度（現行）
        data_score = self._data_completeness(race_data)

        # 2. VB候補の質
        vb_horses = [h for h in race_data['entries'] if h['gap'] >= 3]
        vb_quality = self._vb_quality_score(vb_horses)

        # 3. モデル確信度（予測確率の分散）
        probs = [h['pred_proba_v'] for h in race_data['entries']]
        entropy = -sum(p * log(p) for p in probs if p > 0)
        # 低エントロピー = モデルが明確な順位付けをしている
        confidence_score = max(0, 100 - entropy * 20)

        # 4. 市場乖離度（VBの平均gap）
        avg_gap = mean([h['gap'] for h in vb_horses]) if vb_horses else 0
        market_gap_score = min(avg_gap * 15, 100)

        # 5. 過去ROI実績（同条件レースの歴史的ROI）
        historical_roi = self._historical_roi(
            race_data['track_type'],
            race_data['distance'],
            race_data['entry_count']
        )

        total = (data_score * 0.15 + vb_quality * 0.30 +
                 confidence_score * 0.20 + market_gap_score * 0.20 +
                 historical_roi * 0.15)

        return {
            'total_score': total,
            'invest': total >= 60,            # 投資対象
            'invest_level': 'high' if total >= 80 else
                           'medium' if total >= 60 else 'low',
            'components': {
                'data': data_score,
                'vb_quality': vb_quality,
                'confidence': confidence_score,
                'market_gap': market_gap_score,
                'historical': historical_roi
            }
        }
```

---

### 3-4. バンクロール管理システム

#### アーキテクチャ

```
┌───────────────────────────────────────────────────┐
│ Themis (購入決定エンジン)                           │
│                                                    │
│  入力: 予測確率 / オッズ / バンクロール残高          │
│  出力: 馬券種 / 馬番組合せ / 購入金額               │
│                                                    │
│  ┌────────────────┐  ┌─────────────────────────┐  │
│  │ BettingEngine   │  │ RacePortfolioBetting    │  │
│  │ (ケリー計算)     │  │ (相関管理)              │  │
│  └────────┬───────┘  └─────────┬───────────────┘  │
│           │                    │                   │
│  ┌────────▼────────────────────▼───────────────┐  │
│  │ BankrollManager                              │  │
│  │ - 残高追跡（レース単位で即時更新）            │  │
│  │ - ドローダウンアラート（-20%/-30%/-40%）      │  │
│  │ - safety_factor動的調整                       │  │
│  │ - 日次レポート                                │  │
│  └──────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

#### バンクロール更新タイミング

松風の教訓（011のバグ: マルチプロセスでバンクロール同期不全→200万損失）を踏まえ:

| 方式 | メリット | デメリット | 推奨 |
|------|---------|-----------|------|
| レース毎即時更新 | 最も正確 | 実装バグリスク高、追い上げ過剰 | × |
| 午前/午後分割 | バランス型 | 中程度の複雑さ | **○（中期）** |
| 日単位事前計算 | バグリスク最小、安定 | 日中の損益が反映されない | **○（初期）** |

**推奨**: 初期は日単位。中期で午前/午後分割に移行。

---

### 3-5. ドローダウン防御の多重構造

```
第1層: 追い下げ方式
  → バンクロール減少 → 購入額自動減少

第2層: フラクショナルケリー (safety_factor = 0.25)
  → フルケリーの25%で運用 → 破産確率を指数関数的に低減

第3層: ドローダウンアラート
  -20%: safety_factor → 0.15 に引き下げ
  -30%: 投資停止勧告（翌週まで見送り）
  -40%: 緊急全停止

第4層: 最低バンクロール閾値
  初期バンクロールの10%を下回ったら全停止
  再開条件: パラメータ再検証 + 1ヶ月のバックテスト再実施
```

---

### 3-6. 馬券種ポートフォリオ戦略

#### バンクロール規模別の推奨構成

| 規模 | 馬券種 | 配分比率 | 根拠 |
|------|--------|---------|------|
| ~50万円 | 複勝100% | 全額複勝 | 安定性最優先。大数の法則を効かせる |
| 50-200万円 | 複勝50% + ワイド30% + 枠連20% | 分散開始 | ワイドと枠連は相関が低い（008の知見） |
| 200-1,000万円 | 複勝30% + ワイド25% + 枠連15% + 三連複30% | 中リスク追加 | 三連複のEVを取りに行ける規模 |
| 1,000万円~ | 複勝15% + ワイド15% + 三連複25% + 三連単45% | 全馬券種 | 三連単の高EV×高分散を許容できる |

#### 馬券種間相関マトリクス（推定）

```
         複勝  ワイド  枠連  馬連  三連複  三連単
複勝      1.0   0.6   0.3   0.4   0.5    0.3
ワイド          1.0   0.4   0.7   0.7    0.4
枠連                  1.0   0.5   0.3    0.2
馬連                        1.0   0.8    0.5
三連複                            1.0    0.6
三連単                                   1.0
```

**推奨組合せ**: 複勝 + 三連単（相関0.3→分散効果最大）
**非推奨**: 馬連 + ワイド（相関0.7→リスク集中）

---

### 3-7. 自動計算の出力イメージ

```json
{
  "race_id": "2026021506010408",
  "race_score": 82,
  "invest_level": "high",
  "bankroll": 500000,
  "race_budget": 18000,
  "bets": [
    {
      "ticket_type": "fukusho",
      "horse_num": 7,
      "amount": 5000,
      "ev": 1.42,
      "kelly_fraction": 0.032,
      "reasoning": "VB gap=5, Model B rank=1, odds_rank=6"
    },
    {
      "ticket_type": "fukusho",
      "horse_num": 3,
      "amount": 3000,
      "ev": 1.18,
      "kelly_fraction": 0.019,
      "reasoning": "VB gap=4, Model B rank=2, odds_rank=6"
    },
    {
      "ticket_type": "wide",
      "horses": [3, 7],
      "amount": 2000,
      "ev": 1.31,
      "kelly_fraction": 0.015,
      "reasoning": "VB2頭のワイド組合せ"
    }
  ],
  "total_bet": 10000,
  "expected_return": 13200,
  "expected_roi": 132.0,
  "horse_exposure": {
    "7": 7000,
    "3": 5000
  },
  "max_horse_exposure_ratio": 0.39,
  "risk_assessment": "green"
}
```

---

### 3-8. 実装ロードマップ

#### Phase 1: 基本金額計算（v5.0）

- [ ] ケリー基準計算クラス実装
- [ ] バンクロール管理クラス実装
- [ ] Web UIに推奨金額表示を追加
- [ ] 複勝・単勝のEV計算自動化
- [ ] ドローダウンアラート実装

#### Phase 2: ポートフォリオ拡張（v5.1）

- [ ] ワイドEV計算（条件付き確率の簡易版）
- [ ] 同一レース内相関管理
- [ ] レース選別スコアの本格実装
- [ ] 馬券種別ROIモニタリングダッシュボード
- [ ] 購入証跡の自動記録（税務対応）

#### Phase 3: 組合せ馬券（v6.0）

- [ ] 三連複EV計算（Harville公式）
- [ ] 三連単EV計算（条件付き確率モデル）
- [ ] 馬券種ポートフォリオ最適化
- [ ] モンテカルロシミュレーションによる破産確率計算
- [ ] EV閾値×バンクロール規模の同時最適化

#### Phase 4: 完全自動化（v7.0）

- [ ] Themisエンジン統合（確率・オッズ・バンクロールのみで判断）
- [ ] PAT/IPAT自動投票連携
- [ ] リアルタイムオッズ監視+動的リバランス
- [ ] 税引後EV計算の組込み
- [ ] 監査ログ・改ざん防止記録

---

## Part 4: 投資専門家としての追加提言

### 4-1. リスク管理の原則

**最も重要な教訓**: 松風氏の2019年前半 -97%ドローダウン（160万→5.5万）。

これは「モデルが悪い」のではなく「パラメータチューニングの攻めすぎ」が原因。具体的には:
- EV閾値を下げすぎた→低EV馬券のキャリブレーション誤差で損失
- 購入点数が増えすぎた→追い下げが追いつかない速度でバンクロール減少

**教訓**:
1. **パラメータ1つのミスが最終結果を32分の1にする**（5億→1,739万の機会損失）
2. **初期は保守的に運用し、実績データで検証してから攻める**
3. **EV閾値の変更は数千レース分のバックテストを根拠に**。短期結果での変更は厳禁

---

### 4-2. 現システムの投資戦略としての強み

| 強み | 定量的根拠 |
|------|-----------|
| 正のEV確認済 | gap>=3で複勝ROI 121.1%（1,720ベットのテスト） |
| キャリブレーション良好 | ECE < 0.005 → EV計算に高い信頼性 |
| 純粋テスト評価 | 3-way splitで楽観バイアス除去済み |
| 市場独立シグナル | Model Bが市場価格を見ずに予測→真の情報優位 |

---

### 4-3. 現システムの投資戦略としての弱み

| 弱み | リスク | 対策案 |
|------|--------|--------|
| テスト期間が1.5年 | 市場環境変化への耐性が未検証 | Walk-Forward Validationの導入 |
| 単一馬券種（複勝）中心 | ポートフォリオ分散なし | 馬券種拡張（ワイド、三連複） |
| 金額固定 | バンクロール効率が低い | ケリー基準導入 |
| 税務未考慮 | 雑所得vs一時所得で利益が5倍変わる | 税引後EVの事前計算 |
| 競合AI未考慮 | 同じ歪みを突くAI増加で利益縮小 | 独自データ投資（映像、調教目視） |

---

### 4-4. 投資規模別の推奨戦略

#### 初期フェーズ（バンクロール 5-30万円）

```
目的: モデル検証（利益ではなくデータ蓄積）
馬券種: 複勝のみ（100円均等）
購入基準: VB gap>=3 のみ
月間投資額: ~3万円
期待ROI: 110-120%（期待月利 3,000-6,000円）
重要指標: 的中率、キャリブレーション、gap別ROI
```

#### 成長フェーズ（バンクロール 30-200万円）

```
目的: 収益化開始
馬券種: 複勝 + ワイド
購入基準: VB gap>=3, EV>=1.05
金額計算: フラクショナルケリー（safety_factor=0.25）
月間投資額: ~バンクロールの100-200%
期待ROI: 110-120%
```

#### 本格運用フェーズ（バンクロール 200万円~）

```
目的: 利益最大化
馬券種: 複勝 + ワイド + 枠連 + 三連複
購入基準: EV>=1.02（閾値はバックテストで最適化）
金額計算: ケリー基準 + レース内相関管理
バンクロール更新: 午前/午後分割
ドローダウン防御: 4層構造
税務: 雑所得要件を満たすレース比率の維持
```

---

### 4-5. 分散ドラッグ（Volatility Drag）への対策

投資理論における重要概念。回収率115%でも分散が大きいと複利成長率が下がる。

```
対数リターンの期待値 ≈ ln(E[R]) - σ²/(2×E[R]²)

例:
  回収率115%, σ=30% → 対数成長率 ≈ 0.14 - 0.034 = 0.106 (10.6%)
  回収率110%, σ=15% → 対数成長率 ≈ 0.095 - 0.009 = 0.086 (8.6%)
  回収率110%, σ=10% → 対数成長率 ≈ 0.095 - 0.004 = 0.091 (9.1%)

→ 「回収率を下げてでも分散を下げる」ことが長期複利成長に有利
→ これがEV閾値を下げて購入点数を増やす戦略の数理的根拠
```

**対策**:
- 購入点数を増やして大数の法則を効かせる
- 馬券種ポートフォリオで相関の低い賭けを組み合わせる
- 1レースへの集中投資を避ける（race_budget上限）
- ドローダウンアラートで分散急増時に即座に縮小

---

## 付録: 次回アクション候補

### 即時実行可能

1. [ ] 血統特徴量モジュール（`blood_features.py`）の新規作成
2. [ ] 前走レースレベル特徴量の実装（kb_ext_indexのrating集計）
3. [ ] trainer/jockeys.jsonのpoint-in-time化
4. [ ] バックテストにWalk-Forward Validation導入

### 中期計画

5. [ ] BettingEngineクラス（ケリー基準）のPython実装
6. [ ] BankrollManagerクラスの実装
7. [ ] Web UIに推奨金額カラムを追加
8. [ ] 芝/ダート分離モデルのAUC検証実験
9. [ ] LambdaRank（ランキング学習）実験

### 長期構想

10. [ ] 自前スピード指数エンジン構築
11. [ ] 三連単EV計算（Harville→条件付き確率）
12. [ ] Themis購入決定エンジンの完全自動化
13. [ ] モンテカルロシミュレーション基盤

---

**タグ**: `#MLレビュー` `#精度向上` `#購入戦略` `#バンクロール` `#ケリー基準` `#投資戦略` `#ロードマップ`
**作成**: 2026-02-15（カカシ）
