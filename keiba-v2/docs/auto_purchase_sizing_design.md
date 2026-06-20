# multi-bettype 自動投票 — 選定→配分 設計書

> **対象**: 全レース multi-bettype 自動投票（`bettype_scheduler`）の「どの券種を買うか（selection）」
> →「いくら賭けるか（sizing）」のパイプライン。VB判定の旧設計（`betting_system_design.md`）とは
> 別系統。
> **正本ステータス**: この doc が selection/sizing の設計正本。最終更新 = Session 165（2026-06-20）。
> 本番サイザー = `fixed_grade_v2`（全レース買う）。三層/二層(見送りゲート)路線は §3.7 で正式棄却。
> **関連メモリ**: `[[auto-purchase-project]]` `[[bet-adjustment-items]]` `[[feedback_betting_philosophy]]`
> `[[payout-ceiling-strategy]]` `[[bet-template-lab]]`

---

## 0. 本番の現在地（Session 163 時点）

| 項目 | 値 | 備考 |
|---|---|---|
| 起動 | `bettype_auto.bat`（`KeibaBettypeAuto` タスク・毎日 09:30-18:00 / 1分間隔） | `setup_bettype_scheduler.bat` で登録（管理者必須） |
| 戦略 (strategy) | `concentrate` | bat が `--strategy concentrate` を明示 |
| サイザー (sizing) | **`fixed_grade_v2`** | bat が `--sizing fixed_grade_v2` を明示 |
| per_race 上限 | 3000円 | config |
| per_day 上限 | 30000円（net 収支ベース） | `--per-day-max-yen` / 回収額を差引（Session 159） |

⚠️ **`DEFAULT_SIZER` 定数 = `fixed_grade_v1`** だが、bat が `--sizing fixed_grade_v2` を明示するため
**live は v2 が効く**。`DEFAULT_SIZER` は `--sizing` 省略時のフォールバックに過ぎない（live では未使用）。

---

## 1. パイプライン全体像

```
predictions.json (各馬 pred_proba_w_cal / pred_proba_p / odds / place_odds_min …)
  │
  ├─ bettype_efficiency.process_race(axis=composite◎)
  │     → RaceEfficiency: 各 plan(券種×幅) の synthetic_odds / EV / odds_legs を計算
  │       軸◎ = composite (W/P/ADR) 最強（= AI印◎）
  │
  ├─ bettype_selection.evaluate_and_select(strategy=concentrate)
  │     → どの券種plan を buy するか選定（後述 §2）
  │
  └─ bettype_sizing.size_race_fixed_grade_v2(selection, per_race_cap=3000)
        → 各 plan に金額を割り当て（後述 §3）→ RaceSizing(SizedLeg のリスト)
              │
              └─ bettype_scheduler → target_clicker(runner) → TARGET/IPAT 投票
```

軸◎は **composite 最強（= AI印◎・実力本命）**。`hole_seeker`（妙味軸）は項目3の「無印買い」問題
（[[bet-adjustment-items]]）があるため本番は使わず、`concentrate`（AI印◎軸）固定。

---

## 2. selection（券種選定）= `concentrate`

各 plan を以下で fund 判定する（`bettype_selection.should_fund` / `_select_concentrate`）。

### 2.1 アンカー（単勝◎ / 複勝◎）= 常に fund
軸◎そのものの素直な買い方。EV floor で足切りしない（EV<1.0 の低オッズ本命も候補に残す）。
※ただし sizing 側で複勝は本番不採用（§3.3）。

### 2.2 複合券種（馬連〜三連単）= 2つのゲートの AND
1. **EV ゲート**: `EV >= DEFAULT_COMBO_EV_FLOOR`（**0.85**）
2. **merit ゲート**: `vs_tansho == 'gt'`（合成オッズ > 単オッズ = 広げる相対妙味あり）

#### combo EV floor = 0.85 の根拠（Session 163）
- 旧 `EV >= 1.0`（= `DEFAULT_EV_FLOOR`）では、**控除率20%で combo の EV はほぼ常に <1.0** →
  combo が一切選ばれず **27%のレースが「単のみ」bet** になっていた（fixed_grade_v2 は「単薄く
  combo 厚く=天井を取る」思想なのに配分先 combo が selection 段階で消滅）。
- 実払戻 2 期間 sweep（`sweep_combo_ev_floor.py`）で **0.85 が最適**:
  P1 単のみ27%→15%・ROI 77.7→79.1%・DD 465k→434k / P2 24%→11%・80.4→80.7%・DD↓。
- **0.70 は下げすぎ**: 券種別×EV帯ROIでは 0.70-0.85帯が最良（馬連103/三連複122/三連単102）に
  見えるが、それは「券種別 最良1plan」の数字。floor を 0.70 にすると EV 0.70-0.85 の plan が
  **複数束で選ばれ点数が増え、当たらない点が増えて DD が膨張**（両期間で ROI -0.6pt）。
  = 個別券種ROIに釣られると束効果を見落とす。戦略全体の実払戻では 0.85 が最適点。
