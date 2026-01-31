# オッズ表示機能 調査・設計書

**作成日**: 2026-01-31  
**目的**: KeibaCICD.WebViewer / KeibaCICD.TARGET でオッズを表示・参照し、AIチームとオッズゆがみ分析や株ボード風確認画面を実現するための設計

---

## 1. 調査サマリー

### 1.1 オッズデータソース一覧

| ソース | 場所 | 形式 | タイミング | 取得方法 |
|--------|------|------|------------|----------|
| **RT_DATA** | `E:\TFJV\RT_DATA\{年}\{MMDD}\` | RT*.DAT (固定長) | 当日リアルタイム | TARGET frontier JV 自動取得 |
| **HY_DATA** | `E:\TFJV\HY_DATA\{年}\` | HY*.DAT | レース後確定 | JRA-VAN 蓄積系 |
| **ODDS** (未整備) | `{JV_ROOT}/ODDS/` | O1_*.txt, O2_*.txt | 手動/JV-Link | JV-Link DIFF O1,O2 |
| **SE_DATA** | `E:\TFJV\SE_DATA\{年}\` | SR*.DAT | レース後 | 着順・単勝オッズ(結果)含む |

### 1.2 RT_DATA の実態

**フォルダ構造**
```
E:\TFJV\RT_DATA\
├── 2026\
│   ├── 0131\                    # MMDD
│   │   ├── RT20260131050101011.DAT   # 東京1R 1番
│   │   ├── RT20260131050101012.DAT   # 東京1R 2番
│   │   └── RT20260131100103061.DAT   # 中山3R 6番 等
│   └── ...
├── JI_2026\                     # 時系列オッズ（馬連・馬単）
│   └── 0131\                    # MMDD
│       ├── JT2026013105010101.DAT    # 馬単 東京1R (時系列)
│       ├── JT2026013105010102.DAT    # 馬単 東京2R
│       ├── JU2026013105010101.DAT    # 馬連 東京1R (時系列)
│       └── ...
├── TEMP\                        # BT*.DAT, DM*.DAT (作業用)
└── ...
```

**ファイル命名規則** (推定)
- `RT{raceId}{馬番}.DAT` … 単複枠（O1）。1レースあたり馬番数分のファイル
- `JT{raceId}.DAT` … 馬単（O4）時系列オッズ
- `JU{raceId}.DAT` … 馬連（O2）時系列オッズ

**データ内容**
- **RT*.DAT**: 固定長テキスト、O1 レコード（単勝・複勝・枠連）。オッズ再取得後は O2/O4 等を含む可能性あり
- **JT/JU**: 馬単・馬連の時系列スナップショット（時刻別オッズ変動）

### 1.3 HY_DATA（票数・オッズ）

- **H1**〜**H6**: 単複枠、馬連、ワイド、馬単、3連複、3連単
- ファイル例: `HY1202616.DAT`, `HY2202616.DAT` 等
- 蓄積系: レース後の確定オッズ
- リアルタイム表示には不向き（当日締切前の「今のオッズ」ではない）

### 1.4 既存実装の状態

| コンポーネント | オッズ対応 | 備考 |
|----------------|------------|------|
| **OddsManager** (TARGET) | △ 未接続 | `{JV_ROOT}/ODDS/` を参照するが E:\TFJV に ODDS なし |
| **WebViewer** | △ 型定義のみ | `単勝オッズ` 列あり、race_info.json の列から取得 |
| **evaluator** | ○ オッズ入力想定 | 期待値計算でオッズを引数に受け取る |

---

## 2. データ取得方針の比較

### 2.1 選択肢

| 方式 | メリット | デメリット | 実装難易度 |
|------|----------|------------|------------|
| **A. RT_DATA 直接参照** | 既に取得済み、追加取得不要 | フォーマット解析必要、TARGET frontier JV 依存 | 中 |
| **B. JV-Link DIFF (O1,O2)** | 仕様明確、時刻別スナップショット取得可 | スクリプト・スケジュール設定が必要、ODDS フォルダ整備 | 中 |
| **C. DB 化** | クエリ高速、時系列分析容易 | 初期構築・パイプライン必要 | 高 |

### 2.2 推奨: 段階的アプローチ

```
Phase 1（短期）: RT_DATA 直接参照
  - E:\TFJV\RT_DATA をそのまま利用
  - パーサー実装で「今あるデータ」からオッズ抽出
  - WebViewer にオッズ表示・API 追加

Phase 2（中期）: ODDS フォルダ整備 + JV-Link
  - JV-Link で O1, O2 を定期取得
  - OddsManager を E:\TFJV\ODDS に接続
  - 朝オッズ・締切前オッズのスナップショット保存

Phase 3（長期）: DB 化検討
  - オッズ変動分析・AI チーム連携が本格化したら
  - SQLite 等で軽量 DB、履歴分析用
```

---

## 3. 直接ファイル参照の可否

### 3.1 RT_DATA を直接利用できるか

**結論: 利用可能（要パーサー実装）**

- **場所**: `E:\TFJV\RT_DATA` は既に存在し、当日レースの速報が格納されている
- **アクセス**: TARGET / WebViewer ともに `JV_DATA_ROOT_DIR` 経由で参照可能
- **課題**:
  1. RT_DATA の固定長フォーマット仕様の確定（JV-Data仕様書_4.9.0.1 要確認）
  2. BT/DM 等のレコード種別と RT の対応関係
  3. TEMP と本番フォルダの役割

### 3.2 DB 化が必要か

**現時点では不要**

- 株ボード風「今のオッズ」表示 → ファイル直接参照で十分
- オッズ変動の時系列分析 → Phase 2 で ODDS スナップショットを蓄積してから検討
- 重い集計・バックテスト → 将来 DB 化を検討

---

## 4. 設計案

### 4.1 アーキテクチャ概要

```
[データソース]
  E:\TFJV\RT_DATA      → RT_DATA パーサー
  (将来) E:\TFJV\ODDS  → OddsManager (既存)

