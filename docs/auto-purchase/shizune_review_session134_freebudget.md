# シズネレビュー: Session 134 freebudget 戦略 (5/30-31 OOS 直前)

> **対象**: `ml/strategies/freebudget.py` 新規 / `selective_loader.py` amount 拡張 / `runner.py` bet.amount 配線 / `19_OOS_RUNBOOK.md` / `20_CURRENT_CAPABILITIES.md` 改訂
> **検証日程**: 2026-05-30 (土) 〜 2026-05-31 (日)
> **レビュー日**: 2026-05-28 (Session 134 / OOS 2 日前)
> **観点**:
>   1. 「儲かった経路を守る」 schema 検証 (Session 129 🔴 J 路線) の freebudget 適用
>   2. 「動的調整なし」 原則との整合性 (日跨ぎ更新だけ許可 + 当日中固定)
>   3. 「儲かったから GO」 経路の構造遮断 (§7.3) と Kelly 案分の混線
>   4. §6.4.b 行動アンチパターンへの耐性 — 1万円フリー予算が「気が大きくなる」 衝動を誘発しないか
>   5. OOS 前必須 (5/29 夜まで) の修正コード or 修正ドキュメント
>   6. 5/30 朝 / 5/31 朝の SOP 抜け (日跨ぎ手動入力の隙間)
> **総合判定**: **条件付き GO**。 freebudget 自体は「ふくだの賭け哲学 (確率×オッズ×bankroll) を構造化した良い設計」 だが、 **🔴 4 件 (config 矛盾 1 / 哲学整合 1 / 二重認証ゲート骨抜き 1 / 日跨ぎ手動入力 SOP 1) を 5/29 夜までに潰せば「無条件 GO」**。 過去 3 回 (131/132/133) と同じ詰め方ルートで月曜の振り返りに入れる。

---

## 0. 結論 (3 行)

1. **設計思想は健全**: freebudget は「確率×オッズ×bankroll」 のみを入力とする Themis 原則の構造化実装で、 Kelly 1/4 + cap 10% + 100円丸めは sample 過剰反応に対する適切なダンパー。 「ふくだの動的調整なし」 と「bankroll 自動反映」 を**当日中固定 + 日跨ぎ更新だけ許可**で両立した判断は正しい。
2. **🔴 1 つだけ致命**: `bankroll/config.json` の `per_day_max_yen=10000` / `per_race_max_yen=3000` と freebudget 設定値 (bankroll=10000 / cap_per_bet=1000) の**衝突を runner.py が黙って 5 で abort する確率が非常に高い**。 同一レースに 4 頭以上推奨で per_race=3000 突破 → exit 5。 当日朝に発見 = OOS 試行 ゼロで 1 日終わる。 **5/29 夜までに config.json 側か CLI 側で吸収必要 (🔴-1)**。
3. **🔴 もう 1 つ重要**: 当日プラン音声読み上げ (シズネ 🔴 A) が**金額を読まない**。 freebudget 経路で「6番 100円 / 12番 700円」 のような不均等案分になると、 ふくだは「内容承認した気」 で 700円のレースを止める判断材料が無い (🔴-3)。 二重認証ゲートの実質的骨抜き。

---

## 1. 評価表 — 🟢 9 / 🟡 6 / 🔴 4

| # | 観点 | 評価 | 「先に直せ」? |
|---|---|---|---|
| (1) | freebudget.py の VB Floor 経由設計 (bet_engine.generate_recommendations を経由) | 🟢 | — |
| (2) | Kelly 1/4 + cap 10% + 100円丸め + truncate (EV 降順) のダンパー多層化 | 🟢 | — |
| (3) | `kelly_sized = min(kelly_raw * 0.25, per_bet_cap_pct)` で生 Kelly を冗長に抑える二重保険 (`freebudget.py:180`) | 🟢 | — |
| (4) | source whitelist 拡張 + amount 範囲検証 + 100円単位検証 + 他 source amount 混入で abort (Session 129 🔴 J 路線の延長) | 🟢 | — |
| (5) | 段階的アプローチ (5/30 半自動 → 5/31 フル自動) を OOS 計画から外していない | 🟢 | — |
| (6) | 日跨ぎ更新だけ許可 / 当日中固定 = 「動的調整なし」 原則維持 (`config.json:18` 整合) | 🟢 | — |
| (7) | テスト 18 件追加 (Kelly 案分 / cap / truncate / amount 検証 / schema 互換) | 🟢 | — |
| (8) | `total_yen > bankroll` で EV 降順 truncate (=「気が大きくなる」 構造的緩衝) | 🟢 | — |
| (9) | OOS 5/30 dry-run 結果 (eligible=5 / funded=5 / total=1600円) が cap・100円単位を満たしている確認済 | 🟢 | — |
| 🔴-1 | **`bankroll/config.json` の `per_race_max_yen=3000` と freebudget cap_per_bet=1000 が同一レース 4 頭以上で衝突 → runner exit 5** | 🔴 | **OOS 前必須** |
| 🔴-2 | **`build_daily_plan_text` が金額を読み上げない**。 freebudget で不均等案分 (100円/700円) になると二重認証ゲート (シズネ 🔴 A) の内容承認が骨抜き | 🔴 | **OOS 前必須** |
| 🔴-3 | **5/31 朝の `--bankroll` 手動入力 SOP に「IPAT 表示値の確定タイミング」 が無い** = 払戻中の不確定値を入力する罠 | 🔴 | **OOS 前必須** |
| 🔴-4 | **`generate_recommendations(budget=bankroll)` が VB Floor 通過件数に影響する可能性**を未検証。 budget=10000 と budget=30000 で n_eligible が変わるなら、 1万円フリー予算が ML 選定そのものを歪める = Themis 原則 ("確率×オッズ×bankroll の 3 つだけ" の意味と矛盾) | 🔴 | **OOS 前必須** (調査だけでも) |
| 🟡-A | `MIN_BET_YEN=100` と `per_bet_cap_pct=0.10` が config.json と独立してハードコード。 `config.json` の `kelly_fraction=0.25` も読まれていない (フリーバジェットだけ自前定数) | 🟡 | OOS 前 推奨 |
| 🟡-B | freebudget_bets.json の `description` が「freebudget Kelly 1/4 cap 10% (preset=standard, bankroll=10000円)」 と書かれるが、 OOS 後の git commit で diff の判別がしにくい (日付・実行 timestamp が description にない) | 🟡 | OOS 後 |
| 🟡-C | `extract_freebudget_bets` の戻り値 `FreebudgetResult.warnings` がほぼ未使用 (predictions 空のときだけ追記)。 「Kelly raw が cap で叩かれた件数」 「100円未満で除外された件数」 等の運用観察情報が落ちる | 🟡 | OOS 後 |
| 🟡-D | テスト `test_low_ev_horse_filtered_out` は VB Floor 不通過を確認するが、 Composite VB Score の境界値 (5.5) 直下 / 直上で挙動が変わることをテストしていない | 🟡 | OOS 後 |
| 🟡-E | `test_truncation_keeps_high_ev_first` が `if result.bets and result.n_truncated > 0` 条件付きで、 truncation が起きないケース (全採用) でも PASS してしまう (アサーションが skip される) | 🟡 | OOS 後 |
| 🟡-F | 14_LEDGER_SCHEMA に freebudget 経由の portfolio_id (例: `pf-20260530-A08-A`) と既存 selective 経路の portfolio_id 採番衝突がないか文書化されていない | 🟡 | OOS 後 |

