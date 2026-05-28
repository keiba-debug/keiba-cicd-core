# シズネレビュー: 19_OOS_RUNBOOK.md (Session 133 / OOS 直前)

> **対象**: 19_OOS_RUNBOOK.md (Session 133 起草版) + 20_CURRENT_CAPABILITIES.md (Session 133 仮振り分け)
> **検証日程**: 2026-05-30 (土) 〜 2026-05-31 (日)
> **レビュー日**: 2026-05-27 (Session 133 / OOS 3 日前)
> **観点**:
>   a) 段階的アプローチの妥当性
>   b) 失敗パターン別 SOP の網羅性 (§3.4 / §6.3)
>   c) アンチパターン (§6.4) の本能カバレッジ
>   d) 集計レポート (§7.1) の OOS 評価充足性
>   + シズネ独自: 当日精神状態 / 月初 OFF タイミング / 微妙状況支援 / ギャンブル本能ブレーキ
> **総合判定**: **条件付き GO**。 OOS 自体は段階的アプローチで実行 GO だが、 **🔴 3 件 (§6.4 抜け 2 + §7.1 評価軸 1) を 5/29 夜までに潰せば「無条件 GO」**。 過去 2 回 (131/132) と同じ詰め方ルートで月曜の振り返りに入れる。

---

## 0. 結論 (3 行)

1. **段階的アプローチ (土AM inspect → 土PM 半自動 → 日AM フル → 日PM verify loop) は妥当**。 「徐々に自動度を上げる + ダウングレード可能 + 各 phase で GO/NO-GO」 の構造は、 シズネ Session 130 §「半自動の罠」 への警戒、 [[shizune-agent]] 原則 1 「人間が形骸化するリスク」 を構造的に守れている。
2. ただし **§6.4 アンチパターン 5 件は「お金が消えた直後・勝った直後」 のふくだ本能を 1 つも明示的にカバーしていない**。 「もう一回」 衝動 / 取り戻し衝動 / 検証成功で気が大きくなる衝動 — この 3 つを構造的に塞ぐ追記が **OOS 前必須** (🔴-1)。
3. **§7.1 集計レポートが ROI 1 軸のみ**は OOS 評価としては足りない。 OOS の主目的は「儲かったかどうか」 ではなく「設計通り動いたかどうか」 = **失敗系 event 比率 / Phase 通過率 / verify loop 観測件数** を加える (🔴-3)。 ROI で「儲かったから OK」 と判定する経路を構造的に塞ぐ。

---

## 1. 評価表 — 🟢 9 / 🟡 7 / 🔴 3

| # | 観点 | 評価 | 「先に直せ」? |
|---|---|---|---|
| (1) | 段階的アプローチ §0.2 (土AM/PM → 日AM/PM) | 🟢 | — |
| (2) | GO/NO-GO 判定基準 §0.3 / NO-GO 時の半自動ダウングレード | 🟢 | — |
| (3) | 5/29 夜 Dry-run チェックリスト §1.1-1.6 | 🟢 | — |
| (4) | 不明変数 6 件の確定方法明示 §0.1 | 🟢 | — |
| (5) | inspect-launch でのデータ駆動 §2 | 🟢 | — |
| (6) | 半自動運用への明示的ダウングレード §3 (Session 128 同等) | 🟢 | — |
| (7) | §4.3 実行フロー観察の 11 step 化 | 🟢 | — |
| (8) | §5.2 verify loop 誘発シナリオ (方法 A 自然タイムアウト) の現実性 | 🟢 | — |
| (9) | §6.1 緊急停止が「Ctrl+C 推奨」 で taskkill /F を非推奨化 | 🟢 | — |
| 🔴-1 | **§6.4 アンチパターンに「もう一回」 「取り戻し」 「気が大きくなる」 3 衝動が無い** | 🔴 | **OOS 前必須** |
| 🔴-2 | **§3.4/§6.3 SOP に「PC スリープ復帰経路」 が無い** (5/30-31 連日運用で必発) | 🔴 | **OOS 前必須** |
| 🔴-3 | **§7.1 集計レポートが ROI 1 軸のみ、 設計検証軸 (Phase 通過率/失敗系比率/verify loop) が無い** | 🔴 | **OOS 前必須** |
| 🟡-A | §6.3 SOP に「Step 4 暗証番号入れたが Step 5 precheck 通らない」 行が無い | 🟡 | OOS 前 推奨 |
| 🟡-B | §1.4 Dry-run 当日プラン読み上げに「ふくだの違和感判定基準」 が無い | 🟡 | OOS 前 推奨 |
| 🟡-C | §4.4 success criteria 全 8 項目を「1 レースで全部観測」 と書いてあるが、 漏れ 1 つでも NG なのか部分 GO なのか曖昧 | 🟡 | OOS 前 推奨 |
| 🟡-D | §5.4 観測ログ書式が散文形式、 後で集計しにくい | 🟡 | OOS 後 |
| 🟡-E | §6.2 「シズネ呼んで状況レビュー」 の prompt テンプレが無い | 🟡 | OOS 後 |
| 🟡-F | §8 緊急連絡先が「?」 のまま (運用上の意思決定権限が未定義) | 🟡 | OOS 後 |
| 🟡-G | §7.5 引き継ぎ事項に「6 月以降の週次運用 SOP 策定」 だけで具体 SOP が無い | 🟡 | OOS 後 |

