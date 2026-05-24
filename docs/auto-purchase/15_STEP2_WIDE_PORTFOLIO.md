# 15. (廃止) Step 2 — ワイド ◎-○-▲ BOX とポートフォリオ配分の最小実装

> **🚫 2026-05-24 廃止 (Session 127 / DEPRECATED)**: ふくだ君判断「**フクダの買い方を買うだけなら意味がない。フクダの印は完全無視にしよう**」により、本書および印ベースの F戦法 Step1-4 機械化は **方針として廃止**。
>
> - **印は完全無視**: 自動投票エンジンは DAT / my_marks_v2 を一切参照しない
> - **主軸シフト**: ML予想 + オッズ + EV のみで判断する「印無視モード」（[selective.py](../../keiba-v2/ml/strategies/selective.py) 系）が新主軸
> - **既存資産の扱い**: Step 1 で作った [tansho.py](../../keiba-v2/ml/strategies/tansho.py) / [my_marks.py](../../keiba-v2/ml/features/my_marks.py) は休眠。リーダー部分は将来「印を補助情報として ranker に入力」拡張で再利用予定
> - **後継**: Session 127 内で `16_IGNORE_MARK_AUTO_VOTING.md` （仮）起草予定
>
> 本書の本文以下は **設計史として保存** するが、実装の指針としては使わない。Step 1-4 ロードマップ全体の再定義は別途 [06_PHASED_ROADMAP.md](./06_PHASED_ROADMAP.md) と [09_MY_MARKS_AND_STRATEGY.md](./09_MY_MARKS_AND_STRATEGY.md) で行う。
>
> ---
>
> **作成日**: 2026-05-24（Session 127 / Step 1 完成翌日、同日廃止）
> **担当**: カカシ（設計起草）→ シズネレビュー前に廃止確定
> **当初位置づけ**: [09_MY_MARKS_AND_STRATEGY.md](./09_MY_MARKS_AND_STRATEGY.md) §3.2 で定義した **Step 2 (＋ワイド ◎-○-▲ BOX)** の実装契約。
> **関連**: [09](./09_MY_MARKS_AND_STRATEGY.md)、[10](./10_BANKROLL_CONTROL.md)、[14](./14_LEDGER_SCHEMA.md)、[06](./06_PHASED_ROADMAP.md)

---

ふくだ君から本セッション冒頭で出た方針は 2 つだけ：

1. **配分は「等額 + per_race_max_yen 自動圧縮」**（券種固定比率は持たない）
2. **印不足ケースは「固定化せずオッズを見て柔軟に最終判断」**（=戦略は候補を出すだけ、採用判断はふくだ君）

本書はこの 2 方針を Step 2 の実装に落とす契約。Step 3-4 で配分ロジックを進化させる前提で、**Step 2 はあえて愚直に等額配分**で組む。

---

## 1. Step 2 のスコープ

### 1.1 やる

| 項目 | 内容 |
|---|---|
| 戦略追加 | [`ml/strategies/wide.py`](../../keiba-v2/ml/strategies/wide.py) — ワイドBOX/部分ペア候補生成 |
| ポートフォリオ層 | [`ml/strategies/portfolio.py`](../../keiba-v2/ml/strategies/portfolio.py) — Step 1 単勝 + Step 2 ワイドを 1 portfolio に束ねる |
| 配分計算 | 等額 + per_race_max_yen 自動圧縮（§4）|
| 出力ファイル | `wide_bets.json` / `portfolio_bets.json`（§5）|
| ledger v2 統合 | `formation_type:"box"` / `raw_legs.box` の最初の本番使用（[14 §10.2](./14_LEDGER_SCHEMA.md)）|
| BT 評価基盤 | [`ml/sim/ticket_sweep.py`](../../keiba-v2/ml/sim/ticket_sweep.py) — ワイドBOX の単独 ROI / Step1+Step2 合算 ROI |

### 1.2 やらない（Step 3-4 へ送り）

- 馬連・馬単・三連単・三連複（Step 3-4）
- EV / Kelly ベースの配分ロジック（Step 2 BT 結果を見てから判断）
- 券種別固定比率の config 化（パターン縛り回避、ふくだ君方針）
- ふくだ君判断 UI の本実装（Phase 0 見える化で代替、Step 3 で本実装）

---

## 2. ふくだ君判断（2026-05-24）