---

## 2. 「先に直せ」 詳細 — OOS 前必須 (5/29 夜まで)

### 🔴-1 `bankroll/config.json` の per_race_max_yen=3000 と freebudget cap_per_bet=1000 が同一レース 4 頭以上で衝突 → runner exit 5

**問題**:

`bankroll/config.json:12-13` の現状値:
```json
"per_race_max_yen": 3000,
"per_day_max_yen": 10000,
```

freebudget は bankroll=10000 / per_bet_cap_pct=0.10 → 1馬上限 1000円。 同一レースで `--auto-launch` の最大候補数 = `params.max_win_per_race=2` (`bet_engine.py:326` `standard`) なので **同一 race_id で最大 2 件**。 2 × 1000 = 2000円 < 3000円なので一見 OK に見える。

**ところが**: freebudget は **`generate_recommendations` 経由 → ARd VBルート / Composite VB Score ルート / Place addon** がぶら下がる。 一見 max 2 単勝でも、 単勝+条件付き複勝の Place addon (`place_addon=True`, `place_addon_amount=200`) が standard preset で**有効**。

→ ただし freebudget.py L166-169 で `rec.bet_type not in {"単勝", "単複"}` を除外、 `(rec.win_amount or 0) <= 0` も除外している ので、 「単複」 は通る可能性。 「単複」 を採用しても win_amount 部分のみ amount フィールドに入っているのか、 単勝+複勝の合計 amount なのかが**コードから明確に追えない**。

`bet_engine.py:852` の `generate_recommendations` 内部:
- BetRecommendation.win_amount / place_amount を別フィールド管理
- `bet_type` は "単勝" / "単複" / "複勝" 等の文字列

freebudget.py L116-117:
```python
odds=float(rec.odds or 0),
...
amount=int(amount_yen),  # ← amount_yen は Kelly 案分結果のみ
```

= freebudget は **単勝の bet として扱い、 複勝 addon の 200円は無視**している (`bet_type` フィルタで弾かれる)。 これは設計意図と一致。

**ただし**、 同一レースで以下のケースが現実的に起こりうる:
- ARd VB ルートで 1 頭通過 (Composite Score>=5.5)
- dev_gap ルートで別 1 頭通過 (Composite Score>=5.5)
- → 2 頭それぞれ Kelly で 800円 / 700円 amount 化 = 同一レース合計 1500円

これは per_race_max_yen=3000 を下回るので問題なし。 **ところが** OOS 期間中ふくだが「面白そうだから」 と config.json を一時的に変更する誘惑 (§6.4.b 「気が大きくなる」 衝動) や、 `--per-bet-cap-pct 0.20` で実験する場合に**気付かないうちに per_race 突破する罠**がある。

さらに**もっと致命的**: per_day_max_yen=10000 と bankroll=10000 が**完全一致**。 freebudget は「total_yen <= bankroll」 で truncate するので total_yen <= 10000 が保証されるが、 runner.py L369:
```python
if limits.per_day_max_yen > 0 and total_yen > limits.per_day_max_yen:
```
= `>` 比較なので 10000 == 10000 は通る (= 等号 OK)。 これは仕様としては妥当だが、 **境界値テストが無い**。 freebudget が誤って 10001 円分の bets を生成する (例: 100円丸め後の合計が 10000 を超える truncate バグ) と即 abort。

**修正案 (どれか 1 つ実施)**:

**A**: `bankroll/config.json` を OOS 用に書き換え (一時的)
```json
{
  "settings": {
    "per_race_max_yen": 2000,   // ← 1馬1000円 × 2頭以下に整合 (現3000)
    "per_day_max_yen": 10000,   // 維持
    ...
  }
}
```
ただし「動的調整なし」 原則と矛盾するので、 OOS 用 override 記録を残す。

