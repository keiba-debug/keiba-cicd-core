# 17. 投票後通知レイヤ (notify)

> **作成日**: 2026-05-24 (Session 129)
> **担当**: カカシ (実装) → シズネレビュー
> **位置づけ**: [16_TARGET_AUTOCLICK.md](./16_TARGET_AUTOCLICK.md) の `target_clicker` が投票 click した直後に、 「人間レイヤ」 へ事実を確実に伝えるための音声+ログ通知モジュール。 [12_KILL_SWITCH_COOLDOWN.md](./12_KILL_SWITCH_COOLDOWN.md) §「人が毎朝明示開始」 モデル + シズネ原則「お金の経路の透明性は防衛ラインの一部」 の延長線上。
> **関連メモ**: `notify-layer-roadmap.md` (Session 128 起草の roadmap)

---

## 0. なぜ通知レイヤが要るか

Session 128 のライブ検証 (2026-05-24) で分かった事実:

- 13:18:32 に新潟8R 単勝6番 受付番号 **0045** が成立 (+8,300円 初的中)
- ふくだはターミナルに張り付かないと「投票が成功したか / どの受付番号で受け付けられたか」 を即時把握できない
- 連続投票時 (例: 0045 → 0046 を 14 分間に投票) は **どっちがどっちか** ターミナルだけでは混同しがち
- 失敗時 (rejected / timeout / error) を見逃すと「投票してない」 ことに気づかず、 別の投票を重ねる事故が起こりうる

→ 「自動投票が走った事実」 を 音声 で即時通知することが Phase 4 完全自動化の安全装置として必須。

---

## 1. スコープ (Session 129)

### 1.1 最小要件 (今回実装)

- **TTS (text-to-speech) で受付番号 + 概要を読み上げる**
- 投票成功時だけでなく **rejected / timeout / error も** 音声通知
- pyttsx3 (Python SAPI ラッパ) → PowerShell SAPI (`System.Speech.Synthesis.SpeechSynthesizer`) → 黙って return の 3 段フォールバック
- TTS 失敗は監査ログには残すが本体投票フローは止めない (ログ欠損 < 状態欠損)
- CLI から `--no-notify` で OFF 可能。 `--say-test "テキスト"` で単独テスト可能

### 1.2 将来拡張 (Session 130+)

- Windows Toast (`win11toast`): 履歴残るので二次確認用
- 発走 X 分前リマインダ (Task Scheduler から呼び出し)
- 結果確定後の的中/不的中アナウンス (JRA-VAN payouts 連携)
- 1 日終了サマリ (当日収支 + 累計 ROI)

---

## 2. 設計

### 2.1 モジュール構成

```
keiba-v2/ml/target_clicker/
├── auto_vote.py     ← Session 127-128
├── menu_runner.py   ← Session 127-128
├── ff_writer.py     ← Session 128
├── runner.py        ← Session 128
└── notify.py        ← Session 129 新規
```

### 2.2 公開 API

```python
# notify.py
def speak(text: str, *, rate: int = 0, async_: bool = False) -> bool:
    """TTS で 1 メッセージ読み上げ。 成功 True / 失敗 False"""

def notify_vote_result(result: ClickResult, *, enabled: bool = True) -> bool:
    """ClickResult から人間向け文面を生成 → speak() に渡す"""

def format_receipt_number_kana(n: str | int) -> str:
    """'0045' → 'ゼロ ゼロ 四 五' (1 桁ずつ読み)"""
```

### 2.3 通知文面の生成ルール

| ClickResult.action | サンプル文面 |
|---|---|
| `clicked` (成功) | `受付番号 ゼロ ゼロ 四 五。 投票完了。 合計 千円、 ベット 三件。` |
| `clicked` + 結果ダイアログ閉じれず | `受付番号 ゼロ ゼロ 四 五。 投票完了。 結果ダイアログ閉じ失敗のため、 手動で確認してください。` |
| `dry_run` | `ドライランで投票内容を検証しました。 合計 千円、 ベット 三件。 実投票はしていません。` |
| `rejected` | `投票キャンセル。 理由: 合計金額 三千円が上限千円を超えました。` |
| `timeout` | `投票内容確認ダイアログが 六十秒以内に表示されませんでした。 投票していません。` |
| `error` | `投票エラー。 詳細はログを確認してください。` |

### 2.4 数字読みの正規化

| ケース | 入力 | 出力 (音声) |
|---|---|---|
| 受付番号 (4桁) | `0045` | `ゼロ ゼロ 四 五` |
| 金額 (1000円単位) | `1000` | `千円` (SAPI 既定読み) |
| 金額 (細かい) | `3500` | `三千五百円` (SAPI 既定読み) |
| ベット数 | `3` | `三件` |
| レース番号 | `8R` | `八レース` |
| 馬番 | `6` | `六番` |

→ 受付番号は **必ず 1 桁ずつ** 読ませる。 SAPI 既定だと `0045` を「ゼロゼロよんじゅうご」 と読んでしまうため、 空白区切り + ひらがな変換で強制。

### 2.5 voice 選択

| 環境 | 採用 voice |
|---|---|
| Windows 10/11 既定 | `Microsoft Haruka Desktop` (ja-JP, female) |
| ja-JP voice 不在時 | 既定 voice にフォールバック (音声品質は落ちる) |
| voice 完全不在時 | speak() は False を返す (テキストログのみ) |

### 2.6 TTS バックエンドの 3 段フォールバック