---

## 2. 「先に直せ」 詳細 — OOS 前必須 (5/29 夜まで)

### 🔴-1 §6.4 アンチパターンが「ふくだ本能的ギャンブル衝動」 を 1 つも明示カバーしていない

**問題**:

現状 §6.4 (`19_OOS_RUNBOOK.md:455-462`) は **5 件すべて「技術的アンチパターン」**:

- ledger 手動編集
- selective_vote.bat 連続実行
- --no-bankroll-check 常用
- --ignore-recent-session-expired 確認なし指定
- 暗証番号環境変数化

これは **シズネ自身が日頃言っている本来カバーすべき領域** をスキップしている。 [[feedback_betting_philosophy]] (ふくだの賭け哲学 = パターン縛らない / 動的調整なし) + [[shizune-agent]] 原則 5 「勢いで決めたい発言には立ち止まる」 が**完全にコード化されていない**。

OOS 当日 (特に 5/31 日 PM、 verify loop 観測した直後) に高確率で起こる本能反応:

| 衝動 | 想定状況 | リスク |
|---|---|---|
| **「もう一回」 衝動** | フル自動 1 レース成功 → 「すごい動いた、 もう 1 レース回してみよう」 | 5/29 段階で計画してない bets[] を急遽追加 = max_yen 増額誘惑 |
| **「取り戻し」 衝動** | フル自動で 1,500円 負けて終了 → 「あと 1 レースで取り戻したい」 | 「最終レース」 だけ手動投票 → ledger 整合崩壊 / per_day_max_yen 突破誘惑 |
| **「気が大きくなる」 衝動** | verify loop の復旧フローが綺麗に決まった → 「完璧だ、 来週から amount=500 に上げよう」 | OOS 1 日成功で運用パラメータを上げる判断 = sample N=1 で意思決定 |
| **「面倒くさい」 衝動** | 復旧手動コマンド (recover-session) を打つのが面倒 → 「次は --no-recover で行こうか」 | Session 132 で構造的に塞いだ「思考の隙間」 を自分で外す |
| **「観察者疲れ」 衝動** | 朝から音声通知 6 連発 (起動/プラン/ログイン/受付/...) で疲れた → 「通知音 OFF にして放置しよう」 | --no-notify 常用化 = 内容確認ゲート (シズネ 🔴 A) の骨抜き |

**修正案**: §6.4 に「行動アンチパターン」 サブセクションを追加。 OOS 中の各 phase で「これをやったら止める」 のリストを明文化。

```markdown
### 6.4.b 行動アンチパターン (ふくだ本能的衝動への構造的歯止め)

- ❌ OOS 中に「計画外の bets[]」 を追加投票
  → 5/29 夜時点の selective_bets.json を SoT として固定。
  追加が必要と感じても 5/31 終了まで触らない。 触りたいなら shizune 呼ぶ。
- ❌ OOS で負けた直後の「最終レースだけ手動で取り戻す」
  → 半自動運用にダウングレードしても OK だが、 計画額を上げない。
  「マイナス分の取り戻し」 という発想自体が Themis 原則違反。
- ❌ OOS 1 日 (sample N≤2) で運用パラメータ (amount / max_bets) を上げる
  → 6/6-7 月初 OFF 練習日まで、 amount=100 / max_bets=3 を固定。
  パラメータ変更は最低 4 週 (= 4 開催日) の累計データを見てから。
- ❌ 「面倒」 を理由に Session 131/132 シズネ防御 (二重認証ゲート /
  recover-session 手動 / 通知音) を OFF にする
  → 「面倒さ = 構造的安全弁」 (Session 132 学び)。
  OFF にしたい衝動が出たら即 shizune 呼ぶ。
- ❌ 通知音が「うるさい」 を理由に --no-notify 常用
  → 当日プラン読み上げ = 二重認証ゲート (シズネ 🔴 A)。
  外したら内容承認していないのと同じ。 一時的に音量下げる だけにする。
```

**判定**: **OOS 前必須**。 これは「シズネがレビューに入る理由そのもの」 (TEAM_ROSTER.md 「ブレーキ役」)。 文面追記 10 分、 効果は OOS 期間中の全 phase に渡る。

**所要**: 10 分。

---

### 🔴-2 §3.4/§6.3 SOP に「PC スリープ復帰経路」 が無い

**問題**:

5/30-31 は 2 日連続運用 = ふくだは土曜 PC を一度シャットダウン or スリープして日曜再開する可能性が高い。 だが SOP には:

- ☓ PC スリープ復帰時の TARGET 状態は?
- ☓ スリープ復帰で IPAT セッションは生きてる? 死んでる?
- ☓ スリープ復帰で `IPAT_SESSION_EXPIRED` event が ledger に記録されるか? それとも「気付かないまま投票試行」 か?
- ☓ Wi-Fi 一時切断 → 復帰時の挙動は §5.2 方法 B (上級、 任意) にあるが、 PC スリープ復帰は別事象

