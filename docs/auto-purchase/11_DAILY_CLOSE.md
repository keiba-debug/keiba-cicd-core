# 11. 日次クローズ — ledger × TARGET履歴 × IPAT 三層突合

> **作成日**: 2026-05-23（追加2項目 β1）
> **改訂履歴**:
> - **2026-05-23 v1.1** [12 章 v2.0 「毎日オプトイン」モデル転換](./12_KILL_SWITCH_COOLDOWN.md) の波及で §5.4（**翌朝オプトイン UI 向けの前日サマリ生成**）を新設。日次クローズが生成する `daily_close/{date}.json` は翌朝のオプトイン UI の主要入力になる。
> - **2026-05-23 v1.2** [12 章 v2.1](./12_KILL_SWITCH_COOLDOWN.md) でオプトイン UI に「直近 7 日 ROI 推移スパークライン」が追加された波及で、§5.4 に **`daily_close/{date}.json` を直近 7 日分集計する API/関数の必要性** を追記（§5.4.2 新設）。
> **担当**: シズネ（リスク管理 / 監査 / 税務担当）
> **位置づけ**: 1日の購入を確定させる「日次クローズ」の仕様。`ledger`（自動）／TARGET 履歴（参考）／IPAT 実投票履歴（真の SoT）の3層を突合し、差分レポートを残す。
> **関連**: [./05_RISK_COMPLIANCE.md](./05_RISK_COMPLIANCE.md) §5、[./07_DATA_SCHEMA_AND_EVENTS.md](./07_DATA_SCHEMA_AND_EVENTS.md)、[./09_MY_MARKS_AND_STRATEGY.md](./09_MY_MARKS_AND_STRATEGY.md) §3（F戦法）、[./10_BANKROLL_CONTROL.md](./10_BANKROLL_CONTROL.md) §6、[./12_KILL_SWITCH_COOLDOWN.md](./12_KILL_SWITCH_COOLDOWN.md) §4（翌朝オプトイン UI）、[./13_AUTO_RECONCILIATION.md](./13_AUTO_RECONCILIATION.md) §6.2（OptinContext）

---

ふくだ君。TARGET の購入履歴スクショ、ありがとうございました。あれは想像以上に重要な情報源です。**「F戦法を既に手動でやっている」記録**そのものなので、ledger 設計のリファレンス実装として丁寧に取り込みます。

ただし、シズネが几帳面に1点だけ釘を刺します。**TARGET の「送成功」は「投票成功」ではありません**。TARGET FAQ にも明記されているとおり、TARGET → IPAT への送信が成功しただけで、IPAT 側で実際に投票が受理されたかは別の話です。だから真の SoT（Source of Truth）は **IPAT 実投票履歴 CSV** であって、TARGET 履歴ではない。ここを混同するとお金が消える経路ができます。

---

## 1. 目的とスコープ

| 項目 | 内容 |
|---|---|
| **目的** | 1日の購入を「計画」「送信」「実投票」の3層で確定させ、不一致を翌朝までに検知する |
| **タイミング** | 粒度B（日次クローズ + 報告作成）。原則 **当日 19:00 頃**、運用が難しい日は翌朝 09:00 までに実施 |
| **トリガ** | 手動（ふくだ君がボタンを押す）+ 自動リマインダ（19:00 通知） |
| **成果物** | `data3/reports/{YYYY-MM-DD}.md` 差分レポート / `data3/userdata/daily_close/{YYYY-MM-DD}.json` 構造化記録 |
| **スコープ外** | リアルタイム突合（締切時の整合性は ledger 側で担保、本書では扱わない） |

---

## 2. なぜ「粒度B（日次クローズ）」か

朝会の議論で出た選択肢を整理して残します。

| 粒度 | 内容 | 採否 |
|---|---|---|
| A: レース単位 | 各レース投票直後に IPAT 突合 | ❌ IPAT 即時取得が技術的に難しい、運用負荷も高い |
| **B: 日次クローズ** | **1日の終わりに3層を一括突合・報告生成** | ✅ **採用** |
| C: 週次／月次 | 週末まとめて突合 | ❌ 差分発見が遅れ、税務記録としても粒度が荒い |

B を選んだ理由:

