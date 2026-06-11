# 02. Enhancement Backlog（実装バックログ）

更新ルール:
- Status は `todo / doing / done / hold`
- 完了時は `03_change_log.md` に記録

## Backlog

| ID | Theme | Task | Status | Priority | Done Condition |
|---|---|---|---|---|---|
| E-001 | 共通品質 | 分析JSONに `ci95` / `effective_n` / `stability_flag` を追加する共通仕様を策定 | todo | High | 仕様書1枚 + 対象ファイル一覧 |
| E-002 | 買い目補助 | 低信頼データ減点オプションを bet_engine 後段に追加 | todo | High | ON/OFF比較ログで差分確認 |
| E-003 | 買い目補助 | `jockey_close_win_rate` を同スコア時タイブレークに適用 | todo | High | 同日レースで順位差分を可視化 |
| E-004 | 買い目補助 | 出遅れ注意フィルタ（馬 + 騎手）を追加 | todo | High | `gap>=k` 条件で ROI/CI比較 |
| E-005 | UI | レース表に理由タグ（接戦◎/出遅れ注意/低信頼）を表示 | todo | Mid | 主要タグ3種が表示される |
| E-006 | UI | データ鮮度ヘッダ（created_at, source_built_at）を表示 | todo | Mid | 各分析画面で鮮度が確認可能 |
| E-007 | 導線 | jockey close finish の再集計導線（管理画面 + ページ）追加 | todo | Mid | ボタン1回でJSON再生成可能 |
| E-008 | 導線 | pedigree の cutoff 運用を必須化（未指定エラー） | todo | Mid | 実験時に未指定で停止する |
| E-009 | 検証 | 補助オプション採否を `gap>=k` ROI/CIで判定するテンプレ作成 | todo | High | 評価テンプレ1本化 |