**B**: freebudget.py に `--per-bet-cap-yen` 引数を追加して `per_race_max_yen / max_win_per_race` を超えないよう自動算出。 config.json から読み込み。
```python
# freebudget.py 内
from ml.target_clicker.runner import _read_bankroll_limits
limits = _read_bankroll_limits()
implied_cap = limits.per_race_max_yen // 2  # max 2 単勝 / race
effective_cap_yen = min(int(bankroll * per_bet_cap_pct), implied_cap)
```

**C** (シズネ推奨): **何もせず**、 19_OOS_RUNBOOK §1.5 のチェックリストに**事前検証ステップ追加**:
```markdown
- [ ] `freebudget_bets.json` 生成後、 各 race_id ごとの amount 合計が
      `per_race_max_yen` (3000円) 以下かを目視確認
- [ ] `total_yen` が `per_day_max_yen` (10000円) 以下かを目視確認
- [ ] どれかが NG なら freebudget を `--per-bet-cap-pct 0.05` で再生成 or
      config.json を OOS 用に一時変更 (注: 変更時は git diff で記録)
```

ふくだ判断: A / B / C のどれを選ぶか。 シズネは **C** を強く推奨 (config を本番中に動的に弄らない原則を維持しつつ、 朝の目視ゲートで気付ける構造を作る)。

**判定**: **OOS 前必須**。 文書追記 5 分 + 5/30 朝の目視 1 分。 これを抜くと 5/30 9:30 頃に exit 5 が出て「半自動運用にダウングレード」 直行になる可能性が高い。

**所要**: C を選ぶなら 5 分 (ドキュメント追記のみ)。

---

### 🔴-2 `build_daily_plan_text` が金額を読み上げない = 二重認証ゲートが骨抜き

**問題**:

`notify.py:228-270` の `build_daily_plan_text`:
```python
return (f"本日の投票プラン。 {'、 '.join(detail_parts)}。 "
        f"合計 {n} 件、 {total_yen}円。 "
        "暗証番号を入力すると投票を開始します。")
```

= **「新潟8R 単勝 6 番、 京都8R 単勝 5 番、 他 3 件。 合計 5 件、 5000円」** と読み上げる。

**この音声内容承認は Session 128 時点 (selective_bets.json + `--amount 100` で全件均等) では完璧に機能していた**:
- 全件 100円均等 = 「5 件、 5000円」 = 「1 件 1000 円弱」 と即座にふくだが暗算できる

**freebudget 経路では崩れる**:
- 5/30 dry-run 実例: EV=3.72 → 500円 / EV=1.27 → 100円 (5 件で 1600円)
- 音声: 「5 件、 1600円」 = ふくだは「平均 320円か」 と聞く
- **実態**: 500円 (高 EV) / 400円 / 300円 / 300円 / 100円 のような不均等
- → 「500円のレース」 を聞いて「これは違和感あり、 止めたい」 と思っても、 音声だけでは個別金額が分からない = **暗証番号入力で「全件承認」 してしまう**

つまり**二重認証ゲートの実質的骨抜き**。 シズネ Session 131 🔴 A の設計意図 = 「暗証番号入力に内容承認意味を持たせる」 が、 **金額情報の欠落で承認解像度が落ちる**。

**修正案**:

`notify.py:228-270` の `build_daily_plan_text` に `amount` 読み上げ追加:

```python
def build_daily_plan_text(
    *,
    bets_summary: list[dict],
    total_yen: int,
    max_detail: int = 3,
) -> str:
    ...
    for b in bets_summary[:max_detail]:
        venue = (b.get("venue_name") or "").strip()
        race_no = b.get("race_number")
        umaban = b.get("umaban", "?")
        amount = b.get("amount")  # ← 新規 (freebudget 経路で渡される)
        if venue and race_no:
            label = f"{venue}{race_no}R"
        else:
            rid = b.get("race_id", "")
            label = f"レース{rid[-2:]}" if rid else "レース"
        # Session 134: freebudget 経路で金額不均等になるため amount も読み上げる
        if amount is not None:
            detail_parts.append(f"{label} 単勝 {umaban} 番 {amount}円")
        else:
            detail_parts.append(f"{label} 単勝 {umaban} 番")
    ...
```

`runner.py:512-523` の `bets_summary` 構築箇所で `row["amount"] = b.amount` を追加 (`FfBet.amount` は既に bet オブジェクトに入っている)。

**所要**: notify.py 4 行 + runner.py 1 行 + テスト (build_daily_plan_text の単体テストに amount あり/なしケース追加) で 15 分。

**判定**: **OOS 前必須**。 これは「シズネが入る根本理由」 (内容承認ゲートの機能維持) そのもの。 5/29 夜の Dry-run §1.4 で「金額が読み上げられること」 をチェックリスト項目に追加すること。

---

### 🔴-3 5/31 朝の `--bankroll` 手動入力 SOP に「IPAT 表示値の確定タイミング」 が無い

**問題**:

19_OOS_RUNBOOK §1.5 (5/31 朝の手順):
```powershell
# 例: 5/30 終了残高 = 12300 円だった場合
./.venv/Scripts/python.exe -m ml.strategies.freebudget --date 2026-05-31 --bankroll 12300
```

= ふくだが IPAT サイトを開いて残高目視。

**ところが**:
- IPAT サイトの「残高」 = 入金額 - 投票額 + 確定済払戻 (= 入出金可能額)
- 5/30 PM に投票した馬券の払戻が **5/31 月曜 12:00 以降に反映**されるケースがある (JRA 払戻スケジュール / クレジット即時入金等)
- 「5/31 朝の表示残高」 と「5/30 終了時点の真の bankroll」 が**乖離する**