**実害想定 (5/31 朝に必発しうるシナリオ)**:

```
5/30 PM 半自動運用終了 → ふくだ PC スリープ
5/31 AM PC 復帰 → IPAT セッションは死んでいるが TARGET ウィンドウは残ってる
       → ふくだ「あれ昨日の続き?」 と思って selective_vote.bat 叩く
       → precheck_ipat_session は「メニュー accessible + cmd_id 取得可」 で
         **誤って OK 判定** (実装は launcher.py を信じる、 IPAT Web 残高は見ない)
       → 投票試行 → 投票ダイアログ表示されず timeout
       → IPAT_SESSION_EXPIRED event 記録 → 音声警告
       → ふくだ「あ、 セッション切れか」 → 再ログイン
       → ★ここで 「直近 1h SESSION_EXPIRED」 (Session 133 修正B) が発火し、
         --auto-launch が abort される ★
       → ふくだ「ええ、 単に再起動しただけなんだけど…?」 と混乱
```

つまり **Session 133 修正B の「直近 1h チェック」 が、 PC スリープ復帰経路で誤発火する確率が極めて高い**。 これは新機能の「副作用」 だが SOP に書かれてない = 当日ふくだが混乱する。

**修正案**:

§3.4 / §6.3 表に以下 2 行追加:

```markdown
| PC スリープ復帰後の最初の selective_vote.bat | (1) TARGET ウィンドウを×で閉じてから始めるのを推奨 (2) IPAT Web で残高表示が出るか目視 (3) NG なら半自動運用に戻る | 起動時 SESSION_EXPIRED チェック (修正B) がスリープ後初回に高確率で発火することを §6.4 認知パターンに記録 |
| 修正B の `--ignore-recent-session-expired` を打つ判断基準 | ledger 直近 IPAT_SESSION_EXPIRED_POSTVOTE が「PC スリープによる擬似」 と確信できる場合のみ。 確信なければ 30 分待って自動失効を待つ | 「擬似」 と「本物」 の判別ガイドを Session 134 で 19 §6.5 として整備 |
```

