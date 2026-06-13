# 03. Change Log（更新履歴）

## 2026-06-14 (Session 155 — E-009 follow-up 完了：複勝ROI / walk-forward / option差込口)

- danger-model 着手前に**測定器（E-009 harness）を先に正す**判断（[[feedback_proactive_debt_paydown]]）。danger-model は買い目層介入＝価値は gap-ROI/CI でしか測れず（E-003/E-004 の教訓）、現 harness は①単勝ROIのみ②月別なし＝place側で荒れに強い danger を測れない。3点を実装し E-009 を閉じた。
- **① 複勝ROI**: `fukusho_payout()`（純関数・確定複勝配当 100円あたり、in-the-money外/欠損=0）追加。`enrich` で各行に付与、`measure` で `fuku_payout` を集計し `bootstrap_roi` でブートCI。レポートに「複勝ROI / 複ROI CI」列。**精算の非対称（意図的）**: 単勝は T-5直前オッズ(実行価格)で後知恵回避、複勝は odds_db に T-5複勝オッズが無いため確定配当で精算（ゲートでなく精算用途ゆえ影響小・docstring 明記）。
- **② walk-forward 月別**: `row_month()` + `monthly_breakdown(rows, gap_min)` で月別に単勝/複勝ROI+CI。`--monthly` / `--monthly-gap N`。集計値の幸運な窓に騙されず「特定 gap 帯で各月とも勝てるか」を見る後知恵防止。劣化期間(3-6月)実走で gap>=2 が全月 単勝<100%（73/62/49/36%）＝アグリゲートの幻想を月別で否定できることを確認。
- **③ apply_option 差込口**: `OPTION_REGISTRY`（name→純関数 rows→rows）+ `opt_none`/`opt_high_conviction`（動作例）+ `--option`。指定時は baseline と変換後を同指標で前後比較（gap/band/月別すべて）。**payout/cutoff_odds/hit は改竄せず「どの bet を残すか・予測値補正」のみ**＝精算整合を保つ制約を docstring 明記。danger-model 着手時は danger フラグで割引/除外する関数を1行登録して採否判定できる。
- **検証**: `test_validate_live_predictions.py` 7→**12件green**（fukusho_payout/複勝ROI/row_month/monthly_breakdown/option_registry 追加）。end-to-end: 複勝ROI が `<2.9` 帯で P複勝乖離 -0.219 ／複勝ROI 86%(CI[81,90]) と place 側の妙味/較正バイアスを bet単位で拾えることを実測（[[place-calibration-bias]] 接続）。option 前後比較も baseline 673bet vs high_conviction 155bet で動作確認。
- **➡ これで analysis-reuse バックログ E-001〜E-010 が全て done**。次は [[danger-model-project]]（凡走確率モデル）。この harness の `--option` に danger 割引を登録し、複勝ROI×walk-forward で採否判定する設計が整った。

## 2026-06-14 (Session 155 — E-007 / E-008 導線：再集計ボタン＋cutoff必須化)

- **E-007 騎手接戦の再集計導線を追加 — jockeys.json 凍結の根治ボタン**
  - 凍結インシデント（[[ml-cache-staleness-incident]]）は源データ `jockeys.json`（SE_DATA年集計）の鮮度ギャップが主因。`analysis.jockey_close_finish` を回すだけでは古い master を再集計するだけなので、**master再構築→接戦再集計の2段**を1ボタンに。
  - `api/admin/execute/route.ts`: `rebuild_jockey_close` ＝`build_jockey_master`→`jockey_close_finish` 順次。`commands.ts` の `ActionType` + 両 switch に追加。`jockey-close-finish/page.tsx` ヘッダに `<RecalcButton>`。
  - **付随：IDM 再集計の穴埋め**: IDM 画面に再集計導線が無かった→ `calc_idm_standards` アクション＋サーバーコンポーネント用 `recalc-refresh-button.tsx`（`router.refresh()` ラッパ）を新設し配置。