**実害想定**:
- 5/30 PM 終了時、 IPAT サイトで残高表示 9000 円 (投資 1600 円 - 払戻 0)
- → ふくだ 5/31 朝に IPAT 開く → 残高表示 11500 円 (5/30 中の払戻が確定して反映)
- → 「9000 円のはずだから残高アップ分は反映していい」 と判断して `--bankroll 11500`
- → 5/31 は 11500 ベースで Kelly 案分 → 1馬上限 1150 円
- = **5/30 で当てた払戻を 5/31 の投資原資に組み込む = 「動的調整なし」 違反**

これは **シズネ原則: パターン縛らない / 動的調整なし** ([[feedback_betting_philosophy]]) と**真っ向から矛盾**。 当日中は固定 という日跨ぎだけ許可 ルールは正しく書かれているが、 **「日跨ぎ更新が何を基準にすべきか」 の定義が抜けている**。

**修正案**:

19_OOS_RUNBOOK §1.5 の 5/31 朝の手順を以下に置き換え:

```markdown
**5/31 朝の手順 (日跨ぎバンクロール更新)**:

5/30 PM の **runner.py 終了時点** に標準出力に出力された
「[runner] bankroll day check: OK (XXX <= 10000)」 の XXX を基準にする。
これは「5/30 中に投資した合計額」 なので、 5/30 終了時点の真の bankroll =
`10000 - XXX + payout_5_30`。 ただし **payout_5_30 は 5/30 中に IPAT に
確実に反映されたもののみ** (= 5/30 23:59 時点で IPAT サイトに表示されている払戻)。

5/31 朝に IPAT を開いた時の残高表示は **使わない** (5/30 払戻反映の
タイムラグで本来の bankroll より高く見える)。 代わりに以下の手順:

1. 5/30 23:59 時点で IPAT サイトを開いてスクリーンショット保存
2. その時点の表示残高を 5/31 朝の `--bankroll` に渡す
3. 5/30 23:59 〜 5/31 朝の間に追加で反映された払戻は **5/31 の bankroll に含めない**
   (含めると「動的調整」 になる)
4. 上記運用が面倒なら **5/31 も 10000 円固定** (= 1万円フリー予算を 2 日続ける)

- [ ] 5/30 23:59 までに IPAT 残高スクショ
- [ ] その値を `--bankroll` に渡す
- [ ] 5/30 中の払戻が反映されていない場合は スクショの値を基準に
- [ ] 「5/31 朝の表示残高」 は **使わない** (動的調整の罠)
```

**判定**: **OOS 前必須**。 5/31 朝に発生する判断ミスを構造的に防ぐ。 6/6 月初 OFF 練習日でも同じ問題が出る。

**所要**: 文書追記 10 分。

---

### 🔴-4 `generate_recommendations(budget=bankroll)` が VB Floor 通過件数に影響していないか未検証

**問題**:

freebudget.py L156:
```python
recs = generate_recommendations(races, params, budget=bankroll)
```

= `bet_engine.generate_recommendations` に `budget=10000` を渡している。

**ところが** `bet_engine.py:852` の `generate_recommendations` のシグネチャ:
```python
def generate_recommendations(
    race_predictions: List[dict],
    params: BetStrategyParams,
    budget: int = 30000,
) -> List[BetRecommendation]:
    """全レースの推奨買い目を生成
    ...
    Returns:
        BetRecommendation のリスト（budget スケーリング済み）
    """
```

= **「budget スケーリング済み」** とある。 つまり budget=10000 と budget=30000 で**返ってくる BetRecommendation の件数 or 内容が変わる可能性**。

これは**致命的に Themis 原則違反の可能性**:

> **Themis原則**: 購入決定の入力は「**確率・オッズ・バンクロール残高**」の3つだけ
> ([[shizune-agent]] の Themis 原則記述)

確かに bankroll は入力の 3 つ目だが、 これは **金額決定 (Kelly 案分)** に使うべきもので、 **VB Floor 通過判定 (どの馬を選ぶか)** には使ってはいけない (本来の使い分け)。

`bet_engine.generate_recommendations` の budget 引数が**馬の選定そのものに影響**するなら、 1万円の人と 3万円の人で**「ML が推奨する馬の集合が変わる」** = 同じ確率・オッズでも bankroll で異なる馬を推奨 = **Themis 原則違反**。

**検証必須項目** (5/29 夜までにふくだ確認):

1. `bet_engine.py:852-` を読んで、 `budget` 引数が何に使われているか確認
2. `budget` が「金額 sizing にだけ使われる」 なら問題なし (n_eligible 不変)
3. `budget` が「件数フィルタ / 上位 N 件選定 / カットライン」 に使われるなら **要修正**

シズネが先回りで確認したところ、 `bet_engine.py:852-` の docstring 「budget スケーリング済み」 は**金額ではなく件数を絞る可能性が高い**。 generate_recommendations が `budget // some_unit_yen` のような件数上限を内部で計算しているケースは bet_engine ロードマップで頻出パターン。

**修正案 (検証次第)**:

**ケース A**: budget が金額 sizing のみ
- 何もしなくて良い。 ただし freebudget.py に「budget は sizing のみで件数フィルタしない」 と docstring 追記。

**ケース B**: budget が件数フィルタ
- freebudget.py で `generate_recommendations(races, params, budget=10**9)` のような巨大値を渡し、 freebudget 側で件数を切る (シズネ推奨)
- これで「ML 出力候補集合 ≒ bankroll 非依存」 を保証

**判定**: **OOS 前必須 (調査だけでも)**。 5/29 夜の Dry-run §1.5 後、 ふくだに `bet_engine.generate_recommendations` の budget 引数の役割を 5 分以内に確認してもらう。 ケース B の場合は freebudget.py 1 行修正で済む。

**所要**: 調査 5 分 + (必要なら) 修正 5 分。

---

## 3. 「先に直せ」 OOS 前推奨 (5/29 夜まで、 余力あれば)

