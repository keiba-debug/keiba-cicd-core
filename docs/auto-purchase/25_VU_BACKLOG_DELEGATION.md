# 25. VUバックログ & 委任キット（2026-06-06〜）

> **司令塔 delegation tracker**。6/6 開催運用中に上がった VU 候補を集約し、別セッションに貼れる
> ハンドオフを並べる。各セッションは該当 §3 プロンプトを貼って開始 → 完了時に §1 状態を更新。
> 関連メモリ: [[ai-marks-project]] [[bet-adjustment-items]] [[bettype-selection-roadmap]] [[auto-purchase-project]]

## 0. 共通制約（全VU厳守）

- **live auto-vote 稼働中（開催日中）はコードを live 反映しない**。develop は可、live化はレース外。
- **markSet=6（AI印 評価◎○▲）は凍結・書換禁止**（将来のML特徴量化/監査）。
- **金額・投票・税務(ledger)に触る変更はシズネ・ゲート**（GO/CONDITIONAL/NO-GO）を通す。
- SoT=Python（artifact/DB/ledger 生成）、web は読む/起動するだけ（ledger-reader 流儀）。
- メモリの file:line は数日前の観察。着手時に現コードで必ず裏取り。

## 1. マスター VU バックログ

| ID | 内容 | 種別 | 出所 | 優先 | ゲート/依存 | 状態 |
|---|---|---|---|---|---|---|
| **VU-1** | AI印「買い軸連動」markSet=8（買った軸+相手を印表示） | ML+web | ふくだ 2026-06-06 / 設計書23 | ★高（ふくだ希望） | シズネ CONDITIONAL（条件①-⑥）・markSet=6凍結 | ◐ 進行中 |
| **VU-2** | settle 自動化（→ /bankroll/auto に払戻表示） | Python | W1/W5・ふくだ 2026-06-06 | ★高 | 税務整合・シズネ確認推奨 | ✅ 実装完了（scheduler 登録は ふくだ手動・admin） |
| **VU-3** | web表示強化: ①レース詳細に購入買い目モーダル(W3) ②馬詳細に My印/AI印 履歴 | web | ふくだ VU候補2,3 | 中 | なし（表示専用） | ✅ 完了（表示専用・書込なし、build/lint green） |
| **VU-4** | web制御・配線: ①自動投票コントロールエリア(W4) ②AI印 web admin配線 ③P2b web配線 | web+API | ふくだ / 本セッション残 | 中 | W4=live arm注意・P2b配線はVU-5依存 | ☐ |
| **VU-5** | P2b（adaptive 配分）live化 | 判断+deploy | P2b session | 中 | **シズネ live ゲート + ふくだ承認**・backtest済 | ☐ |
| **VU-6** | AI レース印（P2b出し分けを TARGET レース印 見送/投資/一発/買い に書く＝判断の可視化） | ML+TARGET DAT | ふくだ 2026-06-06 | 中 | **P2b依存**（出し分けが入力）・手動レース印を上書きしない・データ=`MY_DATA\RMark2/3`・dat_writer 流儀を race-level 展開 | 💡候補 |

**推奨着手順**: VU-1（ふくだ希望）→ VU-2（運用の見やすさ・settle自動化）→ VU-3（表示・低リスク）→ VU-4/VU-5（来週・gated）。
VU-1/2/3 は並行可（依存なし）。VU-4 の P2b web配線部 と VU-5 は来週まとめて。

## 2. 委任の進め方

- 各 VU を別ウィンドウ（別セッション）で起動。§3 のプロンプトを貼る。
- 完了したら §1 状態を ✅、commit ハッシュを残す。司令塔が拾って全体ビュー更新。
- 金額/投票/税務に触る VU（1,2,5）は **live 反映前にシズネ・ゲート**。

---

## 3. ハンドオフ・プロンプト

### Prompt VU-1: AI印「買い軸連動」markSet=8

