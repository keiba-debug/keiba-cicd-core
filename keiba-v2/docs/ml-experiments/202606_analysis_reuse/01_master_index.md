# 01. Master Index（202606 横断索引）

## 元レビュー一覧（原本）

- `../202606_rpci_ml_bridge_review.md`
- `../202606_idm_ml_bridge_review.md`
- `../202606_course_dictionary_ml_bridge_review.md`
- `../202606_trainer_patterns_ml_bridge_review.md`
- `../202606_slow_start_ml_bridge_review.md`
- `../202606_pedigree_ml_bridge_review.md`
- `../202606_jockey_close_finish_ml_bridge_review.md`
- `../202606_ml_plus_options_and_race_ui_ideas.md`
- `../202606_lightgbm_market_gap_review.md`

## 再利用テーマ（横断）

1. **最終買い目プラスオプション**
   - 低信頼データ減点
   - 接戦勝率タイブレーク
   - 出遅れ注意シグナル
   - 調教パターン一致加点
2. **レース表の意思決定UI**
   - 理由タグ
   - リスクメーター
   - データ鮮度表示
3. **分析→運用の導線整備**
   - 再集計ボタン追加
   - 品質メタ（CI, n, stability）標準化

## Phase 1 完了サマリー（E-001〜E-010）

- 品質メタ（ci95/effective_n/stability）+ 鮮度ヘッダ + 理由タags + E-009 検証 harness
- E-003 接戦タイブレーク: 実装済・**本番ON見送り**（影響ノイズ範囲）
- E-004 出遅れフィルタ: **却下**（分析先行で逆効果確認）
- 詳細: `02_enhancement_backlog.md` / `03_change_log.md`

## 現在の推奨着手順（Phase 2）

- Step 1: **danger-model P0** — `05_danger_model_kickoff.md` + `analyze_favorite_betrayal.py`
- Step 2: P1 ルール試作 → E-009 `--option` で採否判定
- Step 3: UI「危」ラベル再定義（過剰人気 vs 凡走）
- Step 4: stability 年別レイヤ（RPCI/IDM/調教師）