### 🟡-A config.json の Kelly fraction / per_bet_cap が freebudget で読まれていない

`config.json:9-10`:
```json
"kelly_fraction": 0.25,
"use_current_balance": true,
```

freebudget.py:
```python
DEFAULT_KELLY_FRACTION = 0.25     # 1/4 Kelly (bankroll/config.json と整合)
DEFAULT_PER_BET_CAP_PCT = 0.10
```

= **値はハードコードで整合しているが、 config.json が真の SoT になっていない**。 将来 config.json で kelly_fraction=0.20 に変えても freebudget は気付かない。

**修正案**: freebudget.py の `process_date` 冒頭で config.json を読み、 CLI 引数で上書き可能にする。

```python
def _read_config_defaults() -> dict:
    cfg_path = Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")) \
        / "userdata" / "bankroll" / "config.json"
    if not cfg_path.exists():
        return {}
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("settings", {})
```

優先度: kelly_fraction = CLI > config.json > DEFAULT_KELLY_FRACTION。

**所要**: 15 分。

### 🟡-B description タイムスタンプ追加

description 内に `generated_at` がペイロード trunk に既にあるので、 git diff 時の整合性確認は OK。 ただし grep 時に description 単独で識別したいなら追加検討。

### 🟡-C `extract_freebudget_bets` の `warnings` 充実

- Kelly raw が cap で叩かれた件数 → `cap_hit_count` を warnings に
- 100円未満で除外された件数 → `below_min_count` を warnings に

これは OOS 後の運用観察情報なので OOS 前は不要だが、 5/30-31 で「Kelly が cap に何回叩かれたか」 を観察できれば 6/6 で cap 値見直しの判断材料になる。

### 🟡-D Composite VB Score 境界値テスト

`test_strategy_freebudget.py` に「Score=5.49 (不通過) / Score=5.51 (通過)」 のケース追加。 ただし Score は bet_engine 内部の合成値なので、 外部からの精密制御が難しい。 OOS 後の TODO。

### 🟡-E truncation テストの境界アサーション

`test_truncation_keeps_high_ev_first` の `if result.bets and result.n_truncated > 0` を **必ず truncation が起きる setup に固定**してアサーションを必須化。

```python
def test_truncation_keeps_high_ev_first(self):
    # bankroll=3000 で per_bet_cap_pct=0.5 → 1馬最大 1500 円
    # 6 馬全部高 EV で 1500 円ずつ採用候補 → 合計 9000 円 → 6 馬全部は入らない
    races = [...6 races...]
    result = extract_freebudget_bets({"races": races}, bankroll=3000,
                                      per_bet_cap_pct=0.5)
    assert result.n_truncated >= 1  # 必須化
    assert all(b.win_ev >= 1.5 for b in result.bets)  # 低 EV は落ちている
```

### 🟡-F 14_LEDGER_SCHEMA に portfolio_id 採番衝突可能性の文書化

freebudget 経路と selective 経路を同日に両方走らせると portfolio_id 採番 (A/B/C…) が衝突しないか? Session 129 実装の `pf-20260530-A08-A` 形式は race_id + seq なので、 異なる race_id なら衝突しない。 同一 race_id に両 source が共存するケースは現状なし (freebudget は selective_bets.json と別ファイル `freebudget_bets.json` を読む)。

ただし、 シズネは「**同日に両経路を走らせない**」 を 14_LEDGER_SCHEMA で明示推奨することを提案。

---

## 4. 評価軸 (依頼の 6 観点) への詳細回答

### 4.1 「儲かった経路を守る」 schema 検証 (Session 129 🔴 J 路線) が freebudget にも適用されているか

🟢 **適用済**。 `selective_loader.py:37` ALLOWED_SOURCES に `freebudget_kelly_1q` 追加 + `_validate_bet` で amount 必須・範囲・100円単位検証は完備。 さらに **「他 source で amount があると abort」** (`selective_loader.py:144-149`) も実装 = 誤混入経路を構造的に塞いでいる。 これは Session 129 J 路線を超えて**より厳格化**している (賞賛)。

🟡 ただし**経路独立性**: freebudget_bets.json と selective_bets.json は別ファイル独立保存。 「同日両方走る」 ケースの ledger 衝突可能性が文書化されていない (🟡-F)。

### 4.2 「動的調整なし」 原則との整合性

🟢 **当日中固定の構造化は完璧**。 freebudget.py CLI で `--bankroll` を**手動入力**にしている = 自動取得しない設計が「動的調整なし」 原則の構造化実装。 `config.json:20` `"no_dynamic_adjustment": true` の文書宣言とコード実装が一致。

🔴 ただし**日跨ぎ更新の基準が定義されていない** (🔴-3 参照)。 「5/31 朝の表示残高」 を使うと払戻反映タイムラグで実質的に動的調整になる罠。

### 4.3 「儲かったから GO」 経路の構造遮断 (§7.3) と Kelly 案分の混線

🟢 **Kelly 案分は「ROI 上振れ目的」 ではない**。 1/4 Kelly + cap 10% は**勝率分散を抑える方向 (= 破産確率最小化)** の使い方で、 これは Themis 原則の「bankroll 残高を入力に持つ」 用途と一致。 「儲かる馬を多く買う」 ではなく「破産しない金額を案分する」。

🟢 さらに freebudget.py L194 `candidates.sort(key=lambda x: x[1], reverse=True)` で truncate 時に**高 EV 優先**で残す = ROI 最大化方向だが、 これは「予算超過時の保守判断」 であって動的調整ではない (bankroll はその場で変わっていない)。

🟢 「儲かったから GO」 経路は 19_OOS_RUNBOOK §7.3 で「ROI は OOS 評価軸ではない」 と明記済 = 構造遮断の文書宣言は維持。

