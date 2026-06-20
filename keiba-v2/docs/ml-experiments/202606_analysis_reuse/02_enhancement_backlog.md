# 02. Enhancement Backlog（実装バックログ）

更新ルール:
- Status は `todo / doing / done / hold`
- 完了時は `03_change_log.md` に記録

## Backlog

| ID | Theme | Task | Status | Priority | Done Condition |
|---|---|---|---|---|---|
| E-001 | 共通品質 | 分析JSONに `ci95` / `effective_n` / `stability_flag` を追加する共通仕様を策定 | **done** | High | **v1.2 `E001_quality_meta_spec.md` 確定（Session153・Q1主要metric/Q3減点主役ci95.lower/E-002純化）** |
| E-002 | 買い目補助 | 低信頼データ減点オプションを bet_engine 後段に追加（**純化版＝precision減点のみ・ci95.lower主役。凡走リスクは danger-model別建て**） | **core done** | High | quality_gate純関数done(Session153)・E-003で初の実消費。減点本体はE-004で |
| E-003 | 買い目補助 | `jockey_close_win_rate` を同スコア時タイブレークに適用 | **impl done / ON採用見送り** | High | Session154: 実装+test12green+backtest OFF/ON比較done。ci95.lower採用。**効くが影響ノイズ範囲(±0.3pt/勝数±1)・方向混在→既定OFFでインフラ敷設、健全データ後にブートCI再判定**。詳細は 03_change_log |
| E-004 | 買い目補助 | 出遅れ注意フィルタ（馬 + 騎手）を追加 | **却下（分析先行）** | High | Session154: `analyze_slow_start_edge.py` で gap-ROI/CI 検証。**馬ss率高い馬がROI最良(184%)＝切るのは逆効果**・逃げ馬×ss/騎手シグナルは有意でない。買い目フィルタとして採用せず。詳細は 03_change_log |
| E-005 | UI | レース表に理由タグ（接戦◎/出遅れ注意/低信頼）を表示 | **done** | Mid | Session154: `reason_tags.py`+`slow_start.py`+predict.py配線+vb-table.tsx。Session155: HorseEntryTable(races-v2)展開も完了確認（ml-prediction-reader経由・tsc通過・predictions.json実タグ確認） |
| E-006 | UI | データ鮮度ヘッダ（created_at, source_built_at）を表示 | **done** | Mid | Session154: `freshness.ts`+`FreshnessHeader.tsx`+3画面(jockey-close/slow-start/trainer-patterns)。Session155: 残り4画面(rpci/idm/rating/pedigree)配線完了。**created_atでなくcoverage.to_dateで凍結検知**。遅延ソースにnote |
| E-007 | 導線 | jockey close finish の再集計導線（管理画面 + ページ）追加 | **done** | Mid | Session155: `rebuild_jockey_close`アクション(master再構築→接戦再集計の2段=jockeys.json凍結の根治)+jockey-closeページにRecalcButton。IDM再集計の穴も埋め(`calc_idm_standards`+server用`RecalcRefreshButton`) |
| E-008 | 導線 | pedigree の cutoff 運用を必須化（未指定エラー） | **done** | Mid | Session155: `experiment.py`の血統cutoffリークを WARNING続行→**既定で停止**(未指定/cutoff>=test_start/cutoff付きファイル欠落の黙フォールバック)。明示オプトアウト`--allow-sire-leak`(本番最終学習用)。自動呼び出し元なし=破壊なし |
| E-009 | 検証 | 補助オプション採否を `gap>=k` ROI/CIで判定するテンプレ作成 | **done** | High | Session152骨格+Session155でfollow-up3点完了: ①複勝ROI(確定配当精算+ブートCI・単勝はT-5実行価格と非対称)②walk-forward月別(`--monthly`/`--monthly-gap`で各月持続性=後知恵防止)③apply_option差込口(`OPTION_REGISTRY`+`--option`でbaseline前後比較・danger等は1行登録)。test12green |
| E-010 | 共通品質 | `quality_meta.py` ヘルパ実装 + Phase 1 適用（builder生カウント改修込み） | **done** | High | Session153: 率系5分析(調教師/調教/出遅れ/接戦/血統)。Session155: 連続量3分析(RPCI/IDM/レイティング)に`mean_se`本適用拡張+check_coverage配線(lag_days許容)。pytest35green |

## Phase 2 — danger-model / 運用深化

| ID | Theme | Task | Status | Priority | Done Condition |
|---|---|---|---|---|---|
| E-011 | danger P0 | 現行「危」backtest + 1番人気裏切り要因集計 | **done** | High | `05_danger_model_kickoff.md` + `analyze_favorite_betrayal.py` 実行済（2026-06-20） |
| E-012 | danger P1 | ルールベース `betrayal_score` 試作（1〜2セグメント） | todo | High | P0で n≥80 & 裏切り率+10pt のセグメントからルール化 |
| E-013 | danger 検証 | E-009 `--option opt_danger_v1` 登録・前後比較 | todo | High | 複勝ROI×walk-forward で baseline 上回り |
| E-014 | UI | 現行「危」を過剰人気 vs 凡走リスクにラベル分離 | todo | Mid | HorseEntryTable + reason_tags 系列分離 |
| E-015 | 共通品質 | stability 年別レイヤ（RPCI/IDM/調教師） | todo | Mid | E001 Phase 2 仕様準拠 |
| E-016 | データ | KYI 入厭・降級フラグ調査（danger 特徴量源） | todo | Low | 調査メモ1枚 |

