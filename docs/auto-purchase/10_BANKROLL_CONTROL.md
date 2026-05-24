# 10. Bankroll 制御方針

> **作成日**: 2026-05-23（朝会後の合意を反映）
> **担当**: シズネ（リスク管理担当）
> **位置づけ**: 自動購入における「お金が消える経路」の最終防衛ライン定義。
> **関連**: [./09_MY_MARKS_AND_STRATEGY.md](./09_MY_MARKS_AND_STRATEGY.md)、[./05_RISK_COMPLIANCE.md](./05_RISK_COMPLIANCE.md)、[./07_DATA_SCHEMA_AND_EVENTS.md](./07_DATA_SCHEMA_AND_EVENTS.md)

---

ふくだ君、ここはシズネが一番慎重に書きました。**お金が消える経路を最初に塞ぐ** のがリスク管理の鉄則です。

## 1. 基本方針

朝会での確定事項を、設計言語に翻訳して残します。

| 項目 | 方針 |
|---|---|
| **1レース上限** | `data3/bankroll/config.json` で設定。絶対額（円）で指定。 |
| **1日上限** | 同上。絶対額（円）で指定。 |
| **初期値** | **仮置き**。運用しながらふくだ君が手動調整する前提。 |
| **動的調整** | **行わない**。連勝で増額・連敗で減額のロジックは入れない。 |
| **個別レース上書き** | 可能。1レース上限を当日UI から上書きできる。 |
| **既存 API 統合** | `/api/bankroll/check` を拡張して両上限を参照させる。 |

> カカシ先生、ここで意図的に動的調整を排除するのは、ふくだ君が「腰を据えた戦略再構築モード」（MEMORY.md 現フェーズ）にあるからです。動的調整は調整ルール自体のバグが資金消滅に直結するので、運用と設計が安定してからの後付けで十分です。

---

## 2. なぜ「動的調整なし」か（設計判断の根拠）

過去のセッション知見を踏まえ、シズネが几帳面に整理しました。

### 2.1 動的調整ルールの典型的な失敗モード

| ルール例 | 失敗モード |
|---|---|
| 連勝でレース上限を増額 | 連勝の終わりに最大ベット → 一発で資金喪失。「最後の連勝末尾」は統計的に最も負けやすい |
| 連敗で減額（Anti-Martingale）| 数学的には正しいが、心理的に「取り返したい」と逆行する判断を誘発 |
| DD で自動 kelly_fraction を下げる | フラクション変更後の挙動が直感に反し、何が起きているか分からなくなる |
| EV 高で増額 | EV 高 = キャリブレーション信頼前提。モデル劣化に気づかず資金消滅 |

### 2.2 固定値運用の利点

- **挙動が予測可能**: 「このレース最大いくら」が事前に確定している
- **デバッグしやすい**: 異常な購入額が出たら即座に「上限超過」として検知できる
- **心理的に楽**: 上限が動かないと、ふくだ君が自分の判断に集中できる
- **記録が綺麗**: 税務記録（雑所得申告）の経費計算が一定で済む

### 2.3 動的調整は「Phase 4 以降」の課題

[05_RISK_COMPLIANCE.md](./05_RISK_COMPLIANCE.md) の DD ガード（黄→橙→赤）は、自動購入の **緊急停止系** として別物です。これは「正常時の動的調整」ではなく「異常時の停止」なので、本書のスコープからは除外します。

---

## 3. `bankroll/config.json` 拡張案

### 3.1 既存スキーマ（参考）

現状 `keiba-v2/web/src/app/api/bankroll/config/route.ts` から読み取れる構造:

```json
{
  "created_at": "2026-01-01",
  "updated_at": "2026-05-22",
  "settings": {
    "total_bankroll": 100000,
    "daily_limit_percent": 5.0,
    "race_limit_percent": 2.0,
    "consecutive_loss_limit": 3,
    "kelly_fraction": 0.25,
    "use_current_balance": true
  },
  "rules": {
    "no_increase_after_loss": true,
    "confidence_adjustment": true
  },
  "target_integration": {
    "enabled": true,
    "data_root": "",
    "my_data_folder": "MY_DATA"
  }
}
```

### 3.2 拡張案（**追加** フィールド）

