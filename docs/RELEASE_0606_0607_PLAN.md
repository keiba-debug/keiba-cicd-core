# リリース計画 — 2026/06/06・06/07 開催向け

> **司令塔ドキュメント**（master）。個別セッションはここを読み、成果を本ドキュメントの「進捗ログ」に追記する。
> メモリは参照のみ（docs がマスター）。
> 作成: 2026-06-05（金・開催前日） / メイン管理セッション

## 0. 役割分担

- **このセッション = メイン管理（司令塔）**: 全体計画・依存関係・締切・最終整合性チェック。実作業はしない。
- **個別セッション = 実作業**: 各 P 項目を独立に「成功条件 → verify → コミット」で回す。

各個別セッションの開始時にこのドキュメントの該当 P を読み、終了時に「§5 進捗ログ」へ1行追記すること。

## 1. ゴール

6/6（土）・6/7（日）開催に、①データが整い ②買い目抽出・配分が改善された状態で臨む。

## 2. マスター計画

```
P0 データ整備 ──┬─ P0-A 先週分(5/30・5/31)結果取得+集計再計算   ← 最優先・即着手
                └─ P0-B 6/6・6/7 翌日準備(Phase②)              ← 締切 6/6 09:00
                          │
P1 基盤(Kelly抽出のみ) ───┤  ← 即着手可・P0と並行
                          ▼
P2 本VU 買い目抽出・配分向上 ← P1完了後
P3 学習期間見直し          ← P0-A の集計リフレッシュ後
```

| 優先 | 系統 | 内容 | 担当 | 依存 | 締切 | 状態 |
|---|---|---|---|---|---|---|
| **P0-A** | データ | 先週分(5/30・5/31)成績取得 + 集計再計算（`keiba-data-prep` Phase①: 結果登録 + RPCI/レイティング/IDM/調教師/調教/血統/出遅れ） | データセッション | なし | 6/6 朝 | ✅ 完了 |
| **P0-B** | データ | 6/6・6/7 翌日準備（`keiba-data-prep` Phase②: 出馬表→レースJSON→JRDB統合→調教→ML予測・買い目） | データセッション | P0-A推奨先行 | **6/6 09:00**（vb_refresh稼働まで） | ✅ 6/6完全 / ⏳ 6/7=安田記念のみ(枠順未公開・§6) |
| **P1** | 基盤 | Kelly計算式を共通モジュールへ抽出（下記§3） | VUセッション | なし | P2前 | ✅ |
| **P2** | 本VU | 買い目抽出・配分計算の向上（Session141「評価は信じる・配分で勝つ」の本体） | VUセッション | **P1完了後** | — | ☐ |
| **P3** | 学習 | 学習期間を5月まで拡張（前年5月までの範囲拡大検討） | 学習セッション | **P0-A後** | — | ☐ |

クリティカルパス = **P0**（6/6 09:00 締切）。P1 は並行可。

## 3. P1 基盤調査の結論（2026-06-05 実施）

買い目抽出・配分計算コードの棚卸し結果：**大きなリファクタは不要**。総合評価 **(B) 軽い清掃のみ**。

- ✅ アーキテクチャ健全（Phase2 `bettype_efficiency` → Phase3 `bettype_selection` → 配分 `bettype_sizing` の分離）。テスト約1,900行。
- 🔧 **唯一の下ごしらえ（P2直前推奨）= Kelly計算式の二重定義解消**:
  - `ml/strategies/bettype_sizing.py:74-90` と `ml/strategies/freebudget.py:182-190` がコピペ。
  - 配分をいじると両方修正が必要になり乖離リスク。共通モジュール（`ml/strategies/kelly.py` 等）へ抽出し両呼び出し元をテストで担保。~2h。
- ⏸ **保留でよい改善**（今回のP2には不要・2個目のスケジューラ/オーバーレイ追加時まで）:
  - scheduler の state/lock 重複（`bettype_scheduler.py` ↔ `freebudget_scheduler.py`）
  - `bettype_selection.select_plans`(333-393) の strategy パターン化
  - `bettype_efficiency.build_plans`(326-430+) の券種別分割
  - specialist overlay の niigata1000 ハードコード → レジストリ化