| 論点 | 決定 | 根拠 |
|---|---|---|
| **配分方式** | 等額 + per_race_max_yen 自動圧縮 | パターン縛らない方針。EV 均しのリスクは BT で検証 |
| **印不足レース** | 戦略は候補を出す、採用判断はふくだ君 | 「固定化せず柔軟に最終判断」。strategy 層と approve 層を分離 |
| **最小ベット単位** | **100 円**（JRA-IPAT 最小単位）| 自動圧縮で 100 円未満になったら点数を削る |
| **Step 2 portfolio_strategy 名** | `"F-Step2"` （[14 §9-4](./14_LEDGER_SCHEMA.md) 予約語） | Step 1 単独レースは引き続き `"tansho_ippon"` |
| **◎+穴 ペア** | 候補に**出す**（§3.5 Q1）| 穴は◎より優先される可能性、ペアとして有効 |
| **◎○穴 BOX** | **3点 BOX を組む**（穴を ▲ 相当として扱う、§3.5 Q2）| 後付け分類は pattern_label でカバー |
| **△ の扱い** | **Step 2 候補に含める**（◎-△ もワイド候補、§3.5 Q3）| カカシ初案 (含めない) からふくだ判断で変更。連下も三着圧さえとしてワイド対象 |
| **wide/portfolio 二段構え** | 同意（§5.3 Q4）| wide_bets.json は BT 用、portfolio_bets.json が実購入 SoT |
| **ledger BOX を 3 ticket 分散** | 同意（§6.2 Q5）| ペア単位の BT 分析を捨てたくない |
| **Step 2 受け入れに BT 含めない** | 同意（§8.4 Q6）| ticket_sweep は Step 3 入口で実施 |

---

## 3. ワイド候補の生成ルール

### 3.1 候補生成の原則

「**印があれば候補は出す。何点を採用するかは下流（portfolio + ふくだ君）が決める**」。

`wide.py` は組み合わせ候補を **過不足なく** 列挙する純粋関数に徹する。EV 評価や採否判断は持たない。

### 3.2 印別 候補テーブル

| 持っている印 | ワイド候補（点数） | 備考 |
|---|---|---|
| ◎ のみ | （無し） | Step 1 単勝のみ。portfolio は ticket=単勝1本 |
| ◎ ○ | ◎-○（1点）| ワイドBOX ではなく単ペア |
| ◎ ▲ | ◎-▲（1点）| 同上 |
| ○ ▲ | （無し） | ◎が無い場合は Step 2 では発火しない（§3.4） |
| ◎ ○ ▲ | ◎-○ / ◎-▲ / ○-▲（3点 BOX）| F本流 |
| ◎ ○ ▲ △ | 3点 BOX（△ は Step 2 候補に含めない） | △は Step 3 以降で「軸2頭+流し」素材 |
| ◎ ○ ▲ Ⅲ | 3点 BOX（Ⅲ は連系3着候補専用、Step 2 では未使用） | Ⅲ は三連系で活用 |
| ◎ 穴 | （未確定） | §3.5 開放論点 |

### 3.3 候補出力スキーマ（wide.py の generate() 戻り値）

[`base.py`](../../keiba-v2/ml/strategies/base.py) の `Bet` 既存スキーマを拡張せず使う。

```python
# 例: ◎○▲ 揃いの場合 (Bet 3 個を返す)
[
  Bet(
    race_id="2026052408050500",
    kind=KIND_WIDE,
    horses=[5, 11],            # ◎-○ ペア (馬番ソート済)
    stake_hint=100,            # portfolio 層で上書きされる初期値
    reason="My印 ◎-○",
    mark_pattern="3strong",
    strategy_name="wide_marker",
    formation_type="box_pair",  # 単ペアは box_pair / 3点は box_triple
    raw_legs={"box": [5, 11], "combo_count": 1},
  ),
  Bet(race_id=..., horses=[5, 14], ..., raw_legs={"box": [5, 14], "combo_count": 1}),
  Bet(race_id=..., horses=[11, 14], ..., raw_legs={"box": [11, 14], "combo_count": 1}),
]
```

> **note**: 14 章 §2.3.2 では BOX を `{box: [a,b,c], combo_count: 3}` で 1 ticket にまとめる定義だが、ここでは敢えて **1 ペア = 1 Bet** に分解する。理由は (a) 配分計算 (§4) で 1 ペア単位で削除/圧縮したい、(b) BT で「◎-○ だけ ROI 高い」のような分析がペア単位で必要。ledger 書き込み時に portfolio.py 側で raw_legs.box を集約するか分散保持するかを決める（§6.2 で確定）。