```
あなたは KeibaCICD の実装担当です。AI印「買い軸連動」(markSet=8) を実装します。
SoT設計: docs/auto-purchase/23_AI_MARK_VOTE_SYNC_DESIGN.md(案C) / メモリ [[ai-marks-project]]。着手時に現コードで裏取り。

【背景】AI印 markSet=6 は composite評価の段差ベース(◎単独もあり=断然1強)。一方 自動投票は軸+相手N頭を買う。
評価印と買い目が連動せず「買ってる相手/押さえが無印」(2026-06-06 ふくだ指摘・東京2R 等)。
→ markSet=8「買い軸」専用スロットを新設し、実際に買った軸+相手を印で表示する。

【設計(案C・確定)】
- markSet=6(評価)は凍結・書換禁止。markSet=8 は別スロット。中立記号(¥/◉等)で「買い軸」を表現。
- 買い軸の出所 = ledger v2(purchase_ledger)=税務SoT 起点(scheduler_state でない)。
  軸 = portfolio内 raw_legs の積集合(アンカー型は全legが軸を含む)。相手 = 残りのleg馬。
- ふくだ確定: 軸+相手も印 / -EV軸も気にせず付ける(ブレーキ保留) / markSet=6凍結OK。

【シズネ CONDITIONAL 条件(満たす)】
① markSet=6 凍結ガード ② ledger起点 + ledger writer に axis_umaban 明示保存(box/formation将来用)
③ win_ev<1軸も印付け(ふくだ決定) ④ strategy_name=manual_cli 汚染修正を先行([[manual-auto-bet-coexistence]])
⑤ decode対称(TS+Python) + markSet=8 施錠 + round-trip テスト ⑥ audit「買い軸印は表示用・購入正本はledger」明記。

【実装】
- Python: dat_writer に markSet=8 書込(markSet=1/6/8 施錠維持)。ledger→軸+相手抽出。CLI(例 write_buy_marks --date --apply)。
- web: 出走表に markSet=8「買い軸」列を追加(AI印列の隣)。target-mark-reader 拡張・decode対称。
- テスト: round-trip(TS↔Python)、ledger→印抽出、markSet=6凍結ガード、施錠。

【成功条件】購入のあるレースで 軸+相手が markSet=8 に印表示。markSet=6 不変。pytest + npm run build/lint green。条件①-⑥充足。
【厳守】live auto-vote 稼働中(開催日中)は live 反映しない。markSet=6 は絶対書換禁止。
【完了時】§1 状態更新 + commit、メモリ [[ai-marks-project]] 更新。live反映可否はシズネ+ふくだ。
```

### Prompt VU-2: settle 自動化（/bankroll/auto 払戻表示の根治）

```
あなたは KeibaCICD の実装担当です。settle(精算)自動化を実装します。
メモリ: [[bet-adjustment-items]] W1/W5。着手時に現コード(ml/settle_ledger.py)裏取り。

【背景】/bankroll/auto に払戻が出ない(2026-06-06 ふくだ再指摘)。真因=settle_ledger 手動運用で ledger v2 の payout が空。
/bankroll/results は TARGET CSV 別経路なので出る。
【目標】レース結果確定後に settle を自動実行し ledger v2 payout を埋める → /bankroll/auto に払戻表示。
【実装案】
① 開催日 夜間 Task Scheduler で `python -m ml.settle_ledger --date <当日>`(確定後)
② or vb_refresh/別バッチに「確定レースのみ settle」を統合
③ 冪等(再実行で二重計上しない)・確定前レースは PENDING 維持・superseded/dead-heat 既存ロジック維持。
【成功条件】開催日夜に自動 settle → /bankroll/auto に払戻反映。再実行安全。pytest green。
【厳守】税務SoT(ledger)整合を壊さない。シズネ確認推奨(税務記録に触るため)。
```

### Prompt VU-3: web表示強化（購入買い目モーダル + 馬印履歴）