## 4. P3 学習期間 — 確定事項と要確認

- ✅ **現production = polaris v2.3（2026-06-05 裏取り済）**: `data3/ml/models/polaris/live/meta.json`（version "2.3"・P/W/AR 3モデル+calibrator）と `model_meta.json` が一致。enif(障害)・eclipse(差し)は別用途モデル。train `2020〜2025-03` / val `2025-04` / test `2025-05〜2026-03`、2026-04-26作成。
- ℹ️ v5.6 は旧実験系（env の追加 working-dir / `versions/` に残存しているだけ）。**メモリに「v5.6 production」の記載は無く、メモリは polaris を正しく参照**（当初の懸念は誤検出）。学習は polaris v2.3 を起点に。
- ℹ️ 命名: 実験レポート=v8.x 系 / モデルmeta=polaris 2.x の二重採番（[[multi-model-naming]] 準拠）。次版は polaris 2.4 想定。
- ✅ **分割確定（2026-06-06 ふくだ）**: 「**前年同月(2025.06)が学習に効くか**」を α/β アブレーションで検証（共通OOS test = `2025.07-2026.05`、≈1年確保）。β=train→2025.06（前年同月あり）/ α=train→2025.05（なし）。**β>α なら前年同月は重要**。詳細は §8 Prompt P3。ふくだ仮説「前年同月は重要かもしれない」。
- 学習エントリ: `ml/experiment.py`（CLI `--train-years` / `--val-years` / `--test-years`、`parse_period_range` が `2020-2026.04` 形式を解釈）。静的3分割（walk-forwardではない）。
- 🔗 **依存（重要）**: 学習範囲拡張は引数変更だけでは不可。集計インデックス（`horse_history_cache.json` / JRDB index / `sire_stats_index` / `race_level_index`）の**リフレッシュが先**＝ **P0-A 完了後に着手**。
- リーク注意: `--sire-cutoff` で血統特徴のテスト期間リークを防ぐ。

## 5. 進捗ログ（個別セッションが追記）