### 3.4 「◎ が無いレース」を Step 2 対象外にする理由

- F戦法の核心は ◎ 軸（[09 §3.1](./09_MY_MARKS_AND_STRATEGY.md)）
- ◎ 無し × ○▲ あり = ふくだ君が「軸を持たない」レース = システム側で勝手にワイド組むのは「ふくだ意図に踏み込みすぎ」
- ◎ 無しレースは Step 1 単勝も走らない（[tansho.py L78-79](../../keiba-v2/ml/strategies/tansho.py)）と整合

### 3.5 開放論点（ふくだ君判断仰ぐ）

| # | 論点 | カカシ案 |
|---|---|---|
| Q1 | `◎ 穴` (◎と穴のみ) のワイド候補を出すか？ | **出す**（穴は◎より優先される可能性があるため、ペアの相手として有効）。`raw_legs={"box": [◎umaban, 穴umaban]}` |
| Q2 | `◎ ○ 穴` のような「穴入り 3 強型」を ◎-○-穴 の 3点 BOX とするか？ | **出す**（穴を ▲ 相当として扱う）。pattern_label 集計で後付け分類できれば運用 OK |
| Q3 | △ を Step 2 候補に含めるべきか？ | **含めない**（Step 3 軸2頭+流しで活用）。Step 2 は ◎○▲ + 穴 までに絞る |

---

## 4. 配分計算（Step 2 の本質）

### 4.1 算法

```
入力:
  raceLimit          = bankroll.resolveLimits(raceId).raceLimit  # 円
  bets               = [Bet, Bet, ...]                            # Step1 単勝 + Step2 ワイド候補
  MIN_STAKE_YEN      = 100                                        # JRA-IPAT 最小単位

手順:
  1. 等額候補額 = floor(raceLimit / len(bets) / 100) * 100
  2. 等額候補額 >= MIN_STAKE_YEN なら → 全ベットに等額配分。終了
  3. < MIN_STAKE_YEN なら → 優先度の低いベットから 1 個ずつ削り、 1. を再試行
  4. 全部削っても 1 ベット = MIN_STAKE_YEN に収まらない場合は portfolio_status=skipped

優先度 (低→高):
  ワイド ○-▲ <  ワイド ◎-▲  <  ワイド ◎-○  <  単◎
  (◎ を含むペアを残す / 単◎ は最後まで残す)
```

### 4.2 計算例

**例1**: ◎○▲ 揃い、 raceLimit=3,000円
- 候補: 単◎ + ワイド3点 = 4 bet
- 等額: 3,000 / 4 = 750 → 700円 (100円単位下切り)
- 結果: 単◎=700, ワイド◎-○=700, ワイド◎-▲=700, ワイド○-▲=700, 合計 2,800円

**例2**: ◎○▲ 揃い、 raceLimit=300円
- 候補: 4 bet
- 等額: 300 / 4 = 75 → 100円未満
- 優先度低い `ワイド○-▲` を削除 → 3 bet → 300/3=100円OK
- 結果: 単◎=100, ワイド◎-○=100, ワイド◎-▲=100, 合計 300円

**例3**: ◎ のみ、 raceLimit=3,000円
- 候補: 単◎ 1 bet のみ
- 等額: 3,000 → そのまま単勝に 3,000円
- 結果: 単◎=3,000円（Step 1 と同じ挙動）

### 4.3 race_overrides との関係

[bankroll/limit-resolver.ts §4.1](../../keiba-v2/web/src/lib/bankroll/limit-resolver.ts) の `resolveLimits(config, raceId)` をそのまま使う。race_overrides で per_race_max_yen が上書きされていれば、それが raceLimit に入ってくる。配分側で意識する必要なし。

### 4.4 Step 3-4 への伏線

- 等額配分のロジックは `portfolio.py` の private 関数 `_allocate_equal()` に閉じ込める
- Step 3 で `_allocate_ev_weighted()` / `_allocate_kelly()` を追加する余地を残す
- 既定は `allocation_mode="equal"`、 config で切替可能にする予定（Step 3 で `bankroll/config.json` に `allocation_mode` 追加）

---

## 5. ファイル構成と出力