加えて §0.1 不明変数表に追加 (#7 として):

```markdown
| 7 | PC スリープ復帰時の IPAT セッション挙動 (Wake-up でセッション維持されるか / 別事象として切れるか) | 5/30 PM 終了後にスリープ → 5/31 AM 復帰で観測 | 19 §6.5 (Session 134 で整備) |
```

**判定**: **OOS 前必須**。 これを書かないと、 5/31 朝にふくだが「壊れた? バグ?」 と推測して時間溶かす可能性が高い。 ふくだの shizune 呼出 1 回分以上の価値。

**所要**: 15 分 (表 2 行 + §0.1 追記)。

---

### 🔴-3 §7.1 集計レポートが ROI 1 軸のみ — 「OOS 評価」 として致命的に不足

**問題**:

§7.1 (`19_OOS_RUNBOOK.md:469-488`) は「投資合計 / 払戻合計 / 件数 / 差額 / ROI」 のみ。 **これは「儲かったかどうか」 の集計であって「OOS 検証として GO/NO-GO」 の判定材料ではない**。

OOS の本来の目的:
> 「現実とコード想定のズレを 1 個ずつ確定すること」 (本書 §551 カカシ言)

であれば集計すべきは:

1. **Phase 通過率**: 各 Phase (4-A 起動 / 4-B IPAT メニュー / 4-C-min precheck / 4-C-full 復旧) が「試行 N 回中 何回成功したか」
2. **失敗系 event 比率**: 成功系 (APPROVED / IPAT_CONFIRMED) vs 失敗系 (VOTE_FAILED / IPAT_START_FAILED / TARGET_SAVE_FAILED / TARGET_DIALOG_UNKNOWN / IPAT_SESSION_EXPIRED / IPAT_SESSION_EXPIRED_POSTVOTE / IPAT_SESSION_RECOVERED / IPAT_SESSION_RECOVERY_FAILED) の件数比
3. **verify loop 観測件数**: 18 §1.3 success criteria 6 項目目の達成数 (検知 → 音声 → ledger event → audit JSONL の end-to-end が連結している件数)
4. **音声通知到達率**: notify_text 発生件数 vs notify_spoken=True 件数 (TTS 失敗が静かに起きてないか)
5. **idempotency 重複検知件数**: 同 portfolio/ticket の duplicate 検知が**ゼロであること** (ゼロなら設計通り、 1 以上なら何かが二重実行された)
6. **selective_loader スキーマ違反件数**: 0 件であること (Session 129 🔴 J 防御の確認)

**最も致命的なリスク**: ROI が +10% だったとして、 もし上記 1-6 のどれかが想定外なら「**儲かったから OK 判定** → 翌週も同じ運用 → 隠れバグが累積 → ある日大事故」 のシナリオが成立する。 シズネとして絶対に許容できない。

**修正案**:

§7.1 / §7.2 を以下に置換:

```markdown
### 7.1 設計検証集計 (OOS の主目的)

```powershell
# ① Phase 通過率
./.venv/Scripts/python.exe -c "
import json
from collections import Counter
events = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/events_2026-05.jsonl', encoding='utf-8') if l.strip()]
events = [e for e in events if e.get('at', '').startswith('2026-05-3')]
counts = Counter(e.get('type') for e in events)
total_attempts = counts.get('FF_WRITTEN', 0)
for phase, ok_event, fail_events in [
    ('4-A 起動', 'IPAT_CONFIRMED', ['TARGET_DIALOG_UNKNOWN']),
    ('4-B メニュー', 'IPAT_CONFIRMED', ['IPAT_START_FAILED']),
    ('4-C-min precheck', 'APPROVED', ['IPAT_SESSION_EXPIRED']),
    ('4-C-full 復旧', 'IPAT_SESSION_RECOVERED', ['IPAT_SESSION_RECOVERY_FAILED']),
]:
    ok = counts.get(ok_event, 0)
    fail = sum(counts.get(f, 0) for f in fail_events)
    print(f'{phase:15} success={ok:3d} fail={fail:3d}  pass_rate={ok/(ok+fail)*100 if (ok+fail) else 0:.1f}%')
"

# ② 失敗系比率
./.venv/Scripts/python.exe -c "
import json
from collections import Counter
events = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/events_2026-05.jsonl', encoding='utf-8') if l.strip()]
events = [e for e in events if e.get('at', '').startswith('2026-05-3')]
counts = Counter(e.get('type') for e in events)
success_events = {'APPROVED','IPAT_CONFIRMED','FF_WRITTEN','TARGET_IMPORTED','IPAT_SESSION_RECOVERED'}
failure_events = {'VOTE_FAILED','IPAT_START_FAILED','TARGET_SAVE_FAILED','TARGET_DIALOG_UNKNOWN','IPAT_SESSION_EXPIRED','IPAT_SESSION_EXPIRED_POSTVOTE','IPAT_SESSION_RECOVERY_FAILED'}
n_success = sum(counts.get(t, 0) for t in success_events)
n_failure = sum(counts.get(t, 0) for t in failure_events)
print(f'成功系: {n_success} / 失敗系: {n_failure} / 比率: {n_failure/n_success*100 if n_success else 0:.1f}%')
print(f'判定基準: 失敗系/成功系 比率 ≤ 30% なら設計通り')
"

# ③ verify loop 観測件数 (18 §1.3 success criteria #6)
./.venv/Scripts/python.exe -c "
import json
events = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/events_2026-05.jsonl', encoding='utf-8') if l.strip()]
events = [e for e in events if e.get('at', '').startswith('2026-05-3')]
expired_postvote = [e for e in events if e.get('type') == 'IPAT_SESSION_EXPIRED_POSTVOTE']
recovered = [e for e in events if e.get('type') == 'IPAT_SESSION_RECOVERED']
verify_loops = min(len(expired_postvote), len(recovered))  # 簡易版: 数の min
print(f'IPAT_SESSION_EXPIRED_POSTVOTE: {len(expired_postvote)} 件')
print(f'IPAT_SESSION_RECOVERED:        {len(recovered)} 件')
print(f'verify loop 観測 (簡易): {verify_loops} 件 (target: 1 件以上)')
"

# ④ TTS 到達率
./.venv/Scripts/python.exe -c "
import json
audit = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/target_clicker/audit_2026-05.jsonl', encoding='utf-8') if l.strip()]
audit = [a for a in audit if a.get('at', '').startswith('2026-05-3')]
with_notify = [a for a in audit if a.get('notify_text')]
spoken = [a for a in with_notify if a.get('notify_spoken')]
print(f'notify_text 発生: {len(with_notify)} 件')
print(f'notify_spoken=True: {len(spoken)} 件')
print(f'TTS 到達率: {len(spoken)/len(with_notify)*100 if with_notify else 0:.1f}%')
print(f'判定基準: 95% 以上')
"

# ⑤ idempotency 重複検知件数 (= 二重実行の兆候)
./.venv/Scripts/python.exe -c "
import json
events = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/events_2026-05.jsonl', encoding='utf-8') if l.strip()]
events = [e for e in events if e.get('at', '').startswith('2026-05-3')]
dups = [e for e in events if e.get('payload', {}).get('action') == 'duplicate']
print(f'idempotency duplicate 検知: {len(dups)} 件')
print(f'判定基準: 0 件 (1 以上は二重実行の兆候、 即 shizune 呼出)')
"

# ⑥ selective_loader スキーマ違反件数
./.venv/Scripts/python.exe -c "
import json
events = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/events_2026-05.jsonl', encoding='utf-8') if l.strip()]
events = [e for e in events if e.get('at', '').startswith('2026-05-3')]
schema_violations = [e for e in events if e.get('type') == 'VOTE_FAILED' and 'schema' in str(e.get('payload', {})).lower()]
print(f'selective_loader 違反: {len(schema_violations)} 件')
print(f'判定基準: 0 件 (Session 129 🔴 J 防御の動作確認)')
"
```

### 7.2 GO/NO-GO 判定確定 (設計検証ベース)

| 評価軸 | 基準 | OOS 結果 |
|---|---|---|
| Phase 4-A 起動 通過率 | 100% (許容下限 90%) | _ / _ % |
| Phase 4-B IPAT メニュー 通過率 | 100% (許容下限 90%) | _ / _ % |
| Phase 4-C-min precheck false negative | 0 件 | _ 件 |
| Phase 4-C-full 復旧 verify loop 観測 | 1 件以上 | _ 件 |
| ledger event 失敗系/成功系比率 | ≤ 30% | _ % |
| TTS 到達率 | ≥ 95% | _ % |
| idempotency duplicate | 0 件 | _ 件 |
| selective_loader schema violation | 0 件 | _ 件 |
| 起動時 SESSION_EXPIRED チェック (修正B) 発火確認 | OOS 中 1 回以上の意図的発火試験 | _ 回 |

→ **全 9 軸 ✅ なら「無条件 GO」**。 1 軸でも NG なら **NO-GO + 原因究明 + Session 134 で修正 + OOS 再実施 (翌週末)**。

### 7.3 ROI 集計 (副次)

(従来の §7.1 ロジック、 ただし「副次」 として位置づけ)

判定基準: なし。 OOS の主目的は「設計通り動いたか」 であり、 ROI は **OOS 評価軸ではない** (sample N が小さすぎる)。
```

**判定**: **OOS 前必須**。 これがないと「儲かった → 翌週も同じ運用」 で隠れバグ累積経路が成立する。 [[shizune-agent]] 原則 1 「人間が形骸化するリスク」 + 原則 3 「税務・記録で困らないか」 の核心。

**所要**: 30 分 (集計コード + 判定表)。

---

## 3. Session 132 残宿題 4 件の OOS 前/後 振り分け再判定

20 §7 の仮振り分けに対するシズネ判定:

### 🟡-2 (phase 文字列リテラル定数化) → **20 案「★★★ OOS 前」 に同意**

**理由**:
- タイポすると `manual_review_required` が**静かに False** = 監査ログに「rollback 不能事象だがフラグなし」 が混入
- 工数小 (定数 1 ファイル追加 + 参照 3-4 箇所)
- OOS 後に潰そうとすると、 OOS で記録された ledger event の payload が「修正前バグ含み」 か「正しい挙動」 かの判別が遅れる
- **OOS 前必須で同意**。 5/29 夜に潰す

### 🟡-5 (session_expired_patterns v2 verified_by 必須化) → **20 案「★★★ OOS 前」 に同意、 ただし条件付き**

**理由**:
- OOS 当日 (5/30 PM or 5/31 AM) に inspect-launch で実機 pattern を取得 → JSON 書き込みする時に、 verified_by が必須化されてないと「verified_by 抜けの JSON が事故的にコミットされる」 経路成立
- ただし「実機 dump → 後追いで verified_by 追記」 の方が現実的で、 そっちで防げないか?
- **シズネ判定**: 「load 時 WARNING」 だけは OOS 前必須、 「必須化 (起動時 abort)」 は OOS 後で OK
  - 5/30 当日に「verified_by 入れてないと起動しません」 で詰まると現場で困る
  - WARNING だけなら気づかせる + 投票進行は止めない = 段階的アプローチと整合

**修正提案**: 20 §7 の「🟡-5 OOS 前必須」 を分解:
- (a) load_session_expired_patterns / load_dialog_whitelist_v2 に verified_by 欠落時 stderr WARNING = **OOS 前必須** (30 分)
- (b) verified_by 欠落で起動時 abort 化 = **OOS 後** (Session 134)

### 🔴-1 修正B (起動時 SESSION_EXPIRED チェック) → **20 案「★★★ OOS 前」 に賛成、 ただし PC スリープ復帰経路 (🔴-2) と同時対応**

**理由**:
- 二重投票防止の最終層であることは同意
- ただし上記 🔴-2 で書いた通り、 修正B は **PC スリープ復帰で誤発火する** リスクが高い
- ふくだの質問「入れずに OOS で『修正B が無いと何が起きるか』 を観察してから?」 への回答:
  - **入れた状態で OOS に臨むべき**。 理由: 「修正B が無い場合に起こる事故」 = 二重投票 = 実害が大きすぎる
  - ただし**意図的発火試験を OOS 中に 1 回行う**。 試験手順: 5/30 PM 終了後にスリープ → 5/31 AM 復帰直後に意図的に selective_vote.bat 叩く → 発火確認 → `--ignore-recent-session-expired` で継続

**OOS 中の試験手順を §4.3 に追加推奨**:
```markdown
[★ 修正B 動作確認 (OOS 中に 1 回必須)]
14. 5/31 AM PC 起動直後、 直近 1h に SESSION_EXPIRED が無いことを確認した上で、
    意図的に IPAT セッション切れを誘発 (暗証番号入力後 60 秒放置)
15. selective_vote.bat 再実行 → 起動時チェックで exit 8 になることを確認
16. ledger 確認後 --ignore-recent-session-expired で継続できることを確認
```

### 🟡-8 (多段モーダル対応) → **20 案「★★ OOS 後」 に同意**

**理由**:
- 「OOS で 2 段以上を実機観察してから実装方針確定する方が筋」 は同意
- 1 段だけなら現状 Step 1 (`_close_session_expired_dialog`) で十分
- ただし**OOS で 2 段観察した瞬間に Session 134 で即対応**、 後回しにしない (= 設計判断保留中の不安定領域は早期解消)
- **OOS 後対応で同意**。 観察結果次第で Session 134 必須

---

## 4. シズネ独自観点

### 4.1 当日 (5/30 朝) の精神状態防御策

**現状の SOP の弱点**: 「ふくだは元気でターミナルを正しく読める」 前提。 実際の OOS 当日 (土曜朝) に起こりうる:

- 寝不足 (前日 5/29 夜遅くまで Dry-run やってる可能性)
- 朝食前で血糖値低い
- 「初めての --auto-launch」 への興奮で注意散漫
- 通知音が連発して感覚過負荷

**追加推奨 (§1 末尾に挿入)**:

```markdown
### 1.7 当日精神状態 self-check (5/30 朝、 selective_vote.bat 叩く前)

以下 3 つを声に出して確認:
- [ ] 「いま、 selective_bets.json の中身を 1 件以上目で見たか?」 (見てなければ §1.5 やり直し)
- [ ] 「いま、 今日の投資総額を口で言えるか?」 (言えなければ §1.6 bankroll 確認)
- [ ] 「いま、 何かトラブルが起きたら最初に何を確認するか?」 (答えが「ledger と IPAT 履歴」 で出れば OK、
      出なければ §6.3 を一度読み返してから始める)

3 つどれかが詰まったら **30 分待つ or コーヒー 1 杯飲んでから** start。
朝の 5 分の遅れより、 寝不足の状態で --auto-launch を叩いた事故の方が痛い。
```

**所要**: 5 分追記。 [[shizune-agent]] 原則 5 (「勢いで決めたい発言には立ち止まる」) のセルフサービス化。

### 4.2 月初 OFF 練習日の設定タイミング

**ふくだの質問**: 6 月初開催日 (6/6-7) で正式設定するか、 OOS 結果次第か

**シズネ判定**: **6/6-7 を OOS 結果に依らず固定で「OFF 練習日」 として宣言**。 理由:

- OOS で「無条件 GO」 が出ても、 翌週から週次運用に入ると 18 §1.5 「自動化スキル劣化防止」 のための定期歯止めが**現実に運用されない**経路成立 (現場の「今週は GO だったから来週も GO」 慣性)
- 月初固定にしておけば、 ふくだは「6/6 は OFF」 をカレンダーに先に書ける = 意思決定リソース消費ゼロ
- 6/6 OFF をやってみた上で「やはり毎月不要」 と判断するならその時下ろせばよい (= 設定を緩めるのは容易、 設定がない状態から作るのは難しい = [[shizune-agent]] 「不可逆性の非対称」 と同型)

**追加推奨**: 19 §7.5 引き継ぎ事項に追加:
```markdown
- [ ] 6/6 (土) を月初 OFF 練習日として確定 (OOS 結果に依らず、 18 §1.5 に従う)
      → 6/6 朝に半自動運用で 1 レース投票 → 5/30-31 OOS 結果との比較 = 「自動化なしでも回せる筋力」 維持確認
```

### 4.3 「ふくだは止める権限あり、 でも止める判断ができないとき」 のサポート構造

**ふくだ提示シナリオ**: 「投票確認 dialog が出続けて 30 秒経過」 のような微妙な状況

**現状の SOP の不足**: §6 「失敗時 切り戻し SOP」 は「明確な失敗」 だけ扱っている。 **「微妙な状況」 (= 進めるべきか止めるべきか判断つかない)** への支援が無い。

**シズネ提案 — §6.2 の前に挿入**:

```markdown
### 6.0 「進めるべきか止めるべきか」 判断つかないときの 3 秒ルール

OOS 中に「これは止めた方がいいのか、 続けた方がいいのか」 と 3 秒以上迷ったら、
**即 Ctrl+C で stop**。

判断材料:
- 迷っている = 想定外の状態 = 設計外
- 設計外で「続けた方が早い」 と感じるのは大抵 sunk cost 効果
- 止めて IPAT 残高目視 + ledger 確認 = 失う時間 5 分
- 続けて事故 = 失う金額 数千〜数万円 + 復旧時間 数時間

判断つかない時は shizune を呼ぶ:
```
Agent(subagent_type='shizune', prompt='''
OOS 中。 状況: [今ターミナルに出ている最後の 10 行コピペ]
ledger 直近: [purchase_ledger/2026-05-3X.json 末尾 30 行コピペ]
IPAT 残高: [目視確認した値]
私の懸念: [自分が「これ大丈夫?」 と感じている点を 1 文]
進めるべきか止めるべきか判断したい。
''')
```

shizune は 1-2 分で「止める」 「続けて OK」 「もう少し情報集めて」 のいずれかを返す。
迷う時間 30 秒以上 = shizune 呼出のコスト (1-2 分) を上回るので、 呼んだ方が安い。
```

**所要**: 10 分追記。 これがあると、 ふくだの「判断疲労」 が「shizune に投げる」 に置換されて事故率が下がる。

### 4.4 ギャンブル本能ブレーキ — kill switch / cooldown 周り

**現状**: 12_KILL_SWITCH_COOLDOWN.md が存在するが、 19 OOS_RUNBOOK は kill switch に**一切言及していない**。 これは重大な抜け。

**確認したい点**:
- OOS 中に kill switch (= 当日 emergency_stop) を発火させたら何が起こる? runner.py は止まるが ledger には何が記録される?
- cooldown は OOS 中に発火する条件下にあるか? (例: per_day_max_yen 到達)
- 「+N 円勝った直後 / -N 円負けた直後」 の cooldown は実装されているか?

**シズネ判定**: 19 に §6.6 として追記推奨:

```markdown
### 6.6 kill switch / cooldown の OOS 中の扱い

- 12_KILL_SWITCH_COOLDOWN.md で定義された当日 emergency_stop は OOS 中も有効
- 発火条件 (Session 133 時点で実装確認要):
  - per_day_max_yen 到達 (config.json 既定値)
  - per_race_max_yen 違反 (race_overrides 含む)
  - selective_loader schema 違反
  - 起動時 SESSION_EXPIRED チェック発火 (Session 133 修正B)
- 発火時の挙動:
  - runner.py exit ≥ 5
  - ledger event KILL_SWITCH_TRIGGERED (12 §4.6 / 14 §6) 記録
  - 音声警告
  - 当日中は selective_vote.bat 再実行不可 (??? 実装確認要)
- OOS 中に意図的発火試験 (5/31 PM):
  - per_day_max_yen を 500 円 に一時的に下げて 1 件投票 → 2 件目で発火確認
  - 確認後 元の値に戻す
- ★「もう一回」 衝動 (§6.4.b) と kill switch の関係:
  - kill switch 発火後の「あと 1 レースだけ」 は構造的に不可能 (config 変更が必要)
  - config 変更しようとした瞬間 = 危険サイン = shizune 呼出
```

**所要**: 20 分追記 + 実装確認 (Session 134 で 12 章との整合チェック)。

---

## 5. 質問への直接回答

### a) 段階的アプローチの妥当性
**🟢 妥当**。 「土AM データ取り → 土PM いつも通り → 日AM 新機能試運転 → 日PM verify loop」 は完璧な順序。 NO-GO 時の半自動ダウングレードも明示済 (§0.3)。 これに加え、 4.1 「当日精神状態 self-check」 を入れれば「人的要因」 まで段階化される。

### b) §3.4 / §6.3 SOP の網羅性
**🟡 ほぼ網羅、 ただし「PC スリープ復帰」 が抜け** (🔴-2)。 加えて「復旧 Step 4 で暗証番号入れたが Step 5 precheck が通らない」 行も無い (🟡-A)。 後者は 🟡 として OOS 前推奨。

### c) §6.4 アンチパターンが本能的失敗をカバーしているか
**🔴 全くカバーされていない**。 5 件すべて技術的アンチパターン。 「もう一回」 「取り戻し」 「気が大きくなる」 「面倒くさい」 「観察者疲れ」 5 衝動を明示追記要 (🔴-1)。

### d) §7.1 集計レポート ROI のみで十分か
**🔴 全く不十分**。 OOS の主目的は「設計通り動いたかどうか」、 ROI は副次。 9 軸 (Phase 通過率 / 失敗系比率 / verify loop / TTS 到達率 / idempotency duplicate / schema violation / 起動時チェック発火 + ROI 副次) で再構成要 (🔴-3)。

---

## 6. ふくだに確認したい論点 (3 件)

1. **🔴-1 行動アンチパターン追記**: OOS 中の自分の本能的衝動を構造的に塞ぐリストを §6.4.b として追加する案。 「これは過保護すぎ」 と感じるか、 「ありがたい」 と感じるか? シズネは追記推奨だが、 ふくだの「ブレーキうるさい」 感覚との均衡確認したい。

2. **🔴-3 設計検証集計**: 「ROI で判定しない、 9 軸で判定する」 を OOS 評価基準に格上げする案。 翌週運用 GO の判定が ROI ベースだと「儲かったから OK」 経路で隠れバグ累積。 シズネは強く推奨。 ふくだとして「儲かったかどうか」 が知りたい気持ちと「設計検証」 が知りたい気持ちの優先順位確認したい。

3. **4.2 月初 OFF 練習日固定化**: OOS 結果に依らず 6/6 を OFF 練習日として確定する案。 「OOS 大成功なら不要では?」 と感じるか、 「定期歯止めとしてあった方が安心」 と感じるか?

---

## 7. OOS 検証前 To Do (推奨優先順)

| 優先度 | 項目 | 工数 | 担当 | 期限 |
|---|---|---|---|---|
| 🔴 必須 | 🔴-1: §6.4.b 行動アンチパターン 5 衝動追記 | 10 分 | カカシ | 5/29 夜 |
| 🔴 必須 | 🔴-2: §3.4/§6.3 に PC スリープ復帰行追加 + §0.1 不明変数 #7 追加 | 15 分 | カカシ | 5/29 夜 |
| 🔴 必須 | 🔴-3: §7.1/§7.2 を設計検証集計 9 軸に再構成 + ROI を §7.3 副次に降格 | 30 分 | カカシ | 5/29 夜 |
| 🔴 必須 | Session 132 🟡-2 (phase 文字列定数化) | 30 分 | カカシ | 5/29 夜 |
| 🔴 必須 | Session 132 🟡-5(a) (verified_by 欠落 WARNING のみ、 abort 化は OOS 後) | 30 分 | カカシ | 5/29 夜 |
| 🔴 必須 | Session 133 修正B (起動時 SESSION_EXPIRED チェック) | 60 分 (既に 17 tests 通っているなら配線確認のみ) | カカシ | 5/29 夜 |
| 🟡 推奨 | 4.1: §1.7 当日精神状態 self-check 追記 | 5 分 | カカシ | 5/29 夜 |
| 🟡 推奨 | 4.3: §6.0 「3 秒ルール + shizune 呼出 prompt」 追記 | 10 分 | カカシ | 5/29 夜 |
| 🟡 推奨 | 4.4: §6.6 kill switch / cooldown 記述追加 + 実装確認 | 20 分 | カカシ | 5/29 夜 |
| 🟡 推奨 | 4.2: §7.5 に 6/6 OFF 練習日固定化 1 行追加 | 3 分 | カカシ | 5/29 夜 |
| 🟢 OOS 後 | Session 132 🟡-5(b) (verified_by 欠落 abort 化) | 20 分 | Session 134 |
| 🟢 OOS 後 | Session 132 🟡-8 (多段モーダル対応、 OOS 観察次第) | 60 分 | Session 134 |
| 🟢 OOS 後 | 🟡-A/D/E/F/G | 各 10-30 分 | Session 134 |

**🔴 必須 6 件 合計工数**: 2 時間 45 分。 5/29 夜 (金曜) で完了可能。

---

## 8. Session 133 内で対応すべき優先項目 トップ 3

過去 2 回のレビュー (131 で🔴 4 件 / 132 で🔴 1 件) と同じく、 **🔴 を全潰しして「無条件 GO」 で OOS に臨むパターン**を踏襲。 トップ 3 は:

1. **🔴-3 (§7 集計レポート再構成)** ★最優先★
   - 理由: これがないと OOS 結果を ROI で評価 → 隠れバグ累積経路成立。 1 件で OOS の意味が壊れる
   - 「儲かったから GO」 経路を構造的に塞ぐ
2. **🔴-1 (§6.4.b 行動アンチパターン)**
   - 理由: シズネが入る根本理由 (ブレーキ役)。 これを書かないなら「シズネレビュー受けた意味」 が薄い
   - 5/31 PM の verify loop 成功時の高揚状態への構造的歯止め
3. **🔴-2 (PC スリープ復帰)** + Session 133 修正B
   - 理由: 5/31 朝に必発しうるシナリオ。 SOP に無いと現場で「バグ?」 と混乱
   - 修正B 配線と同時に SOP に書くことで、 副作用と挙動が同じ場所に文書化される

---

## 9. 累積トーンメモ (シズネ自身の振り返り)

過去 3 回のレビュー (129/130/132/133) を並べると、 シズネ → カカシのフィードバックパターンが固まってきた:

| Session | 評価 | 🔴 件数 | 着地 |
|---|---|---|---|
| 129 | 留保付き GO | 3 | OOS なし、 Session 内 全潰し |
| 130 | 条件付き GO | 4 | 同上 全潰し → Session 131 無条件 GO |
| 132 | 条件付き GO | 1 | Session 内 全潰し → ふくだ判断 2 件 (B 入れる / --confirm 見送り) |
| 133 | 条件付き GO | 3 | **OOS 前必須 6 件 (🔴 3 + 🟡-2/🟡-5(a)/修正B)** で「無条件 GO」 で OOS に臨める |

**学び**:
- シズネは「**毎回 🔴 1-3 件出るくらいが健全**」 (0 件だと見落とし疑い、 5 件以上だとカカシ側の品質低下)
- 「OOS 前必須 を 5/29 夜までに全潰し」 のリズムが定着
- ふくだは過去 2 回とも「シズネ推奨案 全採用 + ふくだ独自判断 1-2 件」 で意思決定 = この型を OOS でも継続

---

> 「OOS の主目的は『現実とコード想定のズレを 1 個ずつ確定すること』 — これは ROI で測れない。 9 軸で測る。 そして OOS 中の最大リスクは技術的失敗ではなく、 ふくだの本能的衝動 (もう一回 / 取り戻し / 気が大きくなる)。 アンチパターン 5 件に行動 5 衝動を加え、 PC スリープ復帰の現実シナリオを SOP に書けば、 5/30-31 は『無条件 GO』 で臨める。 月曜の振り返りでは『儲かったかどうか』 ではなく『設計通り動いたかどうか』 を最初に確認する文化を 19 章で確立する。」 — シズネ (Session 133, 2026-05-27)
