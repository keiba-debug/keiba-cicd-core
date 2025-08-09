# 競馬ブック データ取得システム 使い方ガイド

- 最終更新: 2025-08-09
- 対象: `keiba-cicd-core/KeibaCICD.keibabook`

---

## 1. 前提準備

- Python 3.8+
- 依存インストール: `pip install -r requirements.txt`
- Cookie を `.env` に設定（例）:
  ```bash
  KEIBABOOK_SESSION=...
  KEIBABOOK_TK=...
  KEIBABOOK_XSRF_TOKEN=...
  ```
- データ保存先: 既定は `KEIBA_DATA_ROOT_DIR` 直下に統一保存
  - 変更したい場合: `.env` の `KEIBA_DATA_ROOT_DIR` を設定
- 参考: `docs/keibabook/configuration_guide.md`

---

## 2. 推奨の実行方法（安定版 CLI、JSONは `KEIBA_DATA_ROOT_DIR` 直下）

- 従来版 CLI: `python -m src.batch_cli <command> [options]`
- コマンド一覧:
  - `schedule`: レース日程を取得し、`race_ids/YYYYMMDD_info.json` を出力
  - `data`: 既存レースIDを元に `seiseki/shutsuba/cyokyo/danwa` を取得
  - `full`: `schedule` → `data` を一括

### 2.1 単日
```bash
python -m src.batch_cli schedule --start-date 2025/06/07
python -m src.batch_cli data --start-date 2025/06/07 --data-types seiseki
python -m src.batch_cli full --start-date 2025/06/07
```

### 2.2 期間
```bash
python -m src.batch_cli full --start-date 2025/06/01 --end-date 2025/06/07 --delay 5
```

### 2.3 注意
- 保存先は `KEIBA_DATA_ROOT_DIR` 直下（例: `seiseki_YYYYMMDDHHMM.json`）
- 開催がない日はファイルを出力しません（ログに「📭 開催なし」）
- 詳細は `docs/keibabook/data_specification.md` を参照

### 2.4 Windows PowerShell 例
```powershell
Set-Location KeibaCICD.keibabook
$env:KEIBA_DATA_ROOT_DIR = "C:\\keiba_data"
python -m src.batch_cli full --start-date 2025/06/14
```

---

## 3. 高速版（実験的）

- 高速版 CLI: `python -m src.fast_batch_cli <command> [options]`
- 特長: `RequestsScraper` による 10-20倍高速化、並列処理
- 現状: いくつかの小修正が必要（引数・インポート）。順次整備予定
- 使い方（仕様想定）:
```bash
# 日程（高速）
python -m src.fast_batch_cli schedule --start-date 2025/06/07 --delay 0.5

# データ（高速・並列）
python -m src.fast_batch_cli data --start-date 2025/06/07 --data-types seiseki,shutsuba --delay 0.5

# 一括（高速）
python -m src.fast_batch_cli full --start-date 2025/06/01 --end-date 2025/06/07 --delay 0.5
```
- 推奨設定（目安）: `delay=0.5~1.0`, `max-workers=5~12`

---

## 4. Windows/WSL 補足

- PowerShell スクリプト（例）: `scripts/daily_batch_v2.ps1`
  - 全処理: `.	ools\daily_batch_v2.ps1 -Date "2025/06/07" -Mode "full"`
- WSL 環境では `python` 実行時のパスや `.env` 設置位置に注意

---

## 5. ログ・デバッグ

- ログ出力先: `logs/`
- デバッグ実行: `--debug` を付与
- よくあるエラーと対処: `docs/keibabook/troubleshooting.md`

---

## 6. よくある質問

- Q: JSONはどこに出力されますか？
  - A: 既定では `KEIBA_DATA_ROOT_DIR` 直下。`.env` の `KEIBA_DATA_ROOT_DIR` で制御します。
- Q: 開催がない日は？
  - A: JSONは出力されません。ログに「📭 開催なし」と記録されます。

---

## 7. 参考
- `docs/keibabook/api_reference.md`
- `docs/keibabook/data_specification.md`
- `docs/keibabook/setup_guide.md`
- `docs/keibabook/configuration_guide.md`
