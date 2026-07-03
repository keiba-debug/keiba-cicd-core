# 深読み三点（ふかよみさんてん）スリーブ設計（第三スリーブ・comment_a・Session 189）

> **戦略名 = 深読み三点（ふかよみさんてん）**（ふくだ命名 S189・「競馬新聞深読み馬券」の
> ニュアンスから）。内部キー/台帳の strategy_name は `comment_a` のまま（実務名=コメＡ3点セット）。

- 日付: 2026-07-03
- 状態: 設計確定 → 実装（本番投票は `comment_a_enabled=true` にしてから）
- エビデンス正本: `docs/ml-experiments/202607_comment_picks_payout_backtest.md`
- 兄弟設計: `docs/sleeve_orchestration_design.md`（器）/ `docs/selection_engine_design.md`

## 1. 位置づけ

本命EV単（honmei_ev）・逆張り単（gap_tansho）に続く **第三の買い目スリーブ**。
エッジの源泉が既存2本（モデル×市場ギャップ）と直交する **コメントLLM（qwen2.5:14b）の
関係者コメント読解**であり、ポートフォリオ分散の観点でも独立収益源。

- エッジ: コメAI印**Ａ（高確信）**の複勝的中率 人気マッチ+20pt（2025/2026 の2年で再現・
  LLMカットオフ後＝記憶汚染不可能な期間）
- 実払戻バックテスト（2026年・**実装形 2:1:1+R4増額**）: ROI **167.6%** / 尻尾除き **139.3** /
  CI95 **[124.6, 215.4]** / p(≤100)=0.001（エビデンス正本「スリーブ実装形の合算」表・
  再現 = `python -m ml.analyze.comment_sleeve_dataset build` → `... portfolio`）
- 量: Ａ印 約4点/開催日（n=207/51日・R4通過率 57%）

## 2. 選定（selection）

- 源泉: `data3/comment_llm/live/picks_YYYY-MM-DD.json`（朝の prep で生成・当日固定）の
  `confidence=="高"`（=Ａ印）のみ。Ｂ/Ｃは買わない（Ｂの量的拡張は 2026 確認で崩壊済み）。
- オッズゲート**なし**（朝に確定する選定＝[[feedback_odds_gate_hindsight]] の後知恵リスクなし）。
- ワイド相手: 当該レース predictions の **rank_w 最上位（pick 自身を除く・有効オッズ必須）**＝ML本命。
- **取消・除外ガード（シズネ 🔴-1）**: pick の馬番が当該レース predictions entries に有効オッズ
  （>0）付きで存在しない場合（取消・除外・データ欠損）は**その pick を買わない**（stderr に理由記録）。
  picks は朝固定のため日中取消は必ず起きうる。ガード無しだと runner 失敗 → 連続失敗 halt が
  **他スリーブを巻き込む**（マージ投票は1本）。
- **少頭数縮退（シズネ 🟢-4）**: 有効オッズの頭数 <5 のレースは複勝発売なし → 複勝/ワイド脚を
  落とし単勝のみに縮退（warnings 記録）。
- picks ファイル欠損/レース不在 → no-op（安全側）。ただし **enabled なのに picks ファイル自体が
  不存在**の場合は生成系（Ollama/朝prep）の障害シグナルなので、`_picks_by_race` が stderr に
  警告を出し（パス毎のログに残る）、朝の `--check`（exit 1）を prep に配線して検知する
  （Ａ印ゼロの日との区別・シズネ 🟡-1）。

## 3. 配分（sizing）— 「現状考えられる最適」

単位額 u = 残高 × `comment_a_bet_pct`%（100円切捨て・比例フラクショナル＝破産ガード内包、
gap/honmei と同式）。**1つのＡ印につき**:

| 脚 | 配分 | 根拠 |
|---|---|---|
| 複勝（pick） | **2u**（R4ゲート通過時 **3u**） | 最も証拠が強い足（ROI 163.9・CI下限124）。安定担当 |
| 単勝（pick） | 1u | ROI 192 だが尻尾除き118＝高分散。配当の天井担当 |
| ワイド（pick×ML1位） | 1u | ROI 138・p=0.021。分散平準化担当（券種間で的中がずれる） |