```json
{
  "created_at": "2026-01-01",
  "updated_at": "2026-05-23",
  "settings": {
    "total_bankroll": 100000,
    "daily_limit_percent": 5.0,
    "race_limit_percent": 2.0,
    "consecutive_loss_limit": 3,
    "kelly_fraction": 0.25,
    "use_current_balance": true,

    "per_race_max_yen": 3000,
    "per_day_max_yen": 10000,
    "limit_mode": "absolute",
    "limit_priority": "absolute_first"
  },
  "rules": {
    "no_increase_after_loss": true,
    "confidence_adjustment": true,

    "no_dynamic_adjustment": true
  },
  "race_overrides": {
    "20260524051002": {
      "per_race_max_yen": 10000,
      "reason": "自信レース・1万単で勝負",
      "created_at": "2026-05-24T08:30:00+09:00"
    }
  },
  "target_integration": {
    "enabled": true,
    "data_root": "",
    "my_data_folder": "MY_DATA"
  }
}
```

### 3.3 フィールド説明

| フィールド | 型 | 意味 | 既定値（仮） |
|---|---|---|---|
| `settings.per_race_max_yen` | int | 1レース絶対額上限（円） | `3000` |
| `settings.per_day_max_yen` | int | 1日絶対額上限（円） | `10000` |
| `settings.limit_mode` | str | `"absolute"` / `"percent"` / `"both"` | `"absolute"` |
| `settings.limit_priority` | str | `"absolute_first"` / `"percent_first"` / `"min"` | `"absolute_first"` |
| `rules.no_dynamic_adjustment` | bool | 動的調整を明示的に無効化（防衛ライン） | `true` |
| `race_overrides.{raceId}` | obj | レース単位の上書き設定 | （都度追加） |
| `race_overrides.{raceId}.reason` | str | **必須**: 上書き理由を文字列で残す | — |

### 3.4 既定値の初期化方針

- `per_race_max_yen` = `total_bankroll * race_limit_percent / 100` を **初期表示**
- `per_day_max_yen` = `total_bankroll * daily_limit_percent / 100` を **初期表示**
- 初回起動時はこの計算値で `*.json` に書き込み、以後 ふくだ君が手動で書き換える運用

ふくだ君、ここで「percent 由来の絶対額」と「絶対額」が両方あるのは冗長に見えますが、これは意図的です。
**運用が進むと total_bankroll が増減し、percent ベースだと上限が勝手に変動してしまう** ので、絶対額で持って固定するほうが安定します。

---

## 4. 運用ルール

### 4.1 初期値の仮置き

| 項目 | 仮値 | 根拠 |
|---|---|---|
| `total_bankroll` | 100,000円 | 既存設定の継続 |
| `per_race_max_yen` | 3,000円 | total × 3%（少し保守的に） |
| `per_day_max_yen` | 10,000円 | total × 10%（1日で資金1割まで） |

> 数字は **完全に仮**です。運用開始2週間で必ず見直しを入れてください。

### 4.2 上書きの運用フロー

```
ふくだ君が当日UI を開く
    ↓
「このレースは1万単で勝負」と判断
    ↓
レース詳細から「1レース上限を上書き」ボタン
    ↓
金額入力 + 理由（必須）
    ↓
bankroll/config.json の race_overrides に追加
    ↓
当該レースの bankroll/check は上書き値を参照
```

**重要**: 理由を必須にすることで、後から「なんでこのレースだけ多めに賭けたんだっけ」を追跡可能にします。税務記録の観点でも、説明可能性は確保しておくべきです。

### 4.3 上書きの有効期限

- `race_overrides.{raceId}` はレース終了後に **自動でアーカイブ**
- アーカイブ先: `data3/bankroll/history/race_overrides_{YYYY-MM}.json`
- アーカイブされた上書きは config.json から消えるが、履歴は永久保存

---

## 5. `bankroll/check` API の拡張ポイント

### 5.1 現状（route.ts 抜粋）

```ts
const totalBankroll = config.settings?.total_bankroll || 100000;
const dailyLimitPercent = config.settings?.daily_limit_percent || 5.0;
const raceLimitPercent = config.settings?.race_limit_percent || 2.0;
const dailyLimit = Math.floor(totalBankroll * (dailyLimitPercent / 100));
const raceLimit = Math.floor(totalBankroll * (raceLimitPercent / 100));
```

→ percent ベースのみ。絶対額・上書きは未対応。

### 5.2 拡張後の擬似コード

