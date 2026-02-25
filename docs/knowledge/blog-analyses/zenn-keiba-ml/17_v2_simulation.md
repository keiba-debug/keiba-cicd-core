# 17. 【v2.1.1】modules/simulation/の解説

> 出典: Zenn「競馬予想で始める機械学習〜完全版〜」Ch.17

---

## モジュール構成

```
modules/simulation/
├── _betting_tickets.py     # 馬券の買い方定義＋リターン計算
├── _simulator.py           # 成績記録＋回収率集計
└── _plot.py                # 閾値スイープ結果のプロット
```

---

## BettingTickets（馬券リターン計算）

### 設計
- ReturnProcessor（払い戻しテーブル）を受け取り、7券種の的中判定＋払戻計算
- 全メソッド統一: `(race_id, umaban: list, amount) → (n_bets, bet_amount, return_amount)`

### 7券種の実装

| メソッド | 券種 | 枚数計算 | 的中判定 |
|---------|------|---------|---------|
| bet_tansho | 単勝 | len(umaban) | win in umaban |
| bet_fukusho | 複勝 | len(umaban) | win_0/1/2 in umaban（複数的中あり） |
| bet_umaren_box | 馬連BOX | nC2 | {win_0, win_1} ⊆ umaban |
| bet_umatan_box | 馬単BOX | nP2 (permutations) | 順序一致 |
| bet_wide_box | ワイドBOX | nC2 | win_0,win_1 in umaban（複数的中あり） |
| bet_sanrenpuku_box | 三連複BOX | nC3 | {win_0, win_1, win_2} ⊆ umaban |
| bet_sanrentan_box | 三連単BOX | nP3 (permutations) | 順序一致 |

### ポイント
- 馬単・三連単は**順序あり** → `permutations`で全順列を生成、1枚ずつ的中判定
- 馬連・三連複は**順序なし** → `comb(n, r)`で枚数計算、集合の包含で的中判定
- 複勝・ワイドは**複数的中** → 1-3着それぞれに判定、的中した分だけ払戻加算
- 金額は`amount/100`で計算（払戻テーブルが100円単位のため）

### 使用例
```python
betting_tickets.bet_wide_box('202106030610', [1, 3, 6, 9], 100)
# → (6.0, 600.0, 660.0)  # 6枚, 600円投資, 660円払戻
```

---

## Simulator（成績集計）

### calc_returns_per_race(actions)
- KeibaAI.decide_action()の出力 `{race_id: {券種: [馬番]}}` を受け取る
- レースごとに: n_bets, bet_amount, return_amount, hit_or_not を計算
- 券種ごとにBettingTicketsのメソッドを呼び分け（if/elif連鎖）

### calc_returns(actions) → 集計結果
```python
{
    'n_bets': 16440,        # 購入枚数
    'n_races': 4125,        # 参加レース数
    'n_hits': 2644,         # 的中レース数
    'total_bet_amount': 16440,  # 投資額
    'return_rate': 0.764,   # 回収率
    'std': 0.016            # 回収率の標準偏差
}
```

### 回収率の標準偏差の計算

```python
std = returns_per_race['return_amount'].std() * np.sqrt(n_races) / total_bet_amount
```

#### 数学的根拠
- 各レースの払戻 X₁, X₂, ..., Xₙ が独立同分布と仮定
- 払戻合計 G = X₁ + X₂ + ... + Xₙ
- V[G] = n × V[X]（独立同分布の加法性）
- σ[回収率] = σ[G/b] = √(n) × σ(X) / b
- → `std() * sqrt(n_races) / total_bet_amount`

---

## Plot（閾値スイープ）

### 実行フロー
```python
for i in range(N_SAMPLES):
    threshold = T_RANGE[1] * i / N_SAMPLES + T_RANGE[0] * (1 - i / N_SAMPLES)
    actions = keiba_ai.decide_action(score_table, BetPolicyTansho, threshold=threshold)
    returns[threshold] = simulator.calc_returns(actions)

# 回収率 ± 標準偏差をプロット
plot_single_threshold(returns_df, N_SAMPLES, label='tansho')
```

### プロット内容
- X軸: threshold（スコア閾値）
- Y軸: return_rate（回収率）
- **塗りつぶし**: return_rate ± std（ぶれ幅）
- 高threshold → 高回収率だが枚数少 → ぶれ幅大

---

## KeibaCICDとの比較

| 項目 | この書籍 v2 | KeibaCICD v4 |
|------|-----------|-------------|
| シミュレーション対象 | 7券種 | 単勝・複勝のみ |
| 的中判定 | 払い戻しテーブルから逆算 | race JSONの着順から判定 |
| 枚数計算 | comb/permutations | 1レース1枚（均等） |
| 回収率計算 | Simulator.calc_returns() | backtest_bet_engine.py |
| 標準偏差 | `std * sqrt(n) / total_bet` | Bootstrap CI（信頼区間） |
| 閾値探索 | threshold線形スイープ | プリセット3種 + 手動調整 |
| 可視化 | matplotlib（回収率±σ） | Web UI（月別・累積P&L） |
| データソース | ReturnProcessor（払い戻しpickle） | race JSON（オッズ×着順で計算） |

## 参考になるポイント

1. **★ 閾値スイープの可視化** — threshold vs 回収率の2Dプロットで最適閾値を視覚的に探索。うちのbet_engine.pyは固定プリセットなので、この探索アプローチは参考になる。ただしうちは複数条件(gap, EV, AR偏差値)の多次元なので単純スイープは難しい
2. **回収率の標準偏差** — `std * sqrt(n) / total_bet` の数学的導出が明確。うちのBootstrap CIより計算が軽い（仮定が強い分）
3. **7券種のシミュレーション基盤** — 馬連・三連複等のBOX計算がそのまま使える。うちが券種拡張する際の参考実装
4. **permutationsで馬単・三連単BOX** — 順列生成→1枚ずつ的中判定。力技だがシンプルで正しい
5. **シミュレーションをnotebookで柔軟に** — BetPolicyごとにコードを変えられるnotebook方式。うちのexperiment.pyも似た思想

## 標準偏差 vs Bootstrap CI

| | 解析的σ（この書籍） | Bootstrap CI（うち） |
|---|---|---|
| 計算速度 | 速い（1回の計算） | 遅い（1000回リサンプリング） |
| 仮定 | 独立同分布（やや強い） | 分布仮定不要 |
| 精度 | 正規分布に近い時◎ | 常に頑健 |
| 実装 | 1行 | 10行程度 |

→ うちのBootstrap CIは仮定が少ない分より頑健。この書籍方式は素早い概算向き

## 次章で確認したいこと

- Ch.18以降（もしあれば）
- 全体まとめ（この書籍からうちに取り入れるべき項目の優先度整理）
