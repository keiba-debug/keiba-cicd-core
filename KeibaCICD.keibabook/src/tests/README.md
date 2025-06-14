# テストファイル

このディレクトリには、競馬ブックスクレイピングシステムのテスト用ファイルが含まれています。

## ファイル一覧

### `test_syutuba_parser.py`
修正した出馬表パーサーをテストするスクリプト

**使用方法:**
```bash
# プロジェクトルートから実行
python -m src.keibabook.tests.test_syutuba_parser
```

**機能:**
- 出馬表HTMLファイルのパース
- umacd（馬コード）の抽出確認
- データ検証
- JSON形式での結果保存

## テスト実行の前提条件

- `debug_html/syutuba_202503040101.html`ファイルが存在すること
- 適切な認証情報（.envファイル）が設定されていること

## 出力ファイル

テスト実行後、以下のファイルが生成されます：
- `debug_html/syutuba_202503040101_parsed.json` - パース結果のJSON

## 注意事項

- テストファイルは開発・検証用途のため、本番環境では使用しないでください
- 実際のHTMLファイルを使用するため、ネットワーク接続は不要です 