```ts
const settings = config.settings;
const overrides = config.race_overrides?.[raceId];

// 1レース上限の決定
const raceLimitFromPercent = Math.floor(totalBankroll * (settings.race_limit_percent / 100));
const raceLimitFromAbsolute = settings.per_race_max_yen;
const raceLimitFromOverride = overrides?.per_race_max_yen;

let raceLimit: number;
if (raceLimitFromOverride !== undefined) {
  // 上書きが最優先
  raceLimit = raceLimitFromOverride;
} else if (settings.limit_mode === "absolute") {
  raceLimit = raceLimitFromAbsolute;
} else if (settings.limit_mode === "percent") {
  raceLimit = raceLimitFromPercent;
} else if (settings.limit_mode === "both") {
  // both = 厳しい方を採用
  raceLimit = Math.min(raceLimitFromAbsolute, raceLimitFromPercent);
}

// 1日上限も同様（ただし overrides は raceId 単位なので適用外）
const dailyLimit = settings.limit_mode === "absolute"
  ? settings.per_day_max_yen
  : Math.floor(totalBankroll * (settings.daily_limit_percent / 100));
```

### 5.3 追加すべきレスポンスフィールド

```ts
return NextResponse.json({
  canBet,
  warnings,
  errors,
  limits: {
    dailyLimit,
    raceLimit,
    remaining,
    todaySpent,

    raceLimitSource: "override" | "absolute" | "percent",
    overrideReason: overrides?.reason ?? null,
    dailyLimitSource: "absolute" | "percent"
  },
  betTypeStats: ...,
});
```

UI 側で「この上限はどこから来たか」を表示することで、上書き設定の存在をふくだ君が常に意識できるようにします。**透明性は防衛ラインの一部** です。

### 5.4 後方互換性

- 既存の `daily_limit_percent` / `race_limit_percent` は **削除しない**
- 新規 `per_race_max_yen` / `per_day_max_yen` が **未設定の場合は percent ベースにフォールバック**
- 既存運用を壊さない移行パスを確保

---

## 6. 監査・記録要件

[05_RISK_COMPLIANCE.md](./05_RISK_COMPLIANCE.md) で触れた税務観点と紐付けます。

| 記録対象 | 保存先 | 保持期間 |
|---|---|---|
| config.json の変更履歴 | `data3/bankroll/history/config_{YYYY-MM}.jsonl` | 7年（雑所得申告要件） |
| race_overrides | `data3/bankroll/history/race_overrides_{YYYY-MM}.json` | 7年 |
| 上限超過で blocked されたベット | `data3/bankroll/history/blocked_{YYYY-MM}.jsonl` | 7年 |

ふくだ君、これは万が一の税務調査で「ちゃんとリスク管理してました」を示す資料です。地味ですが、必ず実装してください。

---

## 7. シズネからの注意点

1. **絶対額上限を入れた瞬間、percent ベースの roi グラフが歪みます**。`total_bankroll` 変更時に絶対額が追随しないことを認識しておいてください。
2. **race_overrides の蓄積で config.json が肥大化**します。当日終了時に自動アーカイブする cron / hook を必ず設けてください。実装漏れると 数ヶ月で人間が読めなくなります。
3. **`limit_mode: "both"` を使う場合、min（厳しい方）採用が原則**です。max にすると「絶対額か percent のどちらか緩い方」になり、上限の意味を失います。
4. **上書き時の reason 必須は UI 側でバリデーションしてください**。空文字を許すと数週間後に「何でこれ上書きしたんだっけ」になります。
5. **ふくだ君が自分で上書きすること自体が「動的調整」になっていないか**は、月次レビューで確認しましょう。連敗中に上限を上げてないか、連勝中に冷静さを失っていないか、人間が形骸化していないかをシズネが見ます。

---

## 8. 次のアクション

- [ ] **シズネ**: `data3/bankroll/config.json` の現物を確認し、`per_race_max_yen` / `per_day_max_yen` の初期値をふくだ君と決める（仮値 3,000 / 10,000 で開始する想定）
- [ ] **カカシ先生**: `/api/bankroll/check` の拡張実装。後方互換性を保ったまま、`limit_mode: "absolute"` で動かせる状態に
- [ ] **ふくだ君**: 月次レビューの時間枠を確保（上書き履歴と blocked 履歴を見る30分）

---

> お金が消える経路、塞いだつもりです。穴があれば指摘してください。 — シズネ