### 5.1 新規ファイル

```
keiba-v2/ml/strategies/
├── base.py              (Session 126 既存)
├── tansho.py            (Session 126 既存)
├── wide.py              ★新規 §3
└── portfolio.py         ★新規 §4

keiba-v2/ml/sim/
└── ticket_sweep.py      ★新規 §8

data3/races/YYYY/MM/DD/
├── tansho_bets.json     (Session 126 既存)
├── wide_bets.json       ★新規 (wide.py 出力)
└── portfolio_bets.json  ★新規 (portfolio.py 出力 = 配分済の最終形)
```

### 5.2 `portfolio_bets.json` スキーマ案

```json
{
  "strategy": "F-Step2",
  "version": "1.0",
  "description": "Step 1 単◎ + Step 2 ワイド ◎-○-▲ BOX、等額自動圧縮",
  "mark_set": 1,
  "generated_at": "2026-05-24T08:30:00+09:00",
  "race_id_parse_verified_at": "2026-05-24T08:30:00+09:00 (sample=... dat=...)",
  "n_portfolios": 12,
  "total_stake_hint": 28400,
  "sources": { ... },
  "portfolios": [
    {
      "race_id": "2026052408050500",
      "portfolio_strategy": "F-Step2",
      "pattern_label": "3strong",
      "race_limit_yen": 3000,
      "race_limit_source": "absolute",
      "allocation_mode": "equal",
      "n_bets_before_squeeze": 4,
      "n_bets_after_squeeze": 4,
      "total_stake_yen": 2800,
      "bets": [
        {"kind": "tansho", "horses": [5],     "stake": 700, "reason": "My印◎"},
        {"kind": "wide",   "horses": [5, 11], "stake": 700, "reason": "My印 ◎-○"},
        {"kind": "wide",   "horses": [5, 14], "stake": 700, "reason": "My印 ◎-▲"},
        {"kind": "wide",   "horses": [11, 14], "stake": 700, "reason": "My印 ○-▲"}
      ],
      "squeeze_history": []
    },
    {
      "race_id": "2026052408050600",
      "portfolio_strategy": "tansho_ippon",
      "pattern_label": "1strong",
      "race_limit_yen": 3000,
      "n_bets_after_squeeze": 1,
      "total_stake_yen": 3000,
      "bets": [
        {"kind": "tansho", "horses": [3], "stake": 3000, "reason": "My印◎"}
      ]
    }
  ]
}
```

### 5.3 wide_bets.json と portfolio_bets.json の二段構え

- **`wide_bets.json`** = wide.py 単独出力 (BT 評価・デバッグ用、配分前)
- **`portfolio_bets.json`** = portfolio.py 出力 (実購入の SoT、配分済)

vb_refresh / FF 生成は **`portfolio_bets.json` のみ** を読む。`wide_bets.json` は BT / 分析用に残すだけ。

---

## 6. ledger v2 への接続

### 6.1 portfolio_strategy の命名

| 状況 | portfolio_strategy |
|---|---|
| Step 1 単◎ のみ（◎しか印なし）| `"tansho_ippon"` |
| Step 2 F: 単◎ + ワイド（◎○ / ◎▲ / ◎○▲ いずれか）| `"F-Step2"` |

### 6.2 raw_legs の保存粒度

Step 2 では **ワイド BOX を 3 ticket に分散** して書き込む（§3.3 の理由 (b) — ペア単位の BT 分析が後で効くため）。

```jsonc
// 14 §2.3.2 のスキーマ「BOX 1 ticket」 ではなく、 §2.3.1 単一買い目の繰り返しで書く
{
  "portfolio_id": "pf-20260524-K05-A",
  "portfolio_strategy": "F-Step2",
  "tickets": [
    { "ticket_id": "...#t1", "bet_type": "tansho",
      "formation_type": "single",
      "raw_legs": { "horses": [5] },
      "total_amount": 700 },
    { "ticket_id": "...#t2", "bet_type": "wide",
      "formation_type": "single",   // box ではなく single (1ペア)
      "raw_legs": { "horses": [5, 11] },
      "total_amount": 700 },
    { "ticket_id": "...#t3", "bet_type": "wide",
      "formation_type": "single",
      "raw_legs": { "horses": [5, 14] },
      "total_amount": 700 },
    { "ticket_id": "...#t4", "bet_type": "wide",
      "formation_type": "single",
      "raw_legs": { "horses": [11, 14] },
      "total_amount": 700 }
  ]
}
```