- **発見遅延の上限が1日**: 翌朝に必ず気付ける
- **IPAT CSV のDLは1日1回でよい**: ふくだ君の運用負荷が現実的
- **税務記録の自然な粒度**: 雑所得申告は日次集計を年次に積み上げる
- **F戦法との相性**: 1レースで複数券種を打つので、レース単位より日次集計のほうが配分検証しやすい

---

## 3. 三層突合システムの全体像

```
[層1] KeibaCICD ledger         purchase_ledger/{date}.json
  ├ 送信した買い目（自動・即時）
  └ 計画と送信意図のSoT
        │
        ├── (突合A) ─── [層2] TARGET 履歴
        │                ├ 「送成功」記録（参考）
        │                └ TARGET → IPAT 送信ログ
        │
        └── (突合B) ─── [層3] IPAT 実投票履歴 CSV  ← 真のSoT（税務・最終突合）
                          ├ JRA側で受理された投票
                          └ 払戻も含む
```

### 3.1 各層の役割と信頼度

| 層 | データ源 | 信頼度 | 用途 |
|---|---|---|---|
| **[1] ledger** | KeibaCICD 内部 | 高（自前で書く） | 計画と意図の証跡、税務の判断根拠 |
| **[2] TARGET 履歴** | TARGET アプリの履歴画面 | 中（送信成功 ≠ 投票成功） | 参考。ledger と IPAT の中間検証 |
| **[3] IPAT 履歴** | IPAT サイトから手動 DL する CSV | **最高**（JRA公式） | **最終突合・税務記録の主データ** |

### 3.2 突合の方向性

- **突合A（[1] vs [2]）**: 送信したつもりの買い目が TARGET にも残っているか
  - 不一致パターン: ledger に書かれているが TARGET 履歴にない → FF CSV 取込漏れ疑い
- **突合B（[1] vs [3]）**: 送信した買い目が実際に JRA で投票されたか
  - 不一致パターン: ledger にあるが IPAT 履歴にない → **赤フラグ**。投票漏れ・回線断・人手送信ミスのいずれか

> シズネのこだわり: **突合B が最重要**です。突合A は参考。TARGET の「送成功」は信用してはいけません。

---

## 4. TARGET 履歴データ構造の取り込み

### 4.1 ふくだ君のスクショから抽出した実データ構造

```
23日12:28:47  1 送成功◎ 京 5R [A]  買目全 1000円 馬連 08-13
23日12:28:47  2 送成功◎ 京 5R [A]  買目全 3000円 ワイド 08-13
23日12:28:47  3 送成功◎ 京 5R [A]  買目全 3000円 単勝 13
（中略）
23日13:17:58  1 送成功◎ 東 7R [A]  買目マ @300円 3連単 フォ [6点] (17)-(11)-(2,3,9,12,13,16)
---- 計 61 件 / 56900 円 ----
```

### 4.2 フィールド分解と ledger スキーマ対応

| TARGET 表記 | 意味 | ledger スキーマ対応フィールド |
|---|---|---|
| `23日12:28:47` | 送信時刻（日 + HH:MM:SS） | `events[].at`（ISO8601 補完） |
| `1` `2` `3` ... | 送信内の連番 | `target_seq`（新規） |
| `送成功◎` | 送信ステータス | `target_send_status: "success"` |
| `京 5R` | 開催・レース | `race_id` 復元用キー |
| `[A]` | TARGET 内の口座／プロファイル識別 | `target_account: "A"` |
| `買目全` `買目マ` | 買い目の指定方式（全＝指定全買い／マ＝マーク経由） | `bet_source: "all" / "mark"` |
| `1000円` `@300円` | 金額（@は単価、フォーメーション時の1点金額） | `amount_per_combo` / `total_amount` |
| `馬連` `ワイド` `単勝` `3連単` | 券種 | `bet_type`（既存スキーマ準拠） |
| `08-13` | 馬番組み合わせ | `selection: [8,13]` |
| `フォ [6点] (17)-(11)-(2,3,9,12,13,16)` | フォーメーション表記 | §4.3 参照 |
| `---- 計 61 件 / 56900 円 ----` | 日次フッタ | `daily_summary` |

### 4.3 フォーメーション表記の扱い

`フォ [6点] (17)-(11)-(2,3,9,12,13,16)` を構造化:

