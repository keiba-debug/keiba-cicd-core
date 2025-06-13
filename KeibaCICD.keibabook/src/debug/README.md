# デバッグツール

このディレクトリには、競馬ブックスクレイピングシステムのデバッグ・分析用ツールが含まれています。

## ファイル一覧

### `debug_syutuba.py`
出馬表ページのHTMLを取得してumacdの構造を分析するデバッグスクリプト

**使用方法:**
```bash
# プロジェクトルートから実行
python -m src.keibabook.debug.debug_syutuba
```

### `debug_nittei.py`
日程ページのHTMLを取得して分析するデバッグスクリプト

**使用方法:**
```bash
# プロジェクトルートから実行
python -m src.keibabook.debug.debug_nittei
```

### `check_race_ids.py`
レースID情報を詳細に分析するスクリプト

**使用方法:**
```bash
# プロジェクトルートから実行
python -m src.keibabook.debug.check_race_ids
```

## 注意事項

- これらのスクリプトは開発・デバッグ用途のため、本番環境では使用しないでください
- 実行前に適切な認証情報（.envファイル）が設定されていることを確認してください
- HTMLファイルの保存先として`debug_html/`ディレクトリが使用されます 