- **R4ゲート**＝(pred_proba_p_raw + 0.196) × place_odds_min ≥ 1.0
  （コメＡの実測上乗せ+19.6pt をモデル複勝確率に足した EV 判定。2026確認: ROI 189.9 /
  尻尾除き124.3 / p=0.0015）。通過時は複勝を1単位増額。二値絞りにしない（総利益を削るため）。
  フィールド欠損時はブーストなし（安全側）。`comment_a_r4_boost` で OFF 可。
- 既定値: 初期 bankroll 300,000 / bet_pct 0.5%（u=1,500 → 1 pick 6,000〜7,500円）/
  day_pct 10%（30,000円 ≈ 4-5 picks 日）。すべて config で変更可・**enabled 既定 False**。

## 4. 器（既存流用・新規実装なし）

- 投票/タイミング/lock/halt/オッズ鮮度/cage 二段（スリーブ日次 net-loss cage → 全体cap →
  レース合算cap）= `sleeve_orchestrator`（変更不要。registry に1行追加のみ）。
- 優先順: **honmei_ev > gap_tansho > comment_a**（新参は最後尾・cap 競合時に先に落ちる）。
- TARGET/IPAT: runner は fukusho(code1)/wide(code4) 対応済み（ff_writer.BET_TYPE_CODE）。
- settle: `day_recovery.compute_recovery`（単勝=確定オッズ・複勝=**odds_low 下限**・
  ワイド=haraimodoshi 実払戻）。複勝の下限精算は payout を過小評価（≈5-10%）する
  **保守バイアス**＝残高が実際より小さく見える安全側。既知として容認（税務 SoT は
  purchase_ledger/settle_ledger 側）。
- 口座: `data3/userdata/comment_a_live/ledger.json`（gap/honmei と完全隔離）。

## 5. config キー（bankroll/config.json settings 直下）

| キー | 既定 | 意味 |
|---|---|---|
| comment_a_enabled | **false** | master switch（web で明示 ON） |
| comment_a_initial_bankroll_yen | 300000 | 隔離口座の初期額 |
| comment_a_bet_pct | 0.5 | 1単位 = 残高×% |
| comment_a_day_pct | 10.0 | 日次cap = 残高×% |
| comment_a_r4_boost | true | R4 EVゲート通過時に複勝 2u→3u |

## 6. 運用・検証（シズネレビュー反映・S189）

- 稼働前チェック: `python -m ml.strategies.comment_a_live --check --date YYYY-MM-DD`
  （picks 有無・Ａ印数・買い目予定・カナリア3指標を dry 表示）。
  **keiba-data-prep ②（開催日準備）のチェックリストに組み込み、exit 1（picks 無し）は
  黄色警告で prep を終える**（シズネ 🟡-1）。
- **停止・点検基準（三段・シズネ 🟡-2）**:
  1. **ハードDDストップ（事前コミット・★code-enforced★）**: comment_a 口座残高が初期の
     **50%（15万円・ふくだ確定 S189）** を割ったら `CommentASleeve.is_enabled()` が自動で
     False を返し投票停止（`comment_a_live.DD_STOP_FLOOR_PCT` / `dd_stopped()`）。停止中は
     残高が動かない＝実質ラッチ。再開は原因究明のうえ増資 or config 明示変更。
  2. **早期異常検知（的中率カナリア）**: 累積 n≥80 時点で複勝Ａ的中率が**人気マッチ期待+5pt を
     下回ったら**一時停止して点検（backtest +20pt。的中率は ROI より CI が細く最速の検知器。
     監視は ledger でなく legs の複勝足単位で数える）。あわせて月次でＡ印数/日・平均人気・
     R4通過率を backtest 基準値（≈4点/日・人気5.7・57%）と突合——**選定母集団の変質は損失より
     先に現れる**（`--check` がカナリア行を毎朝出力）。
  3. **鈍化検知**: 累積 ROI（直近 n≥100）が 100% を2ヶ月連続で割る、または3ヶ月連続で
     backtest CI 下限（**124%**）を割ったら停止して再検証（gap の鮮度教訓
     [[ml-profit-roadmap]]: stale シグナルは逆シグナル化しうる）。