- 1.0 に戻せば旧挙動（リバーシブル）。`combo_ev_floor` 引数で上書き可。

---

## 3. sizing（配分）= `fixed_grade_v2`

**★Kelly は使わない★**（哲学§5「配分はオッズで歪めない」を文字通り実装）。配分は
**◎の格 = composite gap（◎と○の差）** で決める **固定割合**（オッズ非依存）。

### 3.1 tier（◎の格）
`gap = axis_composite − max(other_composite)` で測る（z絶対値でなく gap = 団子と本命断然を区別）。

| tier | gap | 意味 |
|---|---|---|
| strong | >= 1.0 | ◎が○から抜けている（本命断然） |
| mid | 0.4–1.0 | 手頃な◎ |
| weak | < 0.4 | ◎と○が僅差の団子 |

### 3.2 配分割合 `FIXED_SHARES_V2`（単 share / 複 share、残り = combo）
| tier | 単 | 複 | combo |
|---|---|---|---|
| strong | 15% | **0%** | 85% |
| mid | 30% | **0%** | 70% |
| weak | 15% | **0%** | 85% |

- **山型**: ◎断然(strong)=単で当てても天井低い→単薄く combo 厚く。mid(手頃な◎)=単で取れる→単最厚。
  weak(団子)=軸不確実→単薄く流しへ（ふくだ「単で当てても儲からないなら三連単で」）。
- combo は per_race 残予算を **EV比例**で各 plan に配分 → plan 内は **逆オッズ配分**（合成オッズ定義
  stakeₖ∝1/oₖ と整合・排反/相関を考慮した保守的 widen）。

### 3.3 複勝 = 0%（メインから外し複勝専門キャラへ移譲・Session 163）
- ふくだ「ワイドや単より安く数十円取りにいくゴミ複に意味があるのか」→ 実払戻で実証:
  **複の53%がゴミ複（複オッズ<1.5倍 & combo に埋もれ）・複が当たっても利益の中央値80円・
  57%が+100円未満**。ROI 85% は「+30〜80円の手堅い的中」が支えていただけ（金は増えず当たった感）。
- 複勝の価値（高的中・死なない ROI85%）は **複勝専門キャラ（転がし党/本命党）が別 bankroll で回収**。
  メインは「天井を取る」（単+combo）に専念。→ `FIXED_SHARES_V2` の複 share = 0。
- ★トレードオフ承知★: メイン単体 ROI -0.7〜-1.5pt・的中率58→37%（複の手堅い回収を失う）。が
  複勝はキャラが拾うのでシステム全体では収益源を失わない（別レイヤーへ移譲しただけ）。

### 3.4 ★使い切り保証★（Session 163）
combo が出ない/薄いレースで cap が大量に余ると「単400だけ」で 3000円中 400円しか使わない問題が
起きる（残予算が宙に浮いて消える構造）。→ **combo配分後の残余を単勝◎に上乗せして cap を使い切る**
（ふくだ「残余は単に上乗せ・複は復活させない」）。単 leg があれば増額、無ければ残余で単勝◎を新規。
`axis_odds` 無効時は上乗せしない（単勝が買えないので無理に他券種へ回さない）。

### 3.5 見送りゲート = 無効（`SKIP_MAX_ODDS_FLOOR=0.0`・Session 163）
v2 には当初「最大合成オッズ（配当の天井）< 5.0倍なら降りる」見送りゲートがあったが、
**実払戻検証で害と確定 → 無効化**。降りる対象（堅い高的中レース）の方が買う群より ROI が高かった
（2期間で再現）＝オッズ依存ゲートの後知恵の罠（[[feedback_odds_gate_hindsight]]）。

### 3.6 複勝→ワイド置換 = 無効（`WIDE_SWAP_PLACE_ODDS_FLOOR=0.0`・Session 161）
低オッズ複勝をワイドに置換するロジックも実払戻で一律マイナス（低オッズ複勝は当たりやすく実回収率
が高い）→ 無効化。コードは券種別再検証の足場として残置。

### 3.7 三層/二層サイザー = ★棄却★（Session 164-165・本番不採用）
ふくだ哲学「天井1000%超の価値」「堅いだけのレースは見送る」を直訳した
`three_tier_sizing.py`（勝負15%/様子見3%/見送り）/ `two_tier_sizing.py`（勝負/見送り）を
設計・実装・実払戻 bench したが、**ceiling 見送りゲートは 1000%→400% に緩めても害**と確定。
本番は `fixed_grade_v2`（全レース買う）を維持。コードは registry 残置（参照用）。

**棄却の決定的根拠（`bench_two_tier_v0.py` の着順検証・P1/P2 実払戻）**:
- two_tier が「◎堅い & ceiling<400%」で見送ったレースの着順を調べると、**P1=35件中32件(91%)・
  P2=105件中88件(84%)が「◎が3着内に来て AI印4頭(◎○▲△)で組める券面が400%超」**＝
  axis=◎ で実際に取れたはずの妙味だった（◎飛びの hindsight は P1=3件/P2=17件のみ）。