- **E-008 血統 cutoff の PIT リーク防止を「警告続行」→「既定で停止」に厳格化**
  - `ml/experiment.py` は ①`--sire-cutoff` 未指定 ②cutoff>=test_start ③cutoff付きファイル欠落（通常版に黙フォールバック）の3ケースを **WARNING print で続行**＝リークしたまま学習が走るリスクがあった。全3ケースを **`sys.exit(2)` 停止**に変更。意図的な全データ利用の明示オプトアウト `--allow-sire-leak` を新設。load_data に `allow_sire_leak` 追加で黙フォールバックも封鎖。
  - `ml.experiment` を引数なしで回す自動呼び出し元は scripts/tests/skills に無く（手動実験専用）破壊なし。
- **検証**: web tsc 0エラー（.next/types 既存除く）。experiment.py syntax OK＋`--help` に `--allow-sire-leak` 登録確認。ゲートは load_data 前（重い処理前）で未指定なら即停止。

## 2026-06-14 (Session 155 — E-010 / E-006 拡張：連続量3分析＋鮮度ヘッダ4画面)

- **E-010 を残り連続量3分析（RPCI / IDM / レイティング）に拡張 — `mean_se` 初の本適用**
  - これまで E-010 適用済みは率系5分析（調教師/調教/出遅れ/接戦/血統）のみで、`quality_meta.mean_se`（連続量）は未稼働だった。今回 RPCI/IDM/レイティングに quality+coverage+`schema_version="quality_meta/1"` を付与し mean_se を本番投入。
  - **RPCI** `analysis/race_type_standards.py`: `calculate_course_stats` に `rpci_weighted_mean` の **weighted mean_se**（ci95 は運用閾値と同じ weighted_mean 基準・SE=√(Σw²)·σ/Σw・effective_n=(Σw)²/Σw²）。by_distance_group 8/8 付与・ci95 null 0・effective_n 例 2504。stability は年別レイヤ未構築のため insufficient（Phase 2）。
  - **IDM** `analysis/idm_standards.py`: `_compute_grade_stats` に `winner_idm_mean`（n=winner_count の mean_se）。by_grade 20/20 付与。小サンプル→全年齢プールの fallback は `copy.deepcopy` で隔離し quality に `source`/`original_n` を注記（S-6・プール側汚染を防止）。fallback 5件で実証。
  - **レイティング** `analysis/rating_standards.py`: `_compute_grade_stats` に `rating_mean`（n=horse_count の mean_se）。by_grade 23/23 付与。同型 fallback deepcopy。
  - **coverage は created_at でなく実データ開催日レンジ**を刻む（凍結インシデント同型予防）。3ソースの構造遅延が可視化された＝**レイティング to_date=6/07（最新・keibabook）/ RPCI=5/31（pace/lap 確定遅延 約1週）/ IDM=5/24（JRDB 確定遅延 約2週）**。
- **check_coverage に3分析を追加＋構造遅延の許容（lag_days）**: TARGETS に4要素目 `lag_days`（RPCI=10 / IDM=21 / 他=0）。`--expect` 判定を `expect - lag_days` で緩和し、遅延ソースの **false STALE を回避**しつつ真の凍結（例 4月）は依然検知。`--expect 2026-06-07` で全8分析 OK・exit 0 を実測。
- **E-006 鮮度ヘッダを残り4画面に配線**: `rpci` / `idm` / `rating` / `pedigree`。API/reader は metadata を素通しするため、各 metadata 型に `coverage?`/`schema_version?` を足し `<FreshnessHeader>` を設置。遅延の大きい RPCI/IDM/血統には note で「直近開催未反映でも異常でない」旨を明示。idm-standards-reader に `QualityMeta` 型を追加。
- **検証**: pytest `test_quality_meta`/`test_quality_gate` 35件green（ヘルパ不変）。web tsc 自ファイル0エラー（総数5は既存 `.next/types` のみ）。3ビルダー実走で production JSON 更新（旧版は versioning archive）。
- **残**: stability の年別集計レイヤ（RPCI/IDM/調教師＝Phase 2）／HorseEntryTable は Session 155 で E-005 タグ展開済み確認（既配線）／E-007（jockey close 再集計導線）・E-008（pedigree cutoff 必須化）。