| 日時 | P | セッション | 結果 / commit | 次への申し送り |
|---|---|---|---|---|
| 2026-06-05 | P1調査 | メイン管理 | 基盤調査完了 → (B)軽い清掃のみ。Kelly抽出1点のみ要 | P2着手前にKelly抽出 |
| 2026-06-05 | P0/P1起動 | メイン管理 | データセッション(P0-A→P0-B) と VUセッション(P1) を並行起動。両者進行中 | 完了報告待ち |
| 2026-06-06 | P1 | VUセッション | ✅ **完了**。Kelly計算式を新規 `ml/strategies/kelly.py` に共通化(SSoT)。`bettype_sizing`/`freebudget` を呼び出しに置換し挙動不変(リファクタのみ)、`test_kelly.py` 追加。`pytest ml/tests/` = **491 passed**(既存 `test_bet_engine` 7 fail は本変更前から存在・stash比較で無関係を確認)。commit `ad76bd2` | **P2 解禁** — 配分VUは kelly.py 1箇所修正で両経路(bettype_sizing/freebudget)へ反映可。§3 保留項目(scheduler共通化/select_plans/build_plans/specialist)は未着手のまま |
| 2026-06-06 | P1検証 | メイン管理 | 司令塔レビュー: commit `ad76bd2` 実在(4ファイル/+184−37)・`kelly.py` 純関数で式一致・呼び出し元(bettype_sizing L185/199・freebudget L181)が kelly 経由・対象テスト40 passed を裏取り。**挙動不変を確認**。※報告の float 例「int(10000*0.4)=3999」は実際 4000(プロースの誤り、コード挙動はテストで担保) | P1検収OK。commit/push 判断待ち |
| 2026-06-06 | **P0-A** | データセッション | ✅ **完了**。5/30(SE 361/finish 98%)・5/31(SE 348/finish 99%)結果登録 + 検索index再構築(22,805R)。**集計7種すべて再計算済**(race_type_standards/race_trend_index/rating_standards/race_level_index/idm_standards/trainer_patterns/training_analysis/sire_stats_index/slow_start_analysis = 6/6 00:46-00:51更新)。 | 🔗 **P3(学習)の依存=集計インデックスのリフレッシュ完了**(§4)。`sire_stats_index`/`race_level_index` 等は本日更新済 → **P3 着手可** |
| 2026-06-06 | **P0-B** | データセッション | ✅ **6/6完全**: build_race_from_keibabook 24R(ID解決 332/332=100%・JRDB全頭付与)→cyokyo→調教サマリー3,624頭→predict 24R/closing 21R/generate_bets/vb_refresh(**Value Bets 50**)。predictions.json(652KB/24R 全Rに勝率予測)+bets.json 生成。odds 24/24取得済(前売り)。rebuild-index済。 ⏳ **6/7は安田記念(東京11R)1Rのみ**: keibabook/JRDB/JRA-VAN の独立3ソースとも日曜アンダーカード未公開(枠順決定前)。partial で predictions/bets は生成済(1R)。**今回のスコープ=「6/6開催の準備」で確定(ふくだ)**。 | ℹ️ **6/7(日)データは 6/6(土)日中にならないと提供されない(ふくだ確認・仕様)**→ 6/6日中の提供後に Phase②(6/7)を再実行で full card 化(build_race_from_keibabook→...→vb_refresh)。クリティカルは6/6=達成。<br>✅ **時刻齟齬=解決**: マシンlocal `01:08:27 土`=ネットワーク `16:08 UTC(金)`+9h と秒まで一致→**マシン時計は正確(実時刻も土曜 深夜1時)**。ふくだ申告「8時」は勘違い。9:00タスクは実9:00に正常発火、12時までの最新オッズ予測は自動で間に合う |
| 2026-06-06 | P3分割確定 | メイン管理 | ふくだ確定: 前年同月(2025.06)効果を α(train→2025.05)/β(train→2025.06) アブレーションで検証、共通OOS test=2025.07-2026.05(≈1年)。§4・§8 Prompt P3 更新済 | P3着手可。set_active はレース外 |

## 6. 監視中フラグ（司令塔が追跡）

- ⚠️ **`mykeibadb_daily` 異常終了**（2026-06-05 19:02, Last Result=`-1073741510`=0xC000013A 強制終了相当）。日次オッズDB取得が今日コケた可能性。raceday_sat/sun タスクは正常なので当日オッズは取れる見込みだが、**別途調査**（ふくだ指示で本件は分離）。→ **P0-B時点の追記**: 6/6オッズは前売り24/24取得済(時系列最新 HAPPYO=06051902)。`mykeibadb_raceday_sat` は LastResult=0x0(正常)・NextRun=6/6 9:00 で armed。当日ライブは raceday_sat に依存（daily クラッシュは履歴バッチ・当日には非影響の見込み）。
- ☑ ~~Phase①（先週末集計）が実際に走ったか~~ → **P0-Aで確認・完了**（集計9成果物が 6/6 00:46-00:51 に更新済）。
- ⏳ **6/7(日)アンダーカード未公開**（2026-06-06 確認）: keibabook（ページ「枠順決定前出馬」）/ JRDB(`KYI260607.txt`=17行=1R) / JRA-VAN(SR/SE 0件) の**独立3ソースとも安田記念以外が未着**。バグではなく日曜カードの公開タイミング。**6/7(日)データは 6/6(土)日中まで提供されない(ふくだ確認・仕様)**。→ 6/6日中の提供後に 6/7 Phase②再実行で full card 化（クリティカルパス6/6は達成済・今回スコープは6/6準備で確定）。
- ✅ **時刻齟齬=解決済**: マシン local `2026-06-06 01:08:27 土` = ネットワーク時刻 `Fri 16:08 UTC`+9h で**秒まで一致 → マシン時計は正確**（実時刻も土曜 深夜1時）。ふくだ申告「8時」は勘違い。タスクは NextRun 9:00 のまま正常（まだ深夜1時なので未発火が正しい）。9:00 に raceday_sat→ライブオッズ、vb_refresh が拾い、12時までに最新オッズ予測=自動で間に合う見込み。