```
speak(text)
├── 試行 1: pyttsx3 (Python SAPI ラッパ、 同期、 高速)
│   └─ ImportError or 例外 → 試行 2
├── 試行 2: PowerShell subprocess (System.Speech.Synthesis)
│   └─ タイムアウト 30 秒 or returncode != 0 → 試行 3
└── 試行 3: 何もせず False (ログだけ残す)
```

**Why**: 依存最小化。 pyttsx3 が入っていれば使う、 入っていなくても Windows 標準の SAPI で動く。 完全失敗時も投票本体は止めない。

### 2.7 非同期化

デフォルト同期 (発話完了まで待つ)。 約 4-5 秒の読み上げが投票フローを止めるが、 投票完了 → 次のレースまで時間があるので問題なし。

将来必要なら `async_=True` で `threading.Thread(daemon=True).start()` 化可能。 まずは同期で十分。

---

## 3. auto_vote.py / runner.py への配線

### 3.1 _audit() の中で呼ぶ

`auto_vote.py:_audit()` は全パス (timeout/rejected/dry_run/clicked/error) の合流点。 ここで `notify_vote_result(result)` を `try/except` で呼ぶのが最小侵襲。

```python
# auto_vote.py 抜粋 (パッチ後イメージ)
def _audit(result: ClickResult, *, notify: bool = True) -> ClickResult:
    # ... 既存 JSONL 書込み ...
    if notify:
        try:
            from ml.target_clicker.notify import notify_vote_result
            notify_vote_result(result)
        except Exception as e:
            print(f"[notify] failed: {e}", file=sys.stderr)
    return result
```

### 3.2 CLI オプション

| ファイル | 追加オプション | 用途 |
|---|---|---|
| `__main__.py` | `--no-notify` | TTS 抑制 (テスト時) |
| `runner.py` | `--no-notify` | TTS 抑制 |
| `runner.py` | `--say-test TEXT` | notify.py 単独動作確認 (投票せずに発話のみ) |

### 3.3 click_vote_button() への引数追加

`click_vote_button(notify: bool = True)` を新設して `_audit(..., notify=notify)` に渡す。

---

## 4. 監査ログとの関係

- `audit_{yyyy-mm}.jsonl` (Session 128) に `notify_attempted: bool`, `notify_succeeded: bool`, `notify_text: str` を追加
- TTS 失敗を後から分析できるようにする (シズネ視点: 「通知ログも audit 化」 が原則)

---

## 5. 失敗パスとリカバリ

| 失敗ケース | 挙動 |
|---|---|
| pyttsx3 import 失敗 | PS SAPI にフォールバック |
| PS SAPI も失敗 (Windows 以外, SAPI 無効化, voice 0) | 黙って False, 投票本体は続行 |
| TTS 中に例外 | キャッチして本体止めない |
| TTS 30 秒以上ハング | subprocess timeout で kill → False |

**原則**: 通知は best-effort。 投票成立 (= お金が動いた) こと自体は ledger + audit JSONL が真正ソース。 音声はあくまで人間レイヤへの最速チャネル。

---

## 6. テスト

### 6.1 単独テスト

```bash
# 日本語ボイスで「受付番号 ゼロ ゼロ 四 五。 投票完了」 と読み上げ
python -m ml.target_clicker.runner --say-test "受付番号 ゼロ ゼロ 四 五。 投票完了"

# 受付番号変換ユニット
python -c "from ml.target_clicker.notify import format_receipt_number_kana; print(format_receipt_number_kana('0045'))"
# → 'ゼロ ゼロ 四 五'
```

### 6.2 統合テスト (本番手前)

```bash
# dry-run で notify_vote_result の発話を確認 (投票せず)
python -m ml.target_clicker --dry-run --timeout 60
# → 「投票内容確認ダイアログが…」 or 「ドライランで…」 が読み上げられる
```

### 6.3 本番投票 (来週末)

通常コマンドで起動するだけで自動的に音声通知が走る:

```bash
selective_vote.bat 2026-05-31 100 --confirm
# 投票完了時点で「受付番号 〜 投票完了」 が音声で流れる
```

---

## 7. シズネレビュー観点 (起草段階で想定)

| 観点 | 想定 |
|---|---|
| 通知失敗時の挙動 | 🟢 本体止めない (ログ欠損 < 状態欠損) |
| 個人情報リーク | 🟢 受付番号のみで個人特定不可、 ただし 「金額」 が同居する家庭環境では音量配慮 |
| 監査トレーサビリティ | 🟢 audit JSONL に notify 結果も追記 |
| Windows 依存 | 🟡 SAPI が Windows 限定。 macOS/Linux 移植時は再設計 |
| 連続投票時の発話衝突 | 🟡 同期発話のため衝突しないが、 重なると 4-5 秒×N の待ち時間。 将来 async 化検討 |
| 音声 OFF 環境への配慮 | 🟢 `--no-notify` で完全抑制可能 |

---

## 8. 完成基準 (Session 129)

- [ ] `notify.py` 実装 (3 段フォールバック + 受付番号 kana 変換)
- [ ] `auto_vote.py:_audit()` への配線 (失敗パスも含む全 5 action 対応)
- [ ] `__main__.py` / `runner.py` に `--no-notify` 追加
- [ ] `runner.py` に `--say-test "TEXT"` 追加
- [ ] audit JSONL に `notify_*` フィールド追加
- [ ] PowerShell SAPI で `Microsoft Haruka Desktop` を選択する動作確認
- [ ] 全 action (clicked / dry_run / rejected / timeout / error) の文面確認
- [ ] 設計書 (本ファイル) のシズネレビュー
