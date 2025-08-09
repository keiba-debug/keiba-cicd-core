# 追加開発計画（バックログ）

- 最終更新: 2025-08-09
- 対象: `keiba-cicd-core/KeibaCICD.keibabook`

---

## P0: 直近優先

1. 高速版 CLI の体裁修正（`src/keibabook/fast_batch_cli.py`）
   - `--max-workers` の引数定義と利用を追加
   - `setup_batch_logger`, `parse_date` など必要関数の import 追加
   - ログ出力と例外処理の整合
   - 成果: `fast_batch_cli` が docs の想定仕様どおり実行可能に

2. OptimizedDataFetcher の参照整備（`src/keibabook/batch/optimized_data_fetcher.py`）
   - `NitteiParser` の import/利用確認
   - `ensure_batch_directories`, `get_json_file_path` の import 明確化
   - 例外ハンドリングとスレッドプールのクリーンアップ

3. 保存パスの完全統一
   - `src/keibabook/main.py` に残る `syutuba/cyokyo/danwa` サブディレクトリ保存ロジックを、`common.get_json_file_path()` 経由に統一
   - 影響範囲: 互換利用のユーザー向けに CHANGELOG/移行注記

---

## P1: ドキュメント整備

1. ドキュメント間の不整合解消
   - 「HTMLを保存しない」方針の注記を最新化
   - Selenium/ChromeDriver 記述はレガシー節に隔離し、高速版中心へ

2. `tools/config_manager.py` の有無整合
   - `docs/keibabook/configuration_guide.md` で参照される `tools/config_manager.py` がリポジトリに存在しない場合、
     - a) 実装を追加する、または
     - b) ドキュメントから参照を削除/代替手順を提示

3. 使い方ガイドの更新
   - 本ドキュメントと `docs/keibabook/how_to_use.md` をハブに

---

## P2: 品質向上

1. テスト整備
   - 最低限のユニット/統合テスト（パーサー：固定サンプルHTML、フェッチャ：モック）
   - CI による Lint/テスト（xUnit, pytest 等）

2. 監視/健全性チェック
   - 簡易ヘルスチェック（ログ/最新ファイルの更新確認）

---

## P3: 機能拡張候補

- 地方競馬対応、オッズデータ、血統詳細（`docs/keibabook/data_specification.md` のロードマップ参照）
- キャッシュ/リトライ拡張、取得結果の差分検出
- WebUI/可視化連携

---

## マイルストーン案

- M1: 高速版CLI最小修正完了（P0-1/2）
- M2: 保存仕様完全統一 + ドキュメント整合（P0-3, P1-1）
- M3: コンフィグ管理の整合（P1-2）
- M4: テスト/CI 導入（P2-1）

---

## 参考
- `docs/keibabook/current_state.md`（現状サマリー）
- `docs/keibabook/api_reference.md`
- `docs/keibabook/data_specification.md`
