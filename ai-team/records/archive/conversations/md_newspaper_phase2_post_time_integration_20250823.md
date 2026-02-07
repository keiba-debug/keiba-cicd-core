# MD新聞ヘッダー改善 Phase2: 発走時刻(post_time)統合 指示（2025-08-23）

## 背景・目的
- 改修完了報告にて、ヘッダー拡張（競馬場/レース番号/コース/距離/レース名/クラス）は実装済み。
- ただし post_time（発走予定時刻）は integrated JSON に未収録のため、ヘッダー・レース情報に反映されていない。
- 本フェーズで post_time を取得→統合→出力まで一気通貫に対応し、ヘッダーから発走時刻が把握できる状態にする。

---

## スコープ
1) 取得: nittei 等の日程ソースから各レースの post_time（HH:MM, JST）を取得可能にする。
2) 統合: `integrator_cli` で integrated JSON に `race_info.post_time` を追加・反映。
3) 出力: `markdown_cli` 出力（MD新聞）で以下を満たす：
   - H1 見出し末尾に `発走予定 HH:MM` を付与（post_time が存在する場合）
   - 「📋 レース情報」セクションに **発走予定時刻** を追加（post_time が存在する場合）
4) 再生成: 8/23・8/24 の全レース MD を再生成して成果を確認。

---

## 要件（必須）
- 形式: `race_info.post_time` は 24h 表記 `HH:MM`（例: `15:35`）
- タイムゾーン: JST 固定
- ヘッダー例（post_time あり）:
  - `# 札幌11R 芝 2000m 札幌記念(G2)  発走予定 15:35`
- ヘッダー例（post_time なし）:
  - `# 札幌11R 芝 2000m 札幌記念(G2)`（末尾の発走予定は省略）
- 後方互換性: 既存の表やMermaidなどの構造・表示を崩さない。

---

## 実装対象と方針
### 1. スクレイピング/パーサ（取得）
- 対象: `src/keibabook/scrapers/*` または日程取得ルート
- 推奨ソース: nittei（日程）ページ or レース個別ページの時刻要素
- 実装指針:
  - 正規表現で `HH:MM` 抽出（`([01]?\d|2[0-3]):[0-5]\d`）
  - 全角→半角、`H:MM`→`HH:MM` へゼロ埋め整形
  - 取得不可時は None を返却（無理な補完は行わない）

### 2. 統合処理（integrator_cli）
- 入力: 取得済 post_time（nittei/shutsuba 等）
- マージ: `race_info.post_time` を integrated JSON に保存
- 優先度: `explicit(post_time)` > `nittei` > `shutsuba` > `None`
- バリデーション: フォーマット不一致はログ警告 + 無視

### 3. 生成処理（markdown_cli）
- 現状: ヘッダー拡張は済。post_time があれば H1 末尾に `発走予定 HH:MM` を追加
- レース情報セクション: `**発走予定時刻**: HH:MM` を追記（存在時のみ）
- 欠損時は非表示（ヘッダー/本文とも）

---

## 受け入れ基準（AC）
1. AC1: integrated JSON に `race_info.post_time`（`HH:MM`）が格納される
2. AC2: post_time があるレースは H1 見出し末尾に `発走予定 HH:MM` が表示される
3. AC3: 「📋 レース情報」に **発走予定時刻** が表示される（post_time あり時）
4. AC4: post_time 欠損のレースは表示省略で体裁崩れなし
5. AC5: 8/23・8/24 の全レース MD 再生成でエラー無し、目視で代表例が要件を満たす

---

## テスト計画
- ユニットテスト:
  - パーサ: 生テキスト/HTML から `HH:MM` 抽出・整形のテスト
  - バリデーション: 不正値（例: `25:90`）は None にする
- 統合テスト:
  - `integrator_cli` で post_time マージ後の integrated JSON を検証
- E2E（手動）:
  - `markdown_cli single`/`batch` 両方で post_time の有無ケースを確認
  - G レース/特別/条件戦/新馬/未勝利を各1例確認

---

## 実施手順（コマンド例: PowerShell）
```powershell
# 1) 取得（必要に応じて backfill オプションを追加）
python -m src.fast_batch_cli data --start 2025/08/23 --end 2025/08/24 --data-types nittei --delay 0.5 --max-workers 8

# 2) 統合（post_time 反映）
python -m src.integrator_cli batch --start-date 2025/08/23 --end-date 2025/08/24

# 3) 再生成（MD新聞）
python -m src.markdown_cli batch --date 2025/08/23 --organized
python -m src.markdown_cli batch --date 2025/08/24 --organized
```

---

## トラブルシューティング
- 取得不可（ページ仕様変更/要素欠損）: CSS/XPath/正規表現の再調整、フォールバック導線（別ページ）を追加
- 曖昧フォーマット（例: `9:5`）: 正規化して `09:05` に整形
- レート制限: `--delay` 上げる、ワーカー数調整

---

## スケジュール目安
- 実装: 2〜4h（取得1.5h / 統合1h / 出力0.5h）
- テスト/再生成: 1〜2h

---

## 連絡事項
- 既存ヘッダー拡張を前提に post_time を“追加”するのみ。既存表示の削除・変更は行わない。
- 仕様差分は本ドキュメントに追記の上で合意形成してから実装に反映してください。
