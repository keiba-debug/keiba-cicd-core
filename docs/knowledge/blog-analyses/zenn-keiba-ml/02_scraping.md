# 02. スクレイピング

> 出典: Zenn「競馬予想で始める機械学習〜完全版〜」Ch.02

---

## 取得する4種類のデータ

| データ | メソッド | 内容 |
|--------|---------|------|
| レース結果 | `Results.scrape()` | netkeiba.comのレース結果ページ（着順・タイム等） |
| 馬の過去成績 | `HorseResults.scrape()` | 馬個別ページの全出走履歴 |
| 血統データ | `Peds.scrape()` | 5世代分（62頭）の血統テーブル |
| 払い戻し表 | `Return.scrape()` | 単勝〜三連単の払い戻し金額 |

## 技術的な手法

- **`pd.read_html(url)`** でtableタグを一発取得（netkeiba.comはtableタグ構造）
- 保存は **pickle形式**（`DataFrame.to_pickle()`）
- スクレイピング間隔: `time.sleep(1)` → 2024/11以降は2〜3秒推奨
- 2024/11のnetkeiba仕様変更で **User-Agent必須** に（ランダム選択で対応）

## race_idの構造

```
"2019" + place(2桁) + kai(2桁) + day(2桁) + r(2桁)
→ 例: 201901010101
```
- place: 1〜10（10場）、kai: 1〜6、day: 1〜12、r: 1〜12
- 全組み合わせを生成して存在しないIDはスキップする方式

## 払い戻し表の注意点

- `<br />`タグが消えて複勝・ワイドのデータが結合してしまう問題
- 対策: `html.replace(b'<br />', b'br')` で改行タグを文字列に変換後にパース

## データ更新ロジック

```python
def update_data(old, new):
    filtered_old = old[~old.index.isin(new.index)]
    return pd.concat([filtered_old, new])
```
- 重複するindexは新しいデータで上書き、それ以外は古いデータを保持

---

## KeibaCICDとの比較

| 項目 | この書籍 | KeibaCICD |
|------|---------|-----------|
| データソース | netkeiba.com（HTML scraping） | JRA-VAN（バイナリ直読） |
| レースID | 10桁 `YYYYppkkddrr` | 16桁 `YYYYMMDDJJKKNNRR` |
| 馬ID | netkeiba独自ID | 10桁 ketto_num |
| 血統 | 5世代62頭テーブル | **未実装**（A-0で予定） |
| 払い戻し | スクレイピング | odds_db.py（JRA-VAN） |
| 保存形式 | pickle | JSON |
| 更新方式 | update_data(old, new) | ビルダーで全件再構築 |

## 参考になるポイント

1. **血統5世代62頭** — うちのA-0（血統特徴量）実装時に参照できる。5世代分をどう特徴量化するかは次章以降で確認したい
2. **race_idの全組み合わせ生成** — 存在しないIDはスキップする力技。うちはJRA-VANのDB走査なのでこの問題なし
3. **データ更新のindex重複排除** — シンプルだが実用的なパターン。うちは全件再ビルドなので不要だが、差分更新時には参考になる

## 次章で確認したいこと

- データ加工（前処理）の具体的手法
- 特徴量としてどの列を使うか
- 血統データの特徴量変換方法