```
あなたは KeibaCICD の web 実装担当です。race/horse 詳細の表示強化2件(表示専用・書込なし)。

【1: レース詳細に購入買い目モーダル (W3)】
購入のあるレースに「購入あり」バッジ + モーダルで そのレースの買い目(券種/馬番/金額/受付番号/払戻)を表示。
データ = purchase_ledger v2(race別 portfolios/tickets)。既存 ledger-reader 流用。

【2: 馬詳細に My印(markSet=1)/AI印(markSet=6) 履歴】
その馬の過去レースの My印・AI印を時系列表示。馬→印履歴 reader(レース横断で markSet を馬単位集計)。
印の信頼性評価(AI印が当たってるか)にも使える。重い横断集計はキャッシュ。

【成功条件】両画面で表示。npm run build/lint green。SoT=既存データ読むだけ(書込なし)。
【厳守】live中も表示専用なので安全。markSet=6 は読むだけ(書換禁止)。
【完了時】§1 状態更新 + commit。
```

### Prompt VU-4 / VU-5（来週・gated — 着手前に司令塔へ確認）

```
VU-4 web制御・配線（一部 gated）:
  ① 自動投票コントロールエリア(W4): /bankroll/auto に multi-bettype の当日 arm/halt ボタン
     (freebudget用 AutoVoteControl S139 を拡張)。SoT=Python(schtasks作成/--halt を API経由)、web は起動/停止/監視。
     ★live betting を arm する操作なので二重ゲート + シズネ確認必須。
  ② AI印 web admin配線: write_ai_marks --step 2 --apply を /admin Phase②(execute/route.ts の予測系 +
     buildV4PipelineCommands ヘルパ)に追加。CLI SKILL は配線済(②-5)、web ボタン経路が残。npm build 検証。
  ③ P2b web配線: adaptive 出し分けを odds-race 等に表示。**VU-5 と同時**(P2b live化とセット)。

VU-5 P2b(adaptive配分)live化:
  backtest 済(ROI CI下限>baseline)。**シズネ live ゲート + ふくだ承認後、レース外で** default を
  adaptive/adaptive_fund に切替 or scheduler 戦略変更。今は dormant(opt-in)。
  → コーディングでなく「判断+慎重deploy」。来週、司令塔同席で。
```

## 4. 進捗ログ（各セッションが追記）