```json
{
  "bet_type": "sanrentan",
  "selection_mode": "formation",
  "axis_1st": [17],
  "axis_2nd": [11],
  "axis_3rd": [2, 3, 9, 12, 13, 16],
  "combo_count": 6,
  "amount_per_combo": 300,
  "total_amount": 1800
}
```

ポイント:
- **`combo_count` を必ず保持**: フォーメーションは1点単価 × 点数で総額が決まるので、点数を落とすと金額検算ができなくなる
- **`selection_mode` で BOX / フォーメーション / 流し を区別**: ledger 側でも同様のモードを持つ
- **axis_1st/2nd/3rd の配列構造を統一**: 三連単・三連複・馬単・馬連すべてこの形式で表現可能

### 4.4 F戦法 1レース内複数券種ポートフォリオの記録例

ふくだ君が 23日12:28:47 に京5Rで打ったポートフォリオ（スクショ抜粋）を ledger 形式で表現:

```json
{
  "race_id": "2026052308050500",
  "venue": "京都",
  "race_number": 5,
  "portfolio_id": "20260523-京5R-A",
  "portfolio_strategy": "F_partial_step2",
  "bets": [
    {
      "bet_seq": 1,
      "bet_type": "umaren",
      "selection_mode": "single",
      "selection": [8, 13],
      "total_amount": 1000,
      "target_seq": 1,
      "target_account": "A"
    },
    {
      "bet_seq": 2,
      "bet_type": "wide",
      "selection_mode": "single",
      "selection": [8, 13],
      "total_amount": 3000,
      "target_seq": 2,
      "target_account": "A"
    },
    {
      "bet_seq": 3,
      "bet_type": "tansho",
      "selection_mode": "single",
      "selection": [13],
      "total_amount": 3000,
      "target_seq": 3,
      "target_account": "A"
    }
  ],
  "portfolio_total": 7000
}
```

> シズネ注: `portfolio_id` と `portfolio_strategy` を新設すると、後で F戦法の効果検証（券種別ROI比較・カバー率検証）が一気にやりやすくなります。Step 4 で F が完成した時に必要になる粒度なので、Step 1 の段階から器だけ用意しておくのが几帳面な実装です。

---

## 5. IPAT 実投票履歴 CSV のインポート手順

### 5.1 ふくだ君の運用フロー

```
1. レース日 19:00 頃（or 翌朝）、IPAT サイトにログイン
2. 「投票履歴」→ 当日分を CSV ダウンロード
3. KeibaCICD Web の `/auto-purchase/daily-close` 画面を開く
4. CSV ファイルをドラッグ&ドロップ
5. 自動突合 → 差分レポートが画面に表示
6. ふくだ君が確認 → 「クローズ確定」ボタン
7. `data3/reports/{date}.md` が生成され、ledger が closed 状態に
```

### 5.2 CSV のパース仕様（仮）

IPAT の CSV フォーマットは公式に公開されていない箇所もあるので、**実物を見てから確定する** ことが前提。本書では暫定仕様として:

| 想定列 | 用途 |
|---|---|
| 投票日時 | 突合のタイムスタンプ |
| 開催・レース | race_id 復元 |
| 券種 | bet_type マッピング |
| 買い目 | selection マッピング |
| 金額 | total_amount 検算 |
| 払戻金 | settle_purchases との突合 |

> 実装着手時タスク: ふくだ君に「次回 IPAT CSV を1日分だけサンプル提供してもらう」 → カカシ先生に列定義の確定とパーサ実装を依頼。

### 5.3 アップロード API

```
POST /api/auto-purchase/daily-close/import-ipat
Content-Type: multipart/form-data
- file: <CSV>
- date: 2026-05-23

Response:
{
  "ok": true,
  "ipat_rows_imported": 61,
  "matched": 58,
  "ledger_only": 2,
  "ipat_only": 1,
  "amount_mismatch": 0,
  "report_path": "data3/reports/2026-05-23.md"
}
```

### 5.4 翌朝オプトイン UI 向けの前日サマリ生成（v1.1 新設）

