# 16. 【v2.1.1】modules/policies/の解説

> 出典: Zenn「競馬予想で始める機械学習〜完全版〜」Ch.16

---

## モジュール構成

```
modules/policies/
├── _score_policy.py     # 「馬の勝ちやすさスコア」の計算ロジック
└── _bet_policy.py       # スコア＋オッズから馬券購入戦略を決める
```

---

## ScorePolicy（スコア算出）

### 共通関数
```python
def _calc(model, X):
    score_table = X[UMABAN].to_frame().copy()
    score = model.predict_proba(X)[:, 1]  # P(3着以内)
    score_table['score'] = score
    return score_table

def _apply_scaler(score, scaler):
    return score.groupby(level=0, group_keys=False).apply(scaler)
```

### スケーラー2種
| スケーラー | 式 | 用途 |
|-----------|---|------|
| _scaler_standard | `(x - mean) / std` | レース内偏差値 |
| _scaler_relative_proba | `x / sum` | レース内相対確率 |

### 4つのScorePolicy

| Policy | 処理 | 特徴 |
|--------|------|------|
| **BasicScorePolicy** | predict_probaそのまま | 絶対評価 |
| **StdScorePolicy** | レース内標準化 | **相対評価（最も重要）** |
| **MinMaxScorePolicy** | レース内標準化 → 全体0-1スケーリング | 標準化+正規化 |
| **RelativeProbaScorePolicy** | レース内 x/sum | 確率的解釈可能 |

### StdScorePolicyの意図
- LightGBMの出力は絶対評価 → 同じ0.8でもレースの質で意味が異なる
- 強豪揃いのレースで0.8 vs 弱いメンバーで0.8 → 相対評価で差別化
- **レース内偏差値**で「他の馬と比べてどの程度高いか」を評価

---

## BetPolicy（購入戦略）

### 設計パターン
- AbstractBetPolicy（抽象クラス）で型を規定
- `judge(score_table, **params)` → `{race_id: {券種: [馬番]}}`
- **params で閾値等の数を自由に

### 7つのBetPolicy

| Policy | 券種 | 条件 |
|--------|------|------|
| BetPolicyTansho | 単勝 | score >= threshold |
| BetPolicyFukusho | 複勝 | score >= threshold |
| BetPolicyUmarenBox | 馬連BOX | score >= threshold & 2頭以上 |
| BetPolicyUmatanBox | 馬単BOX | score >= threshold & 2頭以上 |
| BetPolicyWideBox | ワイドBOX | score >= threshold & 2頭以上 |
| BetPolicySanrenpukuBox | 三連複BOX | score >= threshold & 3頭以上 |
| BetPolicySanrentanBox | 三連単BOX | score >= threshold & 3頭以上 |
| BetPolicyUmatanNagashi | 馬単流し | threshold1(軸) + threshold2(相手) |

### 出力例
```python
keiba_ai.decide_action(
    X_test,
    score_policy=StdScorePolicy,
    bet_policy=BetPolicyTansho,
    threshold=0.5
)
# → {'202005040402': {'tansho': [6, 5, 2]},
#    '202005040405': {'tansho': [3, 5, 11, 10]}}
```

### KeibaAI.decide_action()
```python
def decide_action(self, X, score_policy, bet_policy, **params):
    actions = bet_policy.judge(self.calc_score(X, score_policy), **params)
    return actions
```
- score_policy → スコア算出ロジック選択
- bet_policy → 購入ロジック選択
- 両方をStrategyパターンで差し替え可能

---

## KeibaCICDとの比較

| 項目 | この書籍 v2 | KeibaCICD v4 |
|------|-----------|-------------|
| スコア変換 | 4種のScorePolicy（Strategy） | predict.pyでAR偏差値（固定） |
| レース内標準化 | StdScorePolicy | AR偏差値 `50+10*(AR-mean)/max(std,3.0)` |
| 相対確率 | RelativeProbaScorePolicy | レース内正規化（predict.pyで実施） |
| 購入戦略 | 7種のBetPolicy（Strategy） | bet_engine.pyの3プリセット |
| 閾値ベース | score >= threshold | gap>=5 + rank_v<=3 + EV/AR偏差値 |
| 複合条件 | 単一threshold | 複数条件の組み合わせ |
| 券種 | 7種類（単/複/馬連/馬単/ワイド/三連複/三連単） | 単勝・複勝のみ |
| 流し | BetPolicyUmatanNagashi（2閾値） | 未実装 |
| 拡張性 | 抽象クラス+**params | プリセット辞書 |

## 参考になるポイント

1. **StdScorePolicyの思想** — レース内標準化で相対評価。うちのAR偏差値と同じ思想だが、確率出力に対して行っている点が異なる。うちは回帰モデル(RegB)の出力を偏差値化
2. **RelativeProbaScorePolicy** — `x / sum` で確率的解釈可能にする。うちのレース内正規化と本質的に同じ
3. **Strategyパターンの設計** — ScorePolicy/BetPolicyの差し替えが容易。うちのbet_engine.pyのプリセットは実質的に同じ機能だが、コードの分離度はこちらが上
4. **7券種対応** — うちは単複のみ。三連複BOX等は買い目計算が複雑だが、高配当狙いには有用
5. **流し戦略（2閾値）** — 軸馬(高スコア)+相手馬(中スコア)の概念。うちのrank_v<=3(プレフィルタ)+gap>=5(フィルタ)も類似の二段階

## 感想

- ScorePolicyの4種は、うちが既に「AR偏差値」「レース内正規化」で個別に実装しているものの体系化版
- **うちの優位点**: 複数モデル(A/V/W/WV/RegB)の出力を組み合わせたGapフィルターは、単一モデル+閾値より高度
- **書籍の優位点**: 券種の多様性（7種）、Strategyパターンによる拡張性の高さ
- 流し戦略は今後検討の余地あり（三連複の軸+相手）

## 次章で確認したいこと

- Ch.17 simulation（回収率シミュレーションの具体的実装）