🔴 ただし**ふくだ自身**の本能反応 (§6.4.b)。 freebudget の 5/30 dry-run で 5 件 1600 円が表示された時、 ふくだが「思ったより少ない、 もっと買いたい」 と感じる衝動 を、 freebudget は構造的には**塞いでいない** (`--per-bet-cap-pct 0.20` を打てば cap が 2 倍になる)。

→ これは §6.4.b 行動アンチパターン (Session 133 で追加済) で構造化されている範囲。 freebudget 側で追加対策は不要、 ただし**19_OOS_RUNBOOK §1.5 のチェックリストに「freebudget パラメータを変更しない」 を 1 行追加**することを推奨。

### 4.4 §6.4.b 行動アンチパターン「OOS 1日 (N≤2) で運用パラメータを上げる」 への耐性

🟢 freebudget の Kelly cap 10% は固定 = **「気が大きくなる」 衝動を構造的に緩衝**する設計。 5/30 で運悪く 5 件全部当たって +20000 円になっても、 5/31 朝に `--bankroll 30000` と打ち込むのは「ふくだの能動的アクション」 が必要 (自動取得しない設計が効く)。

🟡 ただし**5/31 朝の `--bankroll` 値を「12300円」 のような払戻反映後の値で打つ衝動** (🔴-3 参照) は構造的に塞がれていない。

🔴 §6.4.b には「**OOS 中に freebudget パラメータを変える**」 が明示的になく、 `--per-bet-cap-pct 0.20` や `--kelly-fraction 0.5` を OOS 中に打つことへの構造的歯止めが弱い (🟡-A の問題と関連)。

**推奨追記** (19_OOS_RUNBOOK §6.4.b に 1 行追加):
```markdown
- ❌ **OOS 中に freebudget 引数 (`--bankroll` / `--per-bet-cap-pct` /
     `--kelly-fraction` / `--preset`) を計画外に変更**
  → 5/30 用は §1.5 で生成した freebudget_bets.json を SoT として固定。
  パラメータ変更したい衝動が出たら即 shizune 呼ぶ。
```

### 4.5 OOS 前必須の指摘

上記 🔴-1 〜 🔴-4 を全部潰せば「無条件 GO」。 所要時間: 合計 30-45 分。 ふくだの判断必要事項:
- 🔴-1: A/B/C のどれ選ぶか (シズネ推奨は C)
- 🔴-2: build_daily_plan_text 修正 (修正コード)
- 🔴-3: 19_OOS_RUNBOOK §1.5 改訂 (修正ドキュメント)
- 🔴-4: bet_engine.generate_recommendations の budget 引数役割確認 (調査 + 必要なら修正コード)

### 4.6 5/30 朝 / 5/31 朝の SOP 抜け

🟢 **5/30 朝** は §1.5 freebudget 生成 + §1.6 bankroll 確認 + §1.7 self-check で十分構造化されている。

🔴 **5/31 朝** は §1.5 の「5/30 終了残高を `--bankroll` に渡す」 部分が**払戻タイムラグの罠**を踏む可能性 (🔴-3)。

🟡 さらに微妙な隙間:
- 5/30 OOS 終了後、 ふくだが PC スリープ → 5/31 朝 PC 復帰時に IPAT セッション状態が不明 (§6.5 で記載済だが Session 134 整備予定のまま)
- 5/31 朝に「freebudget_bets.json を新規生成」 する手順と「修正B 起動時 SESSION_EXPIRED チェック」 がどちらが先か明示なし
  - 推奨順序: ① freebudget 生成 → ② Dry-run でファイル目視 → ③ `--auto-launch` で開始 (= 修正B が走る)

**推奨追記** (19_OOS_RUNBOOK §4.2 5/31 AM 手順の冒頭):
```markdown
**実行順序 (5/31 朝)**:
1. PC 復帰確認 (スリープからの復帰直後は §6.3 PC スリープ復帰行を参照)
2. `freebudget_bets.json` 生成 (§1.5 の 5/31 朝の手順参照、 `--bankroll` 値は §1.5 注意事項通り)
3. 生成内容を目視確認 (各 race_id ごとの amount 合計 <= 3000円、 total_yen <= 10000円)
4. §1.7 当日精神状態 self-check
5. `--auto-launch --confirm` 実行 (= 修正B 起動時チェック発火)
```

---

## 5. シズネ独自観点 (依頼外だが重要)

### 5.1 「不均等案分の音声承認解像度」

🔴-2 で指摘した「金額読み上げ」 は単なる文面修正ではなく**心理的な内容承認解像度**の問題。

selective_bets.json + `--amount 100` 時代は「全件同額」 だったので、 ふくだは「件数 × 100円」 で即座に総額を理解できた。 freebudget は不均等案分なので「**個別金額が分からないと内容承認できない**」 状態。

ふくだの賭け哲学「自分にできない買い方を見つける」 ([[feedback_betting_philosophy]]) は、 Kelly のような数理的案分を「自分にできない買い方」 として採用する正しい思想。 **だがその恩恵を受けるには「数理的案分の中身をふくだが理解した上で承認する」 必要がある**。 音声で金額を読み上げないと、 ふくだは「ML が決めたから OK」 で承認 = **半自動の罠** ([[shizune-agent]] 警戒対象) に半歩入る。

### 5.2 「Kelly 採用」 と「動的調整なし」 の哲学的整合

Kelly は本来「**勝率と賠率の関数として bankroll の何 % を賭けるか動的に決める**」 公式。 freebudget はこれを **1/4 縮小 + cap 固定** で抑え込んで「動的調整なし」 と両立させているが、 厳密には**当日中の bankroll は固定だが、 1馬ごとの amount は動的 (Kelly p × odds で変動)**。