[12 章 §4 翌朝オプトイン UI](./12_KILL_SWITCH_COOLDOWN.md#4-翌日オプトイン-ui) は「前日サマリ」と「直近 3 開催日の不一致履歴」を表示する。これらは本書のクローズ確定時に生成され、翌朝の `/api/auto-purchase/optin-context` 経由で UI に供給される。

| フィールド | 出典 | 生成タイミング |
|---|---|---|
| `prev_day.bets` `invest` `payout` `pnl` | `daily_close/{date}.json` の集計 | クローズ確定時 |
| `prev_day.max_severity` `high_count` `medium_count` | 13 章 §4 `reconciliation/{date}.json` の `summary.severity_max` 他 | 突合実行時 |
| `prev_day.stopped_at_eod` | `purchase_ledger/{date}.json` の `events[]` に `KILL_SWITCH_TRIGGERED` があるか | クローズ確定時に走査 |
| `recent_race_days[]` | 直近 3 開催日の `reconciliation/{date}.json` を読んで `max_severity` を抽出 | 翌朝オプトイン UI 表示時に on-demand |
| `unacked_medium_count` | 各日の `reconciliation/{date}.json` の `discrepancies[].acked` フラグ | 同上 |

**重要**: 翌朝オプトイン UI が出る前日の **クローズが未済** だと、サマリが空になります。これは [§10-3](#10-シズネからの注意点) の「クローズ未実施日の翌朝ブロック」と整合し、「**前日クローズ未済 → 翌朝オプトイン UI で「前日サマリが取得できません。先に日次クローズを完了してください」と表示し、開始ボタンを非活性化**」する設計とする。

> シズネ注（v1.1 追記）: これにより日次クローズが「翌朝のオプトイン判断の前提」として組み込まれ、クローズを忘れると翌日が始まらない構造になります。クローズの忘却が物理的に防げる。Themis 原則の周辺事実をふくだ君に提示する前提として日次クローズが必須なので、この依存関係は健全です。

### 5.4.2 直近 7 日 ROI 集計（v1.2 新設 — 12 章 §4.2.4 オプトイン UI スパークライン用）

[12 章 §4.2.4](./12_KILL_SWITCH_COOLDOWN.md#424-ブロック--直近7日-roi-推移スパークライン仕様) のオプトイン UI スパークラインに供給する集計。

| 項目 | 仕様 |
|---|---|
| **集計対象** | `data3/userdata/daily_close/{date}.json` を**当日含む直近 7 日**読み込み（カレンダー日基準。非開催日もスキップせず「invest=0/payout=0/closed=true」のレコードを返す）|
| **欠損扱い** | `daily_close` ファイルが無い日 → `{ invest: 0, payout: 0, roi_pct: null, closed: false }` で返す。UI 側でスパークラインを途切れさせ、灰色 "?" マーカー表示の判断材料にする |
| **集計関数** | `keiba-v2/ml/daily_close/aggregate.py` に `aggregate_recent_roi(end_date: str, days: int = 7) -> RecentRoiResult` を新設（純関数。I/O は呼び出し側）|
| **集計 API** | `/api/auto-purchase/optin-context` の拡張フィールドとして提供（既存の `prev_day` / `recent_race_days` / `unacked_medium_count` に並ぶ）|
| **集計フィールド** | `recent_7day_roi[]`（日別） + `recent_7day_roi_aggregate`（投資加重 ROI / 累計収支 / クローズ済日数）— スキーマは [12 章 §4.2.4 OptinContextV21](./12_KILL_SWITCH_COOLDOWN.md#424-ブロック--直近7日-roi-推移スパークライン仕様) と同一 |
| **invest=0 日の扱い** | `roi_pct` は null（ゼロ除算回避）。投資加重 ROI 集計時には分母に含めない |
| **タイムゾーン** | JST 固定。`end_date` は YYYY-MM-DD 文字列で受け、7 日前 = `end_date - 6 days` をカレンダー日で計算 |

**実装スケッチ（擬似コード）**:

```python
# keiba-v2/ml/daily_close/aggregate.py
from datetime import date, timedelta
from pathlib import Path
import json

DAILY_CLOSE_DIR = Path("data3/userdata/daily_close")

def aggregate_recent_roi(end_date: str, days: int = 7) -> dict:
    end = date.fromisoformat(end_date)
    rows = []
    invest_total = 0
    payout_total = 0
    days_closed = 0
    for i in range(days):
        d = end - timedelta(days=days - 1 - i)
        path = DAILY_CLOSE_DIR / f"{d.isoformat()}.json"
        if not path.exists():
            rows.append({"date": d.isoformat(), "invest": 0, "payout": 0,
                         "roi_pct": None, "closed": False})
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        invest = data.get("summary", {}).get("invest_total", 0)
        payout = data.get("summary", {}).get("payout_total", 0)
        roi = (payout / invest * 100) if invest > 0 else None
        rows.append({"date": d.isoformat(), "invest": invest, "payout": payout,
                     "roi_pct": roi, "closed": True})
        invest_total += invest
        payout_total += payout
        days_closed += 1
    agg_roi = (payout_total / invest_total * 100) if invest_total > 0 else None
    return {
        "recent_7day_roi": rows,
        "recent_7day_roi_aggregate": {
            "invest_total": invest_total,
            "payout_total": payout_total,
            "roi_pct": agg_roi,
            "pnl": payout_total - invest_total,
            "days_closed": days_closed,
        },
    }
```

> シズネ注: 集計関数は純関数にして、I/O テスト用に `DAILY_CLOSE_DIR` を引数注入できるようにすること。pytest で `tmp_path` を使った 7 日分の合成データを流して、欠損日と invest=0 日の両ケースを必ずカバー。「過去にクローズを忘れた日が混ざってもクラッシュしない」が要件。

---

## 6. 自動突合ロジック

> **自動突合エンジンの詳細仕様（起動・通知・kill switch 連動・スキーマ）は [13_AUTO_RECONCILIATION.md](./13_AUTO_RECONCILIATION.md) に分離**。本章は日次クローズ手順としての概要に留めます。

### 6.1 マッチングキー

各レコードを `(race_id, bet_type, selection_normalized, amount)` の4タプルで正規化してマッチング。

- `selection_normalized`: 馬番ソート済み配列の JSON 文字列（例: `[8,13]` → `"8,13"`）
- フォーメーションは axis 構造をそのまま比較せず、**展開後の全 combo を比較**

### 6.2 不一致パターンと色分け

| パターン | 状態 | 色 | アクション |
|---|---|---|---|
| 3層すべて一致 | `OK` | 🟢 | 記録のみ |
| ledger ⊂ TARGET ⊂ IPAT（金額不一致なし） | `OK` | 🟢 | 記録のみ |
| TARGET にあるが IPAT にない | `target_only` | 🟡 | TARGET 送信したが投票されてない可能性。要目視 |
| ledger にあるが IPAT にない | `ledger_only` | 🔴 | **赤フラグ**。送信漏れ・キャンセル・人手ミス |
| IPAT にあるが ledger にない | `ipat_only` | 🟠 | **要確認**。ふくだ君が手動で打った馬券（システム外） |
| 4タプル一致だが金額不一致 | `amount_mismatch` | 🔴 | **赤フラグ**。誤入力・改ざん疑い |

### 6.3 差分レポートのフォーマット

`data3/reports/{date}.md` の構造:

```markdown
# 日次クローズ報告 2026-05-23

## サマリ
- 計画(ledger): 61 件 / 56,900円
- 送信(TARGET): 61 件 / 56,900円
- 投票(IPAT):   60 件 / 56,600円  ← 1件不一致
- 払戻:        12,300円
- 収支:        -44,300円

## 不一致
### 🔴 ledger_only (1件)
| race_id | bet_type | selection | amount | 推定原因 |
|---|---|---|---|---|
| 2026052308050801 | wide | [3,9] | 300 | IPAT側に記録なし。締切間際の送信失敗疑い |

### 🟠 ipat_only (0件)
（該当なし）

### 🔴 amount_mismatch (0件)
（該当なし）

## 採用ポートフォリオ別収支
| portfolio_id | strategy | 投資 | 払戻 | 収支 |
|---|---|---|---|---|
| 20260523-京5R-A | F_partial_step2 | 7,000 | 0 | -7,000 |
| ... | ... | ... | ... | ... |

## My印 vs 着順サマリ
| race_id | ◎ | ○ | ▲ | 着順1 | 着順2 | 着順3 | F結果 |
|---|---|---|---|---|---|---|---|
| 京5R | 13 | 8 | - | 13 | 5 | 8 | ◎1着 ○3着 → 単◎・ワイド◎-○・馬連◎-○ 的中 |

## 翌日への申し送り
- [ ] ledger_only の 1件、IPAT 画面で投票履歴を再確認
- [ ] bankroll 残高: ¥XX,XXX（前日比 -¥44,300）
```

> シズネ注: F戦法を本格運用するなら **「ポートフォリオ別収支」「My印 vs 着順サマリ」** の2セクションは必須です。1点1点の馬券を見ても F の効果は分からない。レース単位・ポートフォリオ単位の集計でこそ「死に馬券なしポートフォリオ」の検証ができます。

---

## 7. 既存スキーマとの関係整理

3つの既存スキーマと、本書で新設する layer の対応関係を几帳面に整理します。

```
┌─────────────────────────────────────────────────────────┐
│ purchase_ledger/YYYY-MM-DD.json  (07章スキーマ)          │
│   状態遷移 + イベント + bets_summary                     │
│   → 本書では [層1] として扱う                             │
└─────────────────────────────────────────────────────────┘
              │ 日次クローズ時に参照
              ▼
┌─────────────────────────────────────────────────────────┐
│ daily_close/YYYY-MM-DD.json  (本書で新設)                │
│   3層突合結果 + ポートフォリオ集計 + 不一致リスト          │
└─────────────────────────────────────────────────────────┘
              │ 確定後に同期
              ▼
┌─────────────────────────────────────────────────────────┐
│ purchases/YYYY-MM-DD.json     (既存・税務SoT)            │
│ confirmed_bets/YYYY-MM-DD.json (既存・判断時点snapshot)  │
│   → IPAT 突合済の値で上書き更新                            │
└─────────────────────────────────────────────────────────┘
```

| 既存スキーマ | 本書クローズ後の扱い |
|---|---|
| `purchase_ledger` | 状態 `CLOSED` に遷移。当日のレース行に `daily_close_ref` 追加 |
| `purchases` | IPAT 履歴で確定した値で上書き。`source: "auto_purchase"` + `daily_close_verified: true` フラグ追加 |
| `confirmed_bets` | 変更しない（判断時点の snapshot として保存・改ざん不可） |

> シズネ注: `confirmed_bets` を絶対に書き換えないことが税務記録の生命線です。判断時点のオッズと EV を「あとから書き換える」と監査上完全にアウトです。クローズで上書きしてよいのは「実際の購入金額」「実際の払戻」など **事実ベースのフィールド** のみ。判断根拠系（EV, gap, preset, model_version）は不変です。

---

## 8. 監査・税務観点での記録要件

[05_RISK_COMPLIANCE.md](./05_RISK_COMPLIANCE.md) §5（税務）の脚注として参照されます。

### 8.1 保存要件

| データ | 保存先 | 保持期間 | 改ざん防止 |
|---|---|---|---|
| `daily_close/{date}.json` | `data3/userdata/daily_close/` | **7年**（雑所得申告要件） | 追記のみ・上書き禁止 |
| `reports/{date}.md` | `data3/reports/` | **7年** | クローズ確定後は read-only |
| IPAT CSV 原本 | `data3/userdata/ipat_raw/{date}.csv` | **7年** | ハッシュ値を `daily_close.json` に記録 |
| TARGET 履歴スクショ／エクスポート | `data3/userdata/target_raw/{date}.{ext}` | **7年** | 同上 |

### 8.2 改ざん防止の最小実装

- クローズ確定時に `daily_close.json` の SHA256 を `data3/userdata/daily_close/_index.jsonl` に追記
- 翌日の起動時にハッシュ検証 → 不一致なら警告
- 完全な改ざん防止は Phase 4 で WORM ストレージ or git commit ベース運用に格上げ（review Phase 4）

### 8.3 税務調査対応の説明可能性

ふくだ君、これは万一の話ですが「なぜこの金額を、なぜこのレースに、いくら賭けたのか」を税務調査で説明できる状態にしておきます。

| 質問 | 回答ソース |
|---|---|
| なぜこのレースに賭けたのか | `confirmed_bets` の EV, gap, preset, model_version |
| なぜこの金額か | `bankroll/config.json` + `race_overrides` の reason |
| 実際にいくら買ったか | `purchases` + `daily_close` で IPAT 突合済 |
| 実際の収支は | `daily_close` の収支サマリ + IPAT CSV 原本 |

「説明可能なリスク管理してました」を示すための一式が、この日次クローズで揃います。

---

## 9. UI モック（最低限）

`/auto-purchase/daily-close` 画面の構成（粒度のみ・詳細デザインは 04章で別途）:

```
┌─────────────────────────────────────────┐
│ 日次クローズ 2026-05-23   [クローズ確定]  │
├─────────────────────────────────────────┤
│ [1] ledger        61件 / 56,900円  ✅   │
│ [2] TARGET 履歴   61件 / 56,900円  ✅   │
│ [3] IPAT 履歴     [ファイルをドロップ]   │
├─────────────────────────────────────────┤
│ 突合結果（CSV取込後に表示）             │
│  🟢 一致:           58件                │
│  🔴 ledger_only:    2件  [詳細]         │
│  🟠 ipat_only:      1件  [詳細]         │
│  🔴 amount_mismatch: 0件                │
├─────────────────────────────────────────┤
│ ポートフォリオ別収支                    │
│  [テーブル]                             │
├─────────────────────────────────────────┤
│ 翌日への申し送り                        │
│  [自動生成 + 手動メモ追記可]            │
└─────────────────────────────────────────┘
```

---

## 10. シズネからの注意点

1. **IPAT CSV の DL を自動化したくなる気持ちは分かりますが、Phase 4 まで保留**。スクレイピング相当の操作は TARGET FAQ の自己責任範囲を超えます。ふくだ君が手動で DL するのが安全。
2. **TARGET 履歴は「参考」止め**。`target_only` の不一致を「OK」扱いにする運用に流されると、お金が消える経路が再び開きます。
3. **クローズ未実施日の翌朝ブロック**: クローズが終わってない日が累積すると突合の意味が薄れます。前日クローズが未済なら、当日の自動購入モードを `manual` に強制ダウンするチェックを Step 1 の段階で入れる価値があります。
4. **CSV 原本は絶対に消さない**。一度パースして JSON 化したから不要、ではなく **原本が真の SoT** です。`ipat_raw/` を `.gitignore` に入れた上で7年保存。
5. **F戦法の検証は「ポートフォリオ単位」で見る**。1点ずつの ROI を見ると F の意義（カバレッジによる分散）が見えません。レポートでは必ず portfolio_id でグループ化して評価してください。

---

## 11. 実装時タスク

順序は依存順。

| # | タスク | 担当候補 | 工数感 |
|---|---|---|---|
| 1 | IPAT CSV のサンプル提供（ふくだ君が次回 DL） | ふくだ君 | XS |
| 2 | CSV パーサ実装（`ml/daily_close/ipat_parser.py`） | カカシ先生 | M |
| 3 | TARGET 履歴フォーマット確定（スクショ → エクスポート機能の調査） | シズネ | S |
| 4 | `daily_close/{date}.json` スキーマ実装 | Backend agent | S |
| 5 | 突合エンジン（`ml/daily_close/reconcile.py`） | Python agent | M |
| 6 | `/auto-purchase/daily-close` 画面（ドロップ + プレビュー + 確定） | Frontend agent | M |
| 7 | レポート生成（Markdown 出力 + ポートフォリオ集計） | Backend agent | S |
| 8 | 改ざん防止ハッシュ + 7年保存ポリシー実装 | シズネ + Backend | S |
| 9 | クローズ未実施日の翌朝ブロック実装 | カカシ先生 | S |
| 10 | **直近 7 日 ROI 集計関数 `aggregate_recent_roi()` 実装**（§5.4.2）+ pytest 欠損日/0 投資日カバー | カカシ先生 | S |
| 11 | **`/api/auto-purchase/optin-context` の `recent_7day_roi[]` フィールド追加**（11 章 §5.4.2 + 12 章 §4.2.4 連動） | Backend agent | XS |

---

## 12. 次のアクション

- [ ] **シズネ**: ふくだ君に次回 IPAT 投票履歴 CSV のサンプル提供を依頼し、列定義を確定する（本書 §5.2 の暫定仕様の更新）
- [ ] **カカシ先生**: `daily_close/{date}.json` スキーマと `reconcile.py` の I/F 草案を Step 2 着手前に作成
- [ ] **ふくだ君**: TARGET アプリ側に「履歴エクスポート」機能があるか確認（スクショではなく構造化データで取れるとパース不要になる）

---

> 「送成功」は「投票成功」ではない。真の SoT は IPAT 履歴。ここをぶらさず運用しましょう。 — シズネ
