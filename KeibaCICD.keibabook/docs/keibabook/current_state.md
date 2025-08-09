# 競馬ブック データ取得システム 現状仕様サマリー（暫定）

- 最終確認日: 2025-08-09
- 対象ディレクトリ: `keiba-cicd-core/KeibaCICD.keibabook/`
- 参照ルール: keiba-cicd-core/dev-rules/db-blueprint ✅ / .cursor/rules/basic/pmbok_paths.mdc ✅ / .cursor/rules/basic/00_master_rules.mdc ✅

---

## 1. 現状の全体像

- 目的: 競馬ブック (`https://p.keibabook.co.jp`) からレース日程・成績・出馬表・調教・厩舎の話を取得し、JSONとして保存
- 実装構成（主要）:
  - `src/keibabook/batch/` バッチ処理（従来版 + 最適化版）
    - `core/common.py`: 共通（ログ、ディレクトリ、Cookie付与セッション、統計）
    - `data_fetcher.py`: 従来版フェッチャ（逐次型）
    - `optimized_data_fetcher.py`: 高速版フェッチャ（requests + 並列）
  - `src/keibabook/scrapers/`
    - `requests_scraper.py`: 軽量HTTPスクレイパ（Cookie直付与）
    - `keibabook_scraper.py`: Selenium版（レガシー）
    - `legacy_scrapers.py`: 旧ユースケース/モデル群
  - `src/keibabook/parsers/`: 各ページをJSONへ変換（`seiseki/syutuba/cyokyo/danwa/nittei`）
  - CLI:
    - `batch_cli.py`: 従来版統合CLI（実運用向け）
    - `fast_batch_cli.py`: 高速版CLI（現状 未完のため要整備）
  - 補助: `utils/config.py`（環境変数/ディレクトリ/Cookie定義）, `utils/logger.py`

---

## 2. 保存仕様（実装の実態）

- 保存形式: JSONのみ（HTMLは原則保存しない。パース都合で一時ファイル利用箇所有り）
- 保存場所（実装基準）:
  - `core/common.py` の `get_json_file_path(data_type, identifier)` により、原則 `KEIBA_DATA_ROOT_DIR` 直下へ統一保存
  - レースID情報: `$KEIBA_DATA_ROOT_DIR/race_ids/YYYYMMDD_info.json`
  - 命名規則: `{data_type}_{race_id or date}.json`
- ドキュメントの表記と実装差分:
  - ドキュメント(v2.2/v2.3)は「全JSONを `data/keibabook/` 直下へ統一」→ `data_fetcher.py` / `optimized_data_fetcher.py` はこの方針に一致
  - ただし `main.py` 内の一部保存処理は、`syutuba/cyokyo/danwa` のサブフォルダを掘るコードが残存（レガシー）。当面は `batch_cli.py` 系の利用を推奨

---

## 3. 認証・セッション

- 方式: Cookie直付与（`KEIBABOOK_SESSION`, `KEIBABOOK_TK`, `KEIBABOOK_XSRF_TOKEN`）
- 定義: `utils/config.py::get_required_cookies()`
- 付与箇所:
  - `batch/core/common.py::create_authenticated_session()`（従来系）
  - `scrapers/requests_scraper.py::_setup_cookies()`（高速系）
- 備考: `src/auth.py` にログイン補助クラスあり（Cookie運用が前提のため、通常は未使用）

---

## 4. CLIの現状

- 従来版 CLI: `python -m src.keibabook.batch_cli <schedule|data|full> ...`
  - 稼働前提となる実装。`DataFetcher` を利用し、`common.get_json_file_path` で統一保存
- 高速版 CLI: `python -m src.keibabook.fast_batch_cli <schedule|data|full> ...`
  - `OptimizedDataFetcher` を呼び出す設計。docs は v2.3 推奨として記載
  - 現状のコード上の未整備点（例）:
    - `--max-workers` 引数の定義漏れ/参照不整合
    - `setup_batch_logger`, `parse_date` 等の未インポート
    - `OptimizedDataFetcher` 側でも `NitteiParser` import・参照の整合性確認が必要
  - 結論: 高速版CLIは微修正が複数必要。先に従来版で安定運用→高速版を段階導入が安全

---

## 5. 主要コンポーネントの役割

- `DataFetcher`（従来）
  - 機能: 日程取得→レースID→各データタイプ取得→JSON保存
  - 保存: `common.get_json_file_path` で `KEIBA_DATA_ROOT_DIR` 直下
- `OptimizedDataFetcher`（高速）
  - 機能: `RequestsScraper` によるHTTP直取得 + 並列処理
  - 保存: 同上。HTML一時ファイルを極力回避
- `Parsers`（`seiseki/syutuba/cyokyo/danwa/nittei`）
  - BeautifulSoupベースのテーブル/ブロック抽出→JSON整形→簡易バリデーション
- `RequestsScraper`
  - Cookie直付与のHTTPアクセス。タイムアウト/簡易検証/任意保存

---

## 6. 環境変数/ディレクトリ

- 主な環境変数（`utils/config.py`）:
  - `KEIBA_DATA_ROOT_DIR` / `KEIBA_DATA_DIR` / `KEIBA_KEIBABOOK_DIR` / `KEIBA_DEBUG_DIR` / `KEIBA_LOG_DIR`
  - Cookie: `KEIBABOOK_SESSION`, `KEIBABOOK_TK`, `KEIBABOOK_XSRF_TOKEN`
- ディレクトリ作成:
  - `utils/config.py::ensure_directories()` または `batch/core/common.py::ensure_batch_directories()`

---

## 7. 既知の不整合・改善候補（優先度順）

1) 高速版CLIの体裁不整合
- `fast_batch_cli.py` の引数・インポート修正、ログ設定の整合、例外処理
- `OptimizedDataFetcher` からの `NitteiParser` 参照/取込の整備

2) レガシー保存パスの残存
- `main.py` の `syutuba/cyokyo/danwa` サブフォルダ保存コードを廃止
- ドキュメントの「統一フォルダ保存」と実装の完全一致

3) トラブルシュート/セットアップ文書の一部レガシー表記
- Selenium/ChromeDriverの記述が残る箇所の注記強化（高速系は不使用）

4) 自動テスト/検証
- 最低限の統合テスト（擬似HTML/Mock）と Lint 設定の確認

---

## 8. 当面の推奨運用

- 実運用: 従来版CLI（`batch_cli.py`）を使用
  - 例: `python -m src.keibabook.batch_cli full --start-date YYYY/MM/DD`
- 高速化ニーズ: 別ブランチで `fast_batch_cli` 修正→段階導入
- ディレクトリ: `.env` の `KEIBA_DATA_ROOT_DIR` を設定し、単一フォルダ保存を徹底（`KEIBA_KEIBABOOK_DIR` は非推奨）

---

## 9. 参考ドキュメント（既存）

- `docs/keibabook/api_reference.md`（v2.3 記述あり・高速版CLIの想定仕様）
- `docs/keibabook/data_specification.md`（保存仕様・命名規則）
- `docs/keibabook/configuration_guide.md`（環境変数と生成/確認ツール）
- `docs/keibabook/setup_guide.md`, `docs/keibabook/troubleshooting.md`

---

## 10. 次のステップ（提案）

- Step A: 高速版CLIの最小修正（引数/インポート/ロギングの整合）
- Step B: `main.py` の保存パスを統一APIへ移行（`get_json_file_path`）
- Step C: ドキュメント整合性の再確認（「HTMLを保存しない」注記の最新化）
- Step D: 簡易自動テスト + Lint を追加

必要に応じ、上記をタスク分割して着手します。