`formation_type:"box"` は **Step 3 以降の 3頭以上 BOX**（馬連 BOX や三連複 BOX）で初めて使う。Step 2 ワイドは「単一ペアの繰り返し」として扱う。

### 6.3 portfolio_id seq

[14 §3.1.2 `assign_portfolio_seq()`](./14_LEDGER_SCHEMA.md) をそのまま使用。Step 2 で「F-Step2 + 独立単勝」のような併存が現実に起きた場合、seq=A (F-Step2) / seq=B (独立) で自然に分離される。

---

## 7. UI / approve フロー

### 7.1 Step 2 では本格 approve UI は作らない

- ふくだ君方針「個別判断・最終決定は人」は Phase 0 見える化で代替
- `portfolio_bets.json` を Web UI で表示する画面 (Phase 0) があれば、見て手動で IPAT 投票 = Step 2 の運用形
- approve ボタン本実装は Step 3 (馬連/馬単) と同時着手

### 7.2 候補の透明性

`portfolio_bets.json` には以下を必ず含める：

- `n_bets_before_squeeze` / `n_bets_after_squeeze` — 圧縮で何点削ったか
- `race_limit_source` — 上限がどこから来たか (override / absolute / percent)
- `squeeze_history` — 削られたベットの記録 (空配列 OK)

「お金の経路の透明性は防衛ラインの一部」（シズネ [10 §5.3](./10_BANKROLL_CONTROL.md)）に整合。

---

## 8. BT 評価計画（ticket_sweep）

### 8.1 評価軸

| 軸 | 比較対象 |
|---|---|
| ROI | Step 1 単独 vs Step 1+2 portfolio |
| 的中率 | ワイド単独 (◎-○ / ◎-▲ / ○-▲ 別) |
| MaxDD | portfolio の最大ドローダウン |
| 印パターン別 ROI | 1strong / 2strong / 3strong / ana_focus |

### 8.2 データ期間

- **Train 期間**: 既存 polaris BT との整合性から 2024-04-01 〜 2026-03-31 (約 2,900 races, 印あり race の subset)
- **OOS 期間**: 2026-04-01 〜 2026-05-24 (Session 123 / 125 と同じ窓)
- **印データ取得元**: TARGET DAT (現状) + my_marks_v2 (Session 125 以降)

### 8.3 出力

`data3/analysis/ticket_sweep/{run_id}/`:
- `summary.json` — 全体メトリクス
- `per_pattern.json` — 印パターン別
- `per_pair.json` — ワイドペア別 (◎-○ / ◎-▲ / ○-▲)
- WebUI `/analysis/ticket-sweep` で可視化（Step 2 完成時に追加）

### 8.4 ticket_sweep は Step 2 必須条件か？

**Step 2 受け入れ基準には含めない**。理由：

1. ticket_sweep は **配分検証** が目的だが、Step 2 は「愚直に等額」で固定する方針
2. EV/Kelly ベース配分の判断材料が必要になるのは Step 3 着手時
3. Step 2 では「印あり race で portfolio_bets.json が正しく生成される」が受け入れ基準（[06 §6.5.2](./06_PHASED_ROADMAP.md) と整合）

ticket_sweep は Step 2 完成後に「Step 3 着手前の必須インプット」として並走着手する。

---

## 9. リスク観点（シズネレビュー向け予備）

カカシ視点での想定リスク。シズネ先生レビューで追加・差し戻し前提。

1. **等額配分は EV を均す罠**: 高EVベットと低EVベットを同額にすると期待値最大化を逃す。Step 2 では BT で実害計測 → Step 3 で対処、と段階処理する
2. **3点 BOX で raceLimit < 400円 のエッジケース**: §4.2 例2 で削られるベットの優先度ロジックが「◎を残す」前提だが、実運用で raceLimit=300円のような極小ケースは現実的か要確認
3. **wide_bets.json と portfolio_bets.json の二重書き込み競合**: 同一日に複数回 vb_refresh が走ったとき、 atomic 書き込み + lock が必要（Session 126 の atomic-write 共通化を Python 側にも展開する必要あり）
4. **ledger v2 ticket 分散 (§6.2) の集計クエリ複雑化**: 14 §3.3 集計 API がワイド BOX を 3 ticket として扱う必要 → group by raw_legs.box 相当の処理が要る
5. **印不足ケースのフォールバック未定義**: §3.5 Q1-Q3 が未確定だと wide.py の generate() で対象判定が曖昧になる
6. **既存 vb_refresh パイプラインへの統合タイミング**: tansho_bets.json は Session 126 で書かれているが、 portfolio_bets.json は新規。 vb_refresh が読む先を切り替える際の互換性
7. **bankroll daily_limit との関係**: per_race_max_yen で配分しても、 当日複数レースで daily_limit_yen を超えるケースの扱い (現状 raceLimit のみ参照)
8. **印パターン `穴` 入りのスキーマ仕様化漏れ**: §3.5 Q1-Q2 が決まらないと raw_legs.box にどの馬番を入れるか定義できない