これは矛盾ではなく**用語の使い分け**:
- 「動的調整なし」 = **bankroll 自体を当日中に変えない**
- 「Kelly 案分」 = **bankroll を入力とした関数で 1馬の amount を決める**

両立は理論的に可能だが、 ふくだが将来「Kelly 1/2 にしようかな」 と思い始める瞬間が来る (= 1馬上限が 1000 → 2000円)。 これは**「動的調整なし」 ではないが「パラメータ調整」 = 別カテゴリ**。

**推奨**: 14_LEDGER_SCHEMA or 18_TARGET_FULL_AUTOMATION に「**動的調整なし vs パラメータ調整の境界**」 を明文化:
- ✅ パラメータ調整 = 開催日と開催日の間 (週次以上の間隔) のみ可能
- ❌ 開催日中 (= OOS 期間中) のパラメータ調整 = 禁止
- ❌ OOS 結果を見て翌週パラメータを上げる = sample N=1 で意思決定 (§6.4.b 違反)

これは Session 135+ で 14_LEDGER_SCHEMA 改訂時のメモ。

### 5.3 「フリー予算」 という呼称の心理リスク

「**1万円フリー予算**」 という呼称自体に**「フリー = 自由」 のニュアンス**が混入している。 これは「自由に使える 1 万円」 と受け取られると、 ふくだの本能が「フリーなんだから多めに買ってもいいか」 と反応する可能性。

**推奨**: 用語を「**1万円当日上限**」 / 「**1万円固定予算**」 / 「**1万円キャップ予算**」 に変更検討 (本書では「フリー予算」 を継続使用するが、 内部用語として 14 / 18 では「**固定予算 (fixed daily budget)**」 を採用することを推奨)。

これは OOS 後の文書整理項目。

### 5.4 「freebudget は 4-D Phase 4-D の先取り」 という見方

20_CURRENT_CAPABILITIES.md §1 で「Phase 4-D = TARGET セッション継続管理」 (未起草) とあるが、 freebudget の「日跨ぎ更新の構造化」 は **Phase 4-D の半歩先取り**になっている。

将来の Phase 4-D 設計で「IPAT 残高自動取得 → 日跨ぎ更新」 を考えるなら、 freebudget の `--bankroll` 引数を「**IPAT 残高取得結果を渡す**」 経路に拡張するのが筋。 ただしこれは**今やらない**:
- IPAT 残高取得 = スクレイピング = 規約リスク
- 自動取得 = 「動的調整なし」 原則の構造的後退
- 5/30 終了時点の payout 反映を「IPAT 残高表示」 で代用するのは🔴-3 で禁じた通り

→ Phase 4-D は当面**スコープアウト**を推奨。 Session 135+ で「**月次レビューで bankroll を手動更新**」 という運用 SOP を策定する方が筋。

---

## 6. ふくだ君に確認したい論点 (4 件)

1. **🔴-1 の選択肢**: A (config.json 一時変更) / B (freebudget で自動算出) / C (チェックリスト追加で目視) のどれを採用するか。 シズネ推奨は **C** (config を本番中に弄らない原則を維持)。

2. **🔴-4 の調査結果**: `bet_engine.generate_recommendations` の `budget` 引数が「金額 sizing」 / 「件数フィルタ」 / 「両方」 のどれか。 ふくだ or カカシが 5 分以内に確認可能か。 件数フィルタなら**Themis 原則整合のため修正必要**。

3. **5.3 用語変更**: 「**1万円フリー予算**」 → 「**1万円固定予算**」 等への変更を OOS 終了後にやる価値があるか。 今やらない方が良いか (= OOS 中の文書差し替えコスト > 心理リスク低減効果)。

4. **§6.4.b 追記**: 「OOS 中に freebudget 引数を計画外に変更しない」 の 1 行追加は今 OOS 前に入れるべきか、 OOS 後でも間に合うか。 シズネは**OOS 前必須**を推奨 (5/30 9:30 頃の「気が大きくなる」 衝動を構造的に塞ぐ最後の歯止め)。

---

## 7. 最終判定

**条件付き GO**。

- 🔴-1 〜 🔴-4 を 5/29 夜までに全部潰せば → **無条件 GO**
- 🔴 残ったまま OOS 突入 → **NO-GO**、 5/30 半自動運用 (selective_bets.json + `--amount 100` フォールバック経路) に降格

過去 3 回 (131/132/133) と同じ「条件付き GO → 全潰し → 無条件 GO」 リズム再現を期待。

**Session 134 内で潰す優先順位** (シズネ推奨):
1. **🔴-1**: 19_OOS_RUNBOOK §1.5 チェックリスト追加 (5 分、 ドキュメントのみ)
2. **🔴-2**: notify.py build_daily_plan_text + runner.py bets_summary (15 分、 コード修正 + テスト)
3. **🔴-3**: 19_OOS_RUNBOOK §1.5 5/31 朝の手順改訂 (10 分、 ドキュメントのみ)
4. **🔴-4**: bet_engine.generate_recommendations の budget 引数役割確認 (5 分調査 + 必要なら 5 分修正)
5. **§6.4.b 追記**: freebudget 引数を変更しないアンチパターン追加 (3 分、 ドキュメントのみ)

合計 30-45 分で全潰し可能。 過去 2-3 回と同じスケジュール感。

---

> 「シズネが入る根本理由 = ブレーキ役。 freebudget は Kelly 採用で『自分にできない買い方』 を構造化した良い設計だが、 数理的案分の中身を音声で承認できない問題と、 5/31 朝の払戻タイムラグ罠と、 1万円という呼称の心理リスクが残る。 全部潰せる範囲。 過去 3 回と同じく月曜の振り返りに『無条件 GO』 で入れる。」
> — シズネ (Session 134)