| 日時 | VU | セッション | 結果 / commit | 申し送り |
|---|---|---|---|---|
| 2026-06-06 | （起票） | メイン管理 | VU-1〜5 集約・委任キット作成。AI印 markSet=6 は今日手動apply済・SKILL配線済 | VU-1 から外注開始 |
| 2026-06-06 | VU-1/2/3 起動 | メイン管理 | 3件を別セッションに委任・並行起動（VU-4/5 は来週 gated で保留） | 各セッションの §4 追記待ち。web 複数触る→commit/pull 規律。金額系(VU-1/2)は live前シズネゲート |
| 2026-06-06 | **VU-2 完了** | settle自動化 | **settle 自動化 実装完了**。①`ml/settle_ledger.py` に `--today`(vb_refresh慣習)+`--catchup-days N`(前日確定の遅延払戻を拾う冪等catch-up)+複数日ループ+終了コード整備。**コアsettle/compute_payout/record_settlement は無変更**(冪等性=settled_at据置/PENDING据置/superseded/dead-heat 全維持)。②`scripts/settle_auto.bat`(lock+log、引数なし=`--today --catchup-days 2`、stale-lock 60分で自動奪取=fail-open)。③`scripts/setup_settle_scheduler.bat`(`KeibaCICD_settle` 毎日17:00-23:59/30分間隔)。テスト+5件(settle 48 / portfolio 含め62 pass)。**シズネ CONDITIONAL_GO**(🔴-1=`%date%`はログ名専用と注記/🟡-1 stale-lock/🟡-2 catchup=2/🟡-5 /du=06:59 を全反映)。3分岐(active skip/stale takeover/normal)実機検証済 | **残=ふくだが `setup_settle_scheduler.bat` を admin 実行してタスク登録**(settle は投票しない=純読取+payout書込なのでlive auto-vote ゲート対象外だが、登録は手動)。stale-lock 自動奪取で「回し忘れ/異常終了で永久halt→払戻空」を根絶。次の的中ある開催夜に /bankroll/auto 反映を実地確認 |
| 2026-06-06 | **VU-2 検証+仕上げ** | settle自動化(引継) | commit 24a45df を独立裏取り: **pytest 48/48 green**、実 ledger に `--today --catchup-days 2 --dry-run`(本日 computed42/won7/pending8、catch-up未開催=no-op skip/exit0)、`settle_auto.bat` lock 3分岐(active=skip保持 / 3h backdate=stale奪取+実行 / 通常)を cmd 実機で再確認。シズネ本セッション再レビュー反映=🟡-3 **exit≠0 を `[ERROR]` ログマーカー化**(`endlocal` 後 `exit /b` は実質0固定のため検知はログが正本)。SJIS+CRLF 維持。 | **税務メモ(シズネ🟡-1)**: 申告に使う数字は `payout`(mykeibadb 確定配当)が正本、`reconciled` は IPAT 突合(13章未実装)の有無を示す監査メタで金額の正否ではない→突合実装後 `--force` re-settle で True 昇格(`test_force_resettle_reconciled_upgrade`)。**ロールアウト順序(シズネ🔴-2)**: 開催日(本日6/6)は scheduler 登録しない。レース外で ①非開催日に `settle_auto.bat YYYY-MM-DD` 単日実settle→ledger差分/SETTLED/_index SHA連続を目視 ②`setup_settle_scheduler.bat` を admin 登録 ③初回発火を在席時 `schtasks /run /tn KeibaCICD_settle` で観察→無人運用。catchup=2 で開催翌々日まで遅延払戻を自動回収 |
| 2026-06-06 | **VU-3 完了** | web表示強化 | **2機能とも実装・表示専用(書込なし)**。①**レース詳細 購入買い目モーダル(W3)**: `ledger-reader.ts` に `getRacePurchase(raceId16)` 追加(16桁先頭8桁→日付→readLedger→flattenLedger→該当race抽出、既存flatten流用)。`RacePurchaseBadgeModal.tsx`(client, Dialog)=「購入あり」バッジ+点数、モーダルで サマリー(投資/払戻/収支/回収率/確定)+買い目テーブル(券種/馬番/金額/受付番号/払戻/結果)。races-v2 page の Promise.all に `getRacePurchase` 追加・アクション行に配置(購入無ければバッジ非描画)。②**馬詳細 印履歴**: `horse-marks-history-reader.ts`(新規)=過去走横断で My印(markSet=1+明示消合成)/AI印(markSet=6 **読むだけ**)を umaban 単位集計、ketto_num キャッシュ(TTL5分)、推奨印の3着内率(信頼性 参考値)。`HorseMarksHistory.tsx`(server, 印色分け+着順色)を horses/[id] の過去走テーブル直後に配置(印あるレースのみ・無ければ非表示)。**markSet=6 は読み取り専用、書換なし**。 | **build green の前提=main(24a45df)が既に赤だった**(VU-3 起因でない pre-existing 型エラー3件: `analysis/ml/page.tsx` ObstacleModelMeta cast / `horses/[id]` + `horse-data-reader` の `kbHorseCode` 未宣言)。stash で HEAD でも同一3件を確認後、runtime-safe な最小修正で解消(`IntegratedHorseData` に `kbHorseCode?` 追加 / ml page に cast)→`npx tsc --noEmit` clean + `npm run build` exit0(80/80 static)。自分の新規3ファイルは型エラーゼロ。lint=既存warning4件のみ(自分の変更ゼロ)。**注**: `settle_auto.bat` が外部プロセスで M 表示されるが VU-3 と無関係→コミット対象外 |