## 2026-06-13 (Session 154 — E-006 鮮度ヘッダ実装)

- **E-006 データ鮮度ヘッダを実装 — 分析画面で coverage.to_date を主役に凍結検知**
  - 動機: ML/分析キャッシュ凍結インシデント（jockey 3ヶ月凍結）は **created_at が新しくても to_date が古い**形で起きた。E-010 で全分析JSONに刻んだ `coverage{from,to}` を画面に出し、再発を表で気づけるようにする。
  - 純ヘルパ `web/src/lib/freshness.ts`: `computeFreshness(to_date, now)` → fresh(<11日)/aging(11-30)/stale(>=31)。**生成時刻でなく被覆末日で判定**。`now` 注入可（テスト可能）。
  - 共通コンポーネント `web/src/components/analysis/FreshnessHeader.tsx`: 鮮度バッジ（色分け+アイコン）+ stale時「⚠集計が古い可能性。再生成を確認」+ 生成日 + schema_version + 任意note。
  - 配線: 3分析画面（`jockey-close-finish` / `slow-start` / `trainer-patterns`＝E-010でcoverage付与済の系）。slow-start には **部分年注意 note**（最新年は季節偏りで年次トレンド比較注意＝stability drift 37%の表示対応）。各JSONで coverage/created_at の位置が違う（top-level vs metadata配下 vs generated_at）ため、ページが明示的に props 渡し。
  - 検証: tsc 自ファイル0エラー（総数5は既存 `.next/types` のみ）。鮮度境界を node 実測＝6/07→fresh(5日)/3/15(凍結日)→**stale(89日)**＝インシデント再発なら赤「要更新」が出る。
  - 残: coverage 未付与の分析（rating/rpci/idm/pedigree_features）は E-010 拡張時にヘッダ追加。HorseEntryTable への E-005 タグ展開も未。

## 2026-06-13 (Session 154 — E-005 表示タグ実装)

- **E-005 理由タグ（接戦◎ / 出遅れ注意 / 低信頼）を実装 — reader→reliable_value→predictions→web の縦串**
  - 方針: E-003/E-004 で「買い目層への新規介入は ROI を動かさない/逆効果」が連続実証されたため、分析シグナルの妥当な居場所＝**表示**。買う/買わない・スコアには一切影響しない純表示メタ。
  - reader: `ml/strategies/slow_start.py`（新規・jockey_ranking quality付き→ci95.lower / horse_stats は rate+N）。`jockey_close.py`(E-003) を接戦◎で再利用。
  - 生成: `ml/strategies/reason_tags.py`（新規・純関数 `build_reason_tags`）。3タグを quality-gate で組み立て。閾値はデータ分布で校正＝**接戦◎** jockey close ci.lower>=0.45(上位22/152騎手)・**出遅れ注意** 馬出遅れ>=30%(総試行N>=4でN過少上振れ排除)/逃げ馬は>=20%/騎手出遅れci.lower>=0.30・**低信頼** 表示タグが小標本(接戦は eff_n のみで判定＝稀少イベントゆえ stability_flag は構造的insufficientになり使わない)。
  - 配線: `predict.py` の result entry に `reason_tags` 付与（`jockey_code`/`ketto_num`/`horse_slow_start_rate`/`avg_first_corner_ratio` を build_reason_tags へ）。map は `_load_reason_tag_maps()` でプロセス内1回ロード。`predictions.append` に jockey_code を追加（接戦タグ用）。
  - web: `predictions-reader.ts` に `ReasonTag` 型 + `reason_tags?`、`vb-table.tsx` の馬名横に `<ReasonTagBadges>`（level別カラー good/caution/warn・低信頼は半透明・detail ツールチップ）。tsc 自ファイル0エラー。
  - テスト: `ml/tests/test_reason_tags.py` 10件green（接戦◎発火/低信頼メタ/出遅れ常習/逃げ馬閾値/騎手出遅れ/空）。strategies系 計57件green。
  - **end-to-end 実証**: `--race-id`/`--date` 再run で predictions.json に reason_tags 着地を確認（race 2026060705030201: close_finish 2(キタノルーズ46%/ビントキナータ47%)+slow_start 5）。jockey_code 配線が close_finish 発火で実証。6/07全日を再生成しタグ付き本番化。
  - 残（follow-up）: races-v2 `HorseEntryTable.tsx`（レース詳細表）への同タグ展開・E-006 鮮度ヘッダと並べる。閾値は config 定数で後調整可。