---

## Session 134 追記: 🔴 全潰し確認 → 無条件 GO

> **判定: 無条件 GO**。 🔴-1 〜 🔴-4 + §6.4.b、 全件をコード/ドキュメント/テストの実体で確認。 過去 3 回 (131/132/133) と同じ「条件付き GO → 全潰し → 無条件 GO」 リズム再現を確認した。

### 検証した実体 (file:line 引用)

| 件 | 確認内容 | 実体 | 判定 |
|----|---------|------|------|
| 🔴-1 | config 衝突 → 目視チェックリスト (推奨 C 採用) | `19_OOS_RUNBOOK.md:147-172` (各 race_id ≤3000 / total ≤10000 の Python ワンライナー + 「config を本番中に弄らない」 明記 + NG時は freebudget 再生成/半自動降格) | OK |
| 🔴-2 | 金額読み上げ (二重認証ゲート骨抜き解消) | `notify.py:267` (`isinstance(amount, int) and amount > 0` ガード → 「N 番 X円」、 else 従来通り) + `runner.py:518` (`row["amount"] = b.amount`) + `test_notify_daily_plan_amount.py` 7件 (型防御/0防御/None フォールバック/truncation 込み) | OK |
| 🔴-3 | 5/31 朝の払戻タイムラグ罠 | `19_OOS_RUNBOOK.md:176-195` (「5/31 朝の表示残高は使わない」 明記 + 5/30 23:59 スクショ基準 + 10000円固定フォールバック + 「23:59〜翌朝の払戻は含めない=動的調整になる」 を構造的に明文化) | OK |
| 🔴-4 | Themis 原則整合 (budget=件数フィルタ疑い) | 調査確定: `bet_engine.py:1517-1528` `apply_budget` Step2 は `total > budget` 時のみ按分縮小、 かつ `win_amount`/`place_amount` とも `max(params.min_bet, ...)` で下限保証 = **按分縮小しても件数不変 = 件数フィルタではない**。 `win_amount` セット箇所 (1142/1218/1233/1272/1329/1345/1402/1422) は全て `params.bet_unit`/Kelly units 由来で budget 非依存。 → `freebudget.py:161` で `budget=10**9` に変更し按分縮小経路を完全無効化、 docstring (156-160) に Themis 原則明記 | OK |
| §6.4.b | freebudget 引数の計画外変更を行動アンチパターン化 | `19_OOS_RUNBOOK.md:597-599` (`--bankroll`/`--per-bet-cap-pct`/`--kelly-fraction`/`--preset` 変更 = 「気が大きくなる」 衝動の隠れ経路。 「5/30 が 1600円しか使ってないから 5/31 は 0.20 で攻めよう」 = sample N=1 反応の典型として明示) | OK |
| §4.2 | 5/31 朝の実行順序明記 | `19_OOS_RUNBOOK.md:375-381` (① PC復帰確認 → ② freebudget生成 → ③ 目視確認 → ④ self-check → ⑤ `--auto-launch`) | OK |

### テスト確認

- `test_notify_daily_plan_amount.py` 7件 + `test_launcher_no_password.py` 14件 + `test_launcher_recovery.py` 23件 = **44 passed / 0.77秒** (シズネ手元再実行)
- 既存 64件 regression なしの報告とも整合
- 修正後 dry-run が修正前と完全一致 (5件/1600円) = 🔴-4 が元々件数に影響していなかった傍証として妥当

### 🔴-4 についての所見 (Themis 原則の番人として)

調査が正しいことを実コードで裏付けた。重要なのは「修正前後が完全一致したから直さなくてよい」 ではなく、 **`budget=10**9` にして按分縮小経路を恒久的に無効化した** 点。 これにより将来 `bankroll` が小さい値で渡されても (例: 5/31 残高が 3000円等)、 freebudget の件数が bankroll に左右されない構造が保証される。 = bankroll は「各馬の金額」 の入力であって「買う/買わないの件数判定」 の入力ではない、 という Themis 原則がコードレベルで担保された。 これは「今回の OOS で一致した」 を超えた恒久的な正しさ。

### 据え置き 🟡 (OOS 後対応に同意)

🟡-A 〜 🟡-F (config.json から kelly_fraction 読込 / description timestamp / warnings 充実 / Composite Score 境界テスト / truncation テスト境界アサーション必須化 / 14_LEDGER_SCHEMA に portfolio_id 衝突文書化) は全て OOS 前必須ではない。 据え置きで合意。

### ふくだ判断待ち 2 件 (OOS 前必須ではない)

1. **5.3 用語変更** (フリー予算 → 固定予算): OOS 中の文書差し替えコスト > 心理リスク低減効果。 **OOS 後で良い**。 ただし §6.4.b で「1万円という呼称が『減ってもまた来週来る』 と錯覚させうる」 リスクは行動アンチパターン側でカバー済なので、 急がない。
2. **§6.4.b 追記タイミング**: OOS 前必須推奨だったので **Session 134 で反映済** (`19:597-599`)。 判断は事後追認で OK。

### 最終判定

**無条件 GO**。 5/30-31 OOS 突入可。 19 §0.2 段階的アプローチ (1レース → 観察 → 継続) に従って実施されたし。

> 「全部潰れてます。 ふくだ君、 これで突入していいです。 ただし OOS 当日は §1.7 self-check を声に出すこと、 §6.4.b の 5 衝動 + freebudget 引数変更を『触りたくなったら shizune 呼ぶ』 を守ること。 数理で組んだ案分を当日いじったら、 それは Kelly じゃなくてただの気分です。 月曜の振り返りに『無条件 GO で検証完了』 で入れましょう。」
> — シズネ (Session 134 追記 / 全潰し確認)