- **settle 再実行ルール（シズネ 🟡-3）**: 週次 prep（JRA-VAN 同期後）で前週末の
  `sleeve_orchestrator --settle` を**必ず再実行**する（冪等・上書き）。haraimodoshi 同期遅れ時、
  当夜 settle はワイド払戻を 0 円で確定させるため（day_recovery は配当未取得→0 の安全側。
  6/28 に未同期を実測済み）。
- **cap 競合監視（シズネ 🟡-4）**: state の skip_reasons の `#comment_a` 件数を週次で数える。
  月間で comment_a 候補の **10% 超が合算 cap 落ち**するなら、優先順・cap 値
  （sleeve_per_race_cap_yen=12,000 現行）・R4増額の三者を再調整。現行値の机上計算では
  **honmei_ev 同居レースの R4増額（7,500円）だけが選択的に落ちる**（6,000+7,500>12,000）
  — backtest に無い欠落バイアスなので頻度を実測する。また残高増で u が太ると固定 cap に
  単独で頭打ちする（比例フラクショナルの意味が cap で死ぬ）— 残高 1.5 倍超で cap 見直し。
- 依存の明示: ①朝 prep で live_picks（コメAI印）生成 — **keiba-data-prep ②-5.5 に配線済み
  （live_picks → live_report → write_comment_marks → `--check`。S189 で新設。従来は手動運用
  だった＝スリーブ化に伴い正式ステップ化）** ②predictions.json（ワイド相手/R4/取消ガード）
  ③ Ollama qwen2.5:14b（picks 生成側の依存）。picks 欠損日はスリーブ全体が no-op（安全）。
- **R4_UPLIFT（+0.196）の前提**: 現行 LLM/プロンプト/入力（keibabook コメント）の母集団平均。
  **qwen モデル差し替え・プロンプト変更・keibabook スクレイパー仕様変更・polaris 昇格**は
  いずれも前提変更＝shadow で1-2週末検証してから継続判断（シズネ 🟢-1）。
- 監視の実装注意: `report()` の hit は**レース単位**カウントで3点セットのどの足が当たったかは
  潰れる。的中率カナリアは votes の legs（bet_type=fukusho）を見て足単位で数えること（🟢-3）。
- 手動買いとの共存: Ａ印は `/analysis/comment-marks` 等でふくだにも見える。同じ馬を手動で
  買うと檻の外（[[manual-auto-bet-coexistence]] の既知構造リスク・口座分離が解）。

## 7. 変更履歴

- 2026-07-03 S189: 初版（設計＋実装＋テスト）。
- 2026-07-03 S189: シズネレビュー（条件付きGO）反映 — 🔴-1 取消・除外ガード＋少頭数縮退、
  🔴-2 エビデンス数値を実装形合算（167.6%・再現器 `ml/analyze/comment_sleeve_dataset.py` 収録）に
  差し替え、🟡-1 picks 欠損検知（不存在警告＋prep ②-5.5 配線＝picks 生成の正式ステップ化）、
  🟡-2 三段停止基準（ハードDD／的中率カナリア／鈍化検知）、🟡-3 settle 週次再実行、
  🟡-4 cap 競合監視。
- 2026-07-03 S189 **ふくだ確定**: ①shadow を飛ばし**小サイズ実弾で 7/4 開始**（u=1,500円・
  日次cap 3万円・隔離30万円 = 有料shadow。エビデンス文書原案の shadow 先行を明示的に置換）
  ②ハードDDストップ = **初期残高の -50%（15万円割れ）**・code-enforced（dd_stopped）
  ③R4増額 = **最初から ON**（comment_a_r4_boost=true 既定・cap落ち頻度は §6 で監視）。