---

## 10. 実装タスク（依存順）

### 10.1 Phase A: 設計確定（このセッション）

- [x] 本書ドラフト作成（カカシ）
- [ ] §3.5 Q1-Q3 ふくだ君判断
- [ ] シズネ先生レビュー → must-fix 取り込み

### 10.2 Phase B: 戦略層実装（次セッション）

- [ ] `ml/strategies/wide.py` — 候補生成（§3 仕様）
- [ ] `ml/strategies/portfolio.py` — 等額配分（§4 仕様）
- [ ] pytest: 配分計算（§4.2 例1-3 を必ずテスト化）
- [ ] CLI: `python -m ml.strategies.portfolio --date YYYY-MM-DD`
- [ ] `portfolio_bets.json` 書き出し動作確認

### 10.3 Phase C: ledger v2 接続

- [ ] `keiba-v2/ml/purchase_ledger/` 配下に v2 スキーマの I/O 実装（[14 §10.3](./14_LEDGER_SCHEMA.md)）
- [ ] portfolio.py から ledger v2 への書き込み配線
- [ ] `_index.jsonl` の SHA256 追記
- [ ] portfolio_id seq の `assign_portfolio_seq()` 実装

### 10.4 Phase D: Web UI 接続（Phase 0 見える化の Step 2 対応）

- [ ] `/auto-purchase` 画面で portfolio 単位の表示（既存 race 単位を portfolio 単位に変更）
- [ ] `portfolio_bets.json` を読む API 追加
- [ ] 圧縮履歴の表示（squeeze_history）

### 10.5 Phase E: BT（後回し可、Step 3 前必須）

- [ ] `ml/sim/ticket_sweep.py` — §8 仕様
- [ ] WebUI `/analysis/ticket-sweep` 追加
- [ ] OOS 評価レポート（Step 2 完成後 2-3 週間運用してから）

---

## 11. 開放論点（ふくだ君判断仰ぐ）

| # | 論点 | カカシ案 |
|---|---|---|
| Q1 | `◎ 穴` のワイド候補を出すか？ | 出す（§3.5 Q1）|
| Q2 | `◎ ○ 穴` を ◎-○-穴 3点 BOX にするか？ | 出す（§3.5 Q2）|
| Q3 | △ を Step 2 候補に含めるか？ | 含めない（§3.5 Q3）|
| Q4 | wide_bets.json と portfolio_bets.json の二段構え（§5.3）に同意？ | 同意推奨（BT 用に分けたい）|
| Q5 | ledger v2 で BOX を 3 ticket に分散保持（§6.2）に同意？ | 同意推奨（ペア単位の BT 分析必須）|
| Q6 | Step 2 受け入れ基準に ticket_sweep BT を含めない（§8.4）に同意？ | 同意推奨（Step 3 入口で実施）|

---

## 12. 次のアクション

- [ ] **ふくだ君**: §11 Q1-Q6 判断
- [ ] **シズネ先生**: 本書全文レビュー（特に §4 配分計算、§6 ledger スキーマ整合性、§9 リスク観点の漏れ）
- [ ] **カカシ**: Q1-Q6 確定 + シズネ must-fix 取り込み後、Phase B 着手（wide.py + portfolio.py 実装）

---

> Step 1 の単◎は 1 ticket × 1 portfolio という最小構成。Step 2 は **1 portfolio に複数 ticket を束ねる最初の段階** で、ここで配分ロジックと ledger v2 の portfolio 概念が初めて意味を持つ。あえて愚直に等額で組んで、BT で歪みを見つけてから Step 3-4 で進化させる戦略。 — カカシ