## 7. 最終整合性チェック（開催直前に司令塔が実施）

- [ ] 6/6・6/7 の race dir / predictions.json / bets.json 生成済み
- [ ] odds DB 鮮度OK（raceday タスク稼働）
- [ ] vb_refresh 稼働中（土 09:00〜）
- [ ] 予想→評価→選定→投票→記録 チェーンが通る

## 8. ハンドオフ・プロンプト（個別セッション起動用）

> 新規セッションにコピペして開始。完了時は §5 進捗ログに1行追記し、§2 の状態を更新すること。
> 共通: working dir 基準 `C:\KEIBA-CICD\_keiba\keiba-cicd-core`。SoTは本ドキュメント（`docs/RELEASE_0606_0607_PLAN.md`）。

### Prompt P0: データセッション（P0-A → P0-B）

```
あなたは KeibaCICD のデータ整備担当です。6/6（土）・6/7（日）開催に向けた週次データ準備を実行してください。
SoT: docs/RELEASE_0606_0607_PLAN.md（開始時に §2・§4・§6 を読む）

【タスク】2フェーズを連続実行（/keiba-data-prep スキルを使う）
P0-A = Phase①: 先週末 2026-05-30(土)・05-31(日) の結果登録 + 全集計再計算
        （RPCI / レイティング / IDM / 調教師 / 調教 / 血統 / 出遅れ）
P0-B = Phase②: 翌日準備 2026-06-06・06-07
        （出馬表スクレイプ → レースJSON構築 → JRDB統合 → 調教サマリー → ML予測・買い目）

【成功条件】
- Phase① 完了: 5/30・5/31 の結果が登録され、各集計成果物が更新されている
- Phase② 完了: 以下が生成される（司令塔の最終チェック項目）
  - C:\KEIBA-CICD\data3\races\2026\06\06\predictions.json と bets.json
  - C:\KEIBA-CICD\data3\races\2026\06\07\predictions.json と bets.json
- 6/6 09:00 の vb_refresh 稼働開始までに Phase② 完了（クリティカルパス）

【検証】
- 上記 4ファイルの存在・更新時刻・サイズを確認
- predictions.json の中身が当日レース分そろっているか軽くスポットチェック

【完了時】
- docs/RELEASE_0606_0607_PLAN.md §5 進捗ログに結果を1行追記、§2 の P0-A/P0-B 状態を ✅ に更新
- P3（学習期間拡張）はこの集計リフレッシュに依存するので、Phase① 完了を §5 に明記

【注意】mykeibadb_daily が 6/5 に異常終了している（§6）。Phase② のオッズ取得で不足が出たら本件を疑い、司令塔に報告（深掘りは別セッション）。
```

### Prompt P1: VUセッション（Kelly計算式の共通化）

```
あなたは KeibaCICD の実装担当です。買い目VU（P2）の前提となる基盤の下ごしらえを行います。
SoT: docs/RELEASE_0606_0607_PLAN.md（開始時に §3 を読む）
コード基準: keiba-cicd-core/keiba-v2 / テスト: python -m pytest ml/tests/

【背景】Kelly 計算式が2箇所にコピペされており、配分ロジック（P2）を触ると両方修正が必要で乖離リスクがある。共通化して P2 を解禁する。
- ml/strategies/bettype_sizing.py:74-90  kelly_amount(...)
- ml/strategies/freebudget.py:182-190    （同式のミラー）

【タスク】
1. 純関数として Kelly 計算式を共通モジュールへ抽出（推奨: 新規 ml/strategies/kelly.py、もしくは ml/bet_engine.py に kelly_amount()）。
2. bettype_sizing.py / freebudget.py の両方を共通関数の呼び出しに置換（挙動は完全不変＝既存の結果と1円も変わらないこと）。
3. 共通モジュールの単体テストを追加（境界: 負EVで0、per_bet_cap_pct 上限、100円単位丸め）。

【成功条件】
- Kelly 計算式の定義が単一（Single Source of Truth）になっている
- 既存テストが全て green（特に test_bettype_sizing.py の kelly_amount==freebudget 一致テスト）
- 挙動不変（リファクタのみ、機能追加なし）

【検証】
- python -m pytest ml/tests/ -v が all pass
- diff が最小（Kelly 抽出と呼び出し置換に限定）

【完了時】
- 日本語で最小コミット、docs/RELEASE_0606_0607_PLAN.md §5 進捗ログに commit ハッシュ付きで追記、§2 の P1 状態を ✅ に更新
- 「P2 解禁」を §5 に明記

【保留（やらないこと）】scheduler の state/lock 共通化・select_plans の strategy パターン化・build_plans 分割・specialist レジストリ化（§3 の保留項目。今回スコープ外）。
```