## 2026-06-13 (Session 154 — E-004 続き)

- **E-004 出遅れフィルタ 分析先行 → 買い目フィルタとして却下（エッジ無し・逆効果確認）**
  - 背景: bet_engine の `horse_slow_start_rate` ペナルティは過去バックテストで逆効果（除外馬の的中率 8.4% > 平均 5%・`bet_engine.py:338` で無効化済）。素朴な減点で実装すると同じ轍 → **実装前に分析先行**（[[feedback_long_term_right_way]] / [[feedback_goal_driven_execution]]）。
  - 手段: `ml/analyze/analyze_slow_start_edge.py`（新規・読み取り専用）。`backtest_cache.json`（結果付き・jockey_code 付き）× `slow_start_analysis.json` jockey_ranking。standard/wide preset の単勝買い目を 馬ss率 / 逃げ馬×ss / 騎手ss率(ci95.lower) / 騎手top3崩壊度 で層別 → 各層の **ROI を bet単位ブートCI** で評価。判定＝負け組の ROI CI上限 < baseline CI下限なら「切るエッジ」。
  - 結果（standard, N=2482, baseline ROI 112.5% CI[86.1,140.7]／wide で再現）:
    - **馬 ss率**: ss_35+(出遅れ常習) ROI **184%** CI[101.7,286.6]＝**最高ROIバケット**。ss_missing(履歴なし若馬) 76% が最低。→ 出遅れ常習を切ると最良の勝ち馬を切る＝逆効果を再確認・むしろ強烈。市場が出遅れ常習を過剰割引＝妙味の源泉。
    - **逃げ馬×ss20+**(プラン崩壊仮説): 82.8% < 115% と方向は正しいが N=200・CI[35.2,138.1] で baseline と**分離せず**＝有意でない。
    - **騎手 ss率 / top3崩壊度**: CI 完全オーバーラップ・エッジ無し。
  - **結論**: 買い目フィルタとしての E-004 は **却下**。出遅れシグナルの妥当な居場所は（あるとすれば）ML特徴量／[[danger-model-project]] だが、買い目層では既に価格に織り込み済みで純損。`slow_start_penalty` は既定 OFF のまま据え置き（コード変更なし）。analyze_slow_start_edge.py を E-004 の採否証跡として保存。
  - 学び: 「常習出遅れ＝危険＝切る」は直感的に正しそうだが**データは真逆**。出遅れ常習馬の高オッズ的中が配当を押し上げ ROI 最良。E-003 と合わせ「**入替/除外が起きること ≠ 収支が良くなること**」が連続で確認された。逃げ馬×ss の理論は方向だけ正しく有意でない＝健全データ蓄積後に再訪候補（実装はしない）。

## 2026-06-13 (Session 154)