[TARGET]
  common/rt_data.py    ← 新規: RT_DATA パーサー
  OddsManager          ← 修正: RT_DATA / ODDS 両対応

[WebViewer]
  /api/odds/[raceId]   ← 新規: オッズ取得 API
  /odds-board          ← 新規: 株ボード風オッズ画面
  レース詳細ページ      ← 既存: オッズ列を RT/ODDS 由来に差し替え
```

### 4.2 オッズ API 設計

```
GET /api/odds/race?date=2026-01-31&track=東京&raceNumber=1

Response:
{
  "raceId": "2026013105010101",
  "source": "RT_DATA",
  "updatedAt": "2026-01-31T10:05:00",
  "horses": [
    { "umaban": "1", "winOdds": 5.2, "placeOddsMin": 2.1, "placeOddsMax": 2.8, "ninki": 1 },
    ...
  ]
}
```

### 4.3 株ボード風 UI イメージ

- **レース一覧**: 日付・競馬場・レース番号でフィルタ
- **オッズテーブル**: 馬番 | 馬名 | 単勝 | 複勝 | 人気 | 変動
- **更新**: 手動更新ボタン or 一定間隔ポーリング
- **AI 連携**: オッズゆがみ検出結果をバッジや注釈で表示（将来）

---

## 5. 次のアクション

### 5.1 即時実施（調査継続）

1. **RT_DATA フォーマット確定**
   - JV-Data仕様書_4.9.0.1.xlsx / PDF で RT, BT, DM レコード仕様を確認
   - サンプルファイル数件をパースして検証

2. **ODDS フォルダ有無の確認**
   - `E:\TFJV\ODDS` を作成するか、既存の別パスを使うか決定
   - OddsManager の `jv_data_root` を `E:\TFJV` に統一済みか確認

### 5.2 Phase 1 実装タスク

| # | タスク | 担当 |
|---|--------|------|
| 1 | RT_DATA パーサー (common/rt_data.py) | TARGET |
| 2 | オッズ取得 API (/api/odds/race) | WebViewer |
| 3 | レース詳細のオッズ列を API 連携に変更 | WebViewer |
| 4 | 株ボード風オッズ画面 (/odds-board) | WebViewer |
| 5 | config.py に get_jv_rt_data_path() 追加 | TARGET |

### 5.3 JV-Link 経由取得（Phase 2）

- `JVLink.exe -dataspec "DIFF O1 O2"` で O1, O2 取得
- 取得先を `E:\TFJV\ODDS\` に統一
- タスクスケジューラで締切前に自動取得
- 参照: `ml/docs/ODDS_MANAGEMENT.md`

### 5.4 追加データソース（2026-01 確認済み）

#### 馬連・馬単の利用可能性
- オッズ再ダウンロード後、RT_DATA 内に **O2（馬連）・O4（馬単）** レコードが含まれる可能性あり
- JVData_Struct.cs の `JV_O2_ODDS_UMAREN`、`JV_O4_ODDS_UMATAN` を参照
- RT*.DAT に複数レコード種別（O1/O2/O4）が連結されている場合のパース対応を検討

#### 時系列オッズ（JI_2026）
- **場所**: `E:\TFJV\RT_DATA\JI_2026\{MMDD}\`
- **形式**: `JT{raceId}.DAT`（馬単）、`JU{raceId}.DAT`（馬連）
- **構造**: **1 ファイル = 1 レース、1 行 = 1 時点のスナップショット**（約 180 行以上/レース）
- **用途例**:
  - オッズ変動の時系列分析
  - 締切直前 vs 朝オッズの比較
  - **特定時刻への巻き戻し**（タイムスライダー）
  - AI チームによるオッズゆがみ・急変検出

---

## 6. 参考資料

- [ODDS_MANAGEMENT.md](../KeibaCICD.TARGET/ml/docs/ODDS_MANAGEMENT.md) - オッズ管理ガイド
- [TARGET_DATA_構造一覧.md](../KeibaCICD.TARGET/docs/TARGET_DATA_構造一覧.md) - JV データ構造
- [JVData_Struct.cs](../../JRA-VAN%20Data%20Lab.%20SDK%20Ver4.9.0.2/JV-Data構造体/C%23版/JVData_Struct.cs) - O1/H1 等オッズ構造体
- JV-Data仕様書_4.9.0.1.xlsx - RT_DATA 詳細仕様（要確認）

---

*最終更新: 2026-01-31*

---

## 7. データ構造メモ（JVData_Struct.cs より）

| レコード | 構造体 | 内容 |
|----------|--------|------|
| O1 | JV_O1_ODDS_TANFUKUWAKU | 単勝・複勝・枠連 |
| O2 | JV_O2_ODDS_UMAREN | 馬連（153組） |
| O3 | JV_O3_ODDS_WIDE | ワイド（153組） |
| O4 | JV_O4_ODDS_UMATAN | 馬単（306組） |