- 対照群 `shobu_only_no_ceiling`（ceilingゲートを抜く）の方が ROI が高い（P2: 60.7% > 54.3%）
  ＝ゲートの純害。
- 二層化自体が全買い `v2_cap3000` に大きく劣後（P1 ROI 79.0% vs 62.3%・winR 40% vs 28%・
  P1 では bankroll=100万でも破綻）。勝負層を絞ると的中率と件数が落ち、配当の偏りで bankroll が溶ける。

**学び**: 162→163→164→165 と「見送りゲート」「天井ゲート」「ceiling 400%」と名前を変えて
3回試したが、**確定オッズで「堅いレースを切る」発想は実払戻で一貫して害**（[[feedback_odds_gate_hindsight]]）。
「天井低い=堅い=妙味なし」は嘘で、堅い◎ほど高的中で回収していた。判定変数の名前を変えても
本質構造（◎断然=堅い高的中Rを切る＝後知恵）は変わらない。

---

## 4. 検証ハーネス（`ml/analyze/`）

| スクリプト | 何を検証するか | 結論 |
|---|---|---|
| `validate_v2_skip_gate.py` | 見送りゲートの実払戻（降りた群をもし買えば） | ゲートは害→無効化 |
| `compare_fukusho_share.py` | 複あり/無し/半分の実払戻ROI・天井・DD | 複ROIは単より良いが役割無し→キャラへ |
| `axis_winplace_by_odds.py` | 軸◎の単/複ROIを軸オッズ帯別に | 複は断然(1-2倍)で最良(95%)・中穴は不安定 |
| `sweep_combo_ev_floor.py` | combo EV floor の単のみ率/ROI/DD sweep | 0.85最適・0.70は束効果でDD膨張 |
| `backtest_template_ceiling.py` | ラボ12テンプレを天井視点(≥1000%率/P90P99) | 複勝堅実党は天井無し・combo系が天井を取る |
| `bench_three_tier_v0.py` | 三層(勝負/様子見/見送り)の実払戻4戦略並列 | 様子見不発火・bench欠陥4件(S164) |
| `bench_two_tier_v0.py` | 二層+ceiling400% の実払戻 + same-case着順検証 | ceilingゲートは害(8-9割◎絡みで取れた)→棄却(S165) |

**検証規律**:
- 精算は **haraimodoshi 実払戻**（cache の combo payout 近似は使わない）= [[feedback_combo_backtest_settlement]]。
- オッズ依存のゲート/条件は **predictions 直前オッズ**（リークなし・本番同条件）で検証 = [[feedback_odds_gate_hindsight]]。
- floor/閾値は実払戻 sweep で決める（思想だけで決めない）。

---

## 5. 残課題（次セッション以降）

1. **★メインレースの単フル張り問題**（[[bet-adjustment-items]] 項目8・来週宿題）: combo の EV が極端に
   低いメインR（東京11/阪神11=軸2.4-2.7倍・combo最良EV 0.3-0.46）で combo 全弾き → 使い切り保証で
   単3000フル張り。低オッズ本命に単3000フルは妙味薄→降りる/薄くする or 天井基準のボーナス少額枠を検討。
   ※オッズ依存の降りる判断は後知恵の罠に注意＝実払戻検証必須。
2. **複勝専門キャラ/本命党(単複)キャラを立てる**（複の移譲先・[[character-betting-personas]]）。
3. **本丸=ラボの天井テンプレを投票に配線**（[[lab-wiring-project]]・template_flat 実装済）。

---

## 6. 変更履歴

| Session | 変更 | commit |
|---|---|---|
| 140-141 | multi-bettype 自動投票 v1（selection + sizing）骨格 | — |
| 159 | per_day 上限を net 収支ベースに | b123b73 |
| 161 | fixed_grade_v1 新設（評価ベース固定配分・Kelly撤廃）/ 複→ワイド置換棄却 | — |
| 162 | fixed_grade_v2（山型配分 + 見送りゲート）/ template_flat 実装 | — |
| 163 | 見送りゲート無効化 | c544da5 |
| 163 | AI直前印(購入連動印 markSet3) を settle後に日次配線 | ed29e79 |
| 163 | 複勝をメインから外す（複share=0）+ 検証ハーネス | 2c43563 |
| 163 | combo EVゲート 1.0→0.85（「単のみ」bug修正） | a86e31a |
| 163 | 使い切り保証（残余→単上乗せ）+ combo floor 0.85確定 | 265e7e3 |
| 164 | three_tier_v0 実装（勝負15%/様子見3%/見送り）/ bench欠陥4件で昇格凍結 | — |
| 165 | two_tier_v0 実装 + ceiling 1000→400% 再走 / **着順検証でゲートは害と確定 → 三層/二層路線を正式棄却・v2維持** | — |