### Prompt P2: VUセッション（買い目抽出・配分の向上 ＝「評価は信じる・配分で勝つ」）

```
あなたは KeibaCICD の実装担当です。本VU（自動購入3軸目の本丸）に着手します。
SoT: docs/RELEASE_0606_0607_PLAN.md。思想の出典（メモリ）: bet-adjustment-items 項目4 / feedback_betting_philosophy §4 / bettype-selection-roadmap 構想1 Phase3-4。
前提: P1完了済（Kelly は ml/strategies/kelly.py が SSoT。配分は kelly.py の1箇所修正で bettype_sizing/freebudget 両経路へ反映）。
※メモリの file:line は数日前の観察。着手時に現コードで必ず裏取りすること。

【核心思想】AIの馬評価（composite / win_prob / AI印◎○▲）は信じてよい（5/31 目黒記念で◎○▲完璧的中＝実証済）。
勝敗を分けるのは「評価した馬を どう資金配分・券種選択するか」。ここを詰める。

⚠️【リスク/タイミング — 司令塔指示・厳守】
- 本VUは実際に金額を動かす変更。**6/6・6/7 のライブ投票に未検証ロジックを載せない**。既定は dry-run / shadow 観察。
- live 反映は backtest で ROI 改善を示し + シズネ ゲート通過後。原則 **来週以降**。レース当日に配分ロジックを差し替えない。
- **vs_tansho（合成オッズ<単オッズ）を fund 条件に使わない**（シズネ置き土産）。控除率下では市場オッズでほぼ全プラン EV<1 が常態で、合成比較は「広げる相対妙味」であり期待値の符号ではない。fund 判断は EV絶対水準 + bankroll。
- 固定「○○モード/プリセット」を作らない・連勝増額等の動的調整なし（feedback_betting_philosophy）。

──────────────────────────────────
【P2a：軸選定の同点団子バグ修正（correctness・優先・低リスク）】
症状: hole_seeker の `bettype_selection.find_taste_axis(popularity_gap_max)` が、win_prob が同点・僅差の馬を
  順位(win_rank)で「model上位の過小評価馬」と誤認し、77倍級の下位団子馬を軸にする。
  → AI評価（◎）と買い軸が 8R中7R 不一致＝無印ばかり買う主因。
病的ケース（着手時に再現確認）: 京都12R `2026053108031212` ⑯(77倍/gap+13、実は⑧⑰と同値の下位団子) /
  京都8R `2026053108031208` ⑥(60倍/複勝率3%)。
あるべき: 「評価した馬の中で妙味を買う」＝同点・僅差を上位扱いしない。
対応:
  ① gap軸採用を3条件化: gap≥閾値 かつ win_prob絶対値≥閾値 かつ 2位との差/比が突出（＝同点でない）。
     満たさなければ composite軸（=AI印◎）に据え置き。
  ②（検討）軸候補を AI印（◎○▲△Ⅲ）が付く馬に限定し、評価と買いを直結。
受け入れ: 上記2レースで軸が composite上位/AI印馬に戻る + 回帰テスト追加。

【P2b：配分・券種の出し分け（本丸・develop+backtest、live は後）】
bettype_efficiency（合成オッズ・期待リターン一覧＝Phase2実装済）を「選定の足切り・出し分け」に配線する。
求める挙動（レース特性に応じて）:
  - 単のみ（◎突出/流す妙味なし）
  - 増額（自信度・EV・bankroll から張る）
  - 大穴100円流し（ローリスク・ハイリターン枠。当たればラッキー、外しても痛くない）
  - 降りる（妙味なし/評価が割れすぎ）
併せて 複勝薄利floor（項目1）: 低オッズ複勝（例 <1.8〜2.0倍）or 最低期待利益(円)未満は除外。
実装: bettype_sizing の SIZER 差し替え（--sizing プラガブル）+ bettype_selection。
**backtest 必須**（walk-forward / 既存 ml/analyze/backtest_strength_weights.py 流用可）。ROI改善を示してから live。
──────────────────────────────────

【成功条件】
- P2a: 病的2レースで軸是正 + pytest 全green。
- P2b: backtest で ROI 改善（CI下限で判定）+ dry-run 出力が妥当。
- §3 の保留項目（scheduler/select_plans/build_plans/specialist）は触らない。

【完了時】
- 日本語で最小コミット。docs §5 に commit付きで追記、§2 P2状態を更新。
- live 反映可否は **シズネ + ふくだ判断** を §5 に明記（自分で set/有効化しない）。
```