- **E-003 接戦タイブレーク 実装done・本番ON採用は見送り（インフラ敷設）**
  - 設計: composite `vb_score` が **同点** のときだけ効く純タイブレーク。買う/買わない判定は変えず、
    `max_win_per_race` で単勝候補が溢れたときの「単勝で残す/複勝に降格」の順序だけを騎手接戦勝率で解消。既定 **OFF**。
  - `reliable_value`=**ci95.lower 採用**（生率0.769でなく下限0.451＝小標本上振れ騎手に軸を奪われない）。E-002 quality_gate を消費する最初の実配線。
  - 実装: `ml/strategies/jockey_close.py`（新規・リーダー+純関数）/ `bet_engine.py`（`enable_close_tiebreak` param・`apply_win_per_race_limit` の `close_lookup` 引数で ON時のみソートキーに `-close_reliable` を dev_gap より先に挿入・`generate_recommendations` の `jockey_close_map` 引数・`df_to_race_predictions` entry に `jockey_code`）/ `experiment.py`（df メタ列 `jockey_code`）。
  - テスト: `ml/tests/test_jockey_close.py` 12件green（同点だけ効く・vb_score差は逆転させない等を固定）。既存 `test_bet_engine.py` の7赤は変化なし＝新規破壊ゼロ。
  - **backtest OFF/ON 比較（v2.3, OOS test 2025-05〜2026-03 / 42,270行 / 2,622R）**:
    - standard 112.5%→112.7%（137→138勝・入替17R）/ wide 111.2%→111.4%（155→156勝・入替18R）/ aggressive 117.1%→**116.8%**（114勝同・入替12R）。
    - その他5preset（max_win=1 or vb_score無効）は入替0。
    - **結論**: タイブレークは確かに発火するが ROI 影響は **ノイズ範囲**（±0.3pt・勝数±1・~25万円ベットに±数百円）・方向混在。**本番ON採用は見送り**＝gap-ROI/CIゲート方針どおり健全データ(6/13+)蓄積後にブートCIで再判定。インフラは敷設済み・既定OFFで本番デフォルト経路はゼロ変化。
  - 学び: 「同点が頻発する＝タイブレークが効く好題材」は正しかったが、**入替が起きること ≠ ROIが動くこと**。同点同士はそもそもモデル評価が拮抗＝期待値も近く、どちらを残しても収支はほぼ同じ。タイブレークの妙味は「将来モデルが同点をもっと作る／接戦シグナルを別の意思決定（相手選択・配分）に使う」局面で。

## 2026-06-12 (Session 152)

- **E-009 検証ハーネス骨格を実装**: `ml/analyze/validate_live_predictions.py`（読み取り専用 / test 7件green）
  - ライブpredictions × T-5直前オッズ × 実払戻を **gap軸 / odds帯軸**で集計（較正乖離・単勝ROI・bet単位ブートCI）
  - predictions の `cache_freshness` メタで劣化/健全を仕分け（`--split-freshness`）
  - 劣化期間(3/21-6/7)実走で人気馬複勝の過小評価（<2.9帯 -0.223）を再現＝Session151 incident(-0.228)と一致＝**正しさ実証**
  - 使い捨て `C:/tmp/diag_live_{v23,w}_bias.py` を吸収（廃止可）
- **前提として** MLキャッシュ鮮度の再発防止3層（検知=predict.py / 監視=keiba-status-check / 検証可能性=predictions の `cache_freshness` メタ）を実装。E-006(鮮度ヘッダ)・E-001(品質メタ)の先行事例
- 残: ハーネスに将来オプション差込口(apply_option)・複勝ROI・walk-forward月別。次の土台＝**E-001 品質メタ標準化**
- **E-001 仕様策定 → シズネ独立レビュー → v1.1**: v1.0 草案 → シズネが実物裏取りレビュー（`E001_review_shizune.md` 🔴4/🟡11/🟢7）→ 全面反映で **v1.1 確定**（quality に metric 必須 / 率×n復元全廃→builder生カウント改修 / IDM=mean_se / prior 指標別・デフォルト禁止 / stability=CIベース判定 / E-002連携節新設）。残=ふくだ確認 Q1(主要metric仮置き)/Q3(E-002減点の主役)
- **jockey_close_finish 凍結解消**: 3/17凍結（MLキャッシュ凍結と同じ「未配線」構造要因）→ 再生成（152騎手・avg close_win_rate 49.1%）+ `keiba-data-prep` ①-2 へ配線
- **E-010 起票**: quality_meta.py ヘルパ + Phase 1 適用

## 2026-06-11

- `202606_analysis_reuse/` フォルダを新設
- 以下の運用ドキュメントを追加
  - `README.md`
  - `01_master_index.md`
  - `02_enhancement_backlog.md`
  - `03_change_log.md`
- 方針:
  - `202606_*.md` 原本は保持
  - 本フォルダで横断統合・実装優先順位・採否基準を育成