### Prompt P3: 学習セッション（学習期間の拡張 → polaris 2.4 候補）

```
あなたは KeibaCICD のML担当です。学習期間を見直し、polaris 2.4 候補を検証します（マイナーVU）。
SoT: docs/RELEASE_0606_0607_PLAN.md §4。
前提: P0-A完了で集計インデックス（sire_stats_index / race_level_index / horse_history_cache 等）はリフレッシュ済＝学習データ依存はクリア。
現production = polaris v2.3（train 2020〜2025.03 / val 2025.04 / test 2025.05〜2026.03）。
学習エントリ = ml/experiment.py（--train-years / --val-years / --test-years、parse_period_range が "2020-2026.04" 形式を解釈）。静的3分割 + bootstrap CI。

【Step 0: 分割をふくだと確定（着手前に必ず）】
ふくだ確定（2026-06-06）: 検証する仮説＝「**前年同月(2025.06)を学習に入れると効くか**」。α/β アブレーションで測る。
  - β（本命・前年同月あり）: train 2020-2025.06
  - α（対照・前年同月なし）: train 2020-2025.05
  - **共通OOSテスト期間で β・α・v2.3 を比較**（テストは直近1年弱を確保＝ふくだ「テストに1年は要る」）。**β>α なら「前年同月は重要」が裏付く**。
  - val（早期停止用1ヶ月）と test の非重複は P3セッションが clean に設定（例: 共通 test=2025.08-2026.05、val は各 train 直後月）。要は 2025.06 の train/test 帰属だけ toggle し test は共通に。
  - ※司令塔注意: 実レース月 2026.06 は test外＝本検証は「直近OOSでの recency/前年同月効果」を測る（6月固有の季節性の直接検証には将来 walk-forward が要る）。
  - 本番用（効果確認後・最大データ）: 勝った分割を直近(例 2026.04)まで延ばし val 2026.05 で再学習し production候補に。

【タスク】
1. **α・β の2分割で polaris 2.4候補を各1本学習**（--version で 2.4a/2.4b 等に分け、血統リーク防止に --sire-cutoff 指定）。
2. **α・β・v2.3 を同一OOSテスト期間で比較**: AUC(P/W) + ROI（bootstrap CI 1000×）。**ROIのCI下限で改善を判定**。**β>α で「前年同月効果」を確認**。
3. 勝った分割を本番用（直近まで最大データ）で再学習し production候補に。どれも改善なければ「拡張は効かず＝現状維持」を記録。

【成功条件】
- v2.3 vs 2.4 の比較レポート（docs/ml-experiments/、命名 v{番号}_{英名}.md）。
- 改善判定が CI下限ベースで明示されている。

⚠️【厳守】**set_active（live昇格）は 6/6・6/7 のレース中にやらない**（投票チェーンに影響）。今回のゴールは比較・レポートまで。昇格は ふくだ承認後・レース外。

【完了時】
- docs §5 追記、§2 P3状態を更新。実験ログをメモリ（ml_experiment_log）にも反映。
```
