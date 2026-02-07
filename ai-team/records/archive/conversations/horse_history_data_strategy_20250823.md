# 馬の過去走データ取得・蓄積戦略（2025-08-23）

## 背景・目的
- MD新聞の改善案（脚質適合、ラップ適性、割安検出 等）の多くは「過去走履歴」に依存。
- 信頼できる履歴データの継続蓄積（蓄積系）を整備し、的中率・回収率向上に直結させる。

## 必要な過去走数（目安）
- 脚質/ラップ適性: 3〜5走（直近の傾向重視）
- コース/距離/馬場適性: 5〜10走（サンプル確保）
- 馬体重トレンド: 5走
- 安定評価・学習用途: 10〜12走

---

## 選択肢と比較
### 1) 自前バックフィル（organized/seiseki から遡及）
- 概要: 既存の `Z:/KEIBA-CICD/data/organized/**/seiseki_*.json` を走査し、同一馬IDで過去走を集約
- 長所: すぐ着手可、コストなし、ライセンスクリア
- 短所: カバレッジに欠落（過去期間が無いと拾えない）、完全性は保証できない
- 適用: Phase 1（直近3走のカバーに最適）

### 2) JRA-VAN 蓄積系を正式参照（Data Lab）
- 概要: JRA-VAN公式の蓄積系データをSDKで取得して正規化・保存
- 長所: 網羅性・鮮度・正確性が高い、公式ID体系
- 短所: 実装工数、API/ライセンス順守、安定運用の考慮が必要
- 適用: Phase 2（本命。10〜12走を高品質に）

### 3) TARGET データ参照（CSV/DB エクスポート）
- 概要: TARGETのエクスポートを定期取込
- 長所: 実務上の網羅性・加工の柔軟性
- 短所: エクスポート前提/手順依存、ライセンス配慮、整合性管理が必要
- 適用: Phase 3（補完オプション）

---

## 推奨アプローチ（段階導入）
- Phase 1（今週）: 自前バックフィルで各馬「直近3走」を確保
  - integrator_cli が `shutsuba` の馬リストから、organized配下の `seiseki_*.json` を走査
  - 取得できた履歴から簡易特徴量（上り3F平均、通過傾向、距離/コース成績）を算出
  - MD新聞に「脚質適合/調教指数/割安タグ」等、3項目を先行反映
- Phase 2（来週〜）: JRA-VANアダプタで「10〜12走」を公式に蓄積
  - horseId/JVIDマッピング、正規化スキーマ、差分更新、キャッシュを実装
  - 週末対象馬のみ前日夜間にプリフェッチ
- Phase 3（必要時）: TARGETインポータ（CSV）で補完

---

## 蓄積スキーマ案（JSON）
- 保存先: `Z:/KEIBA-CICD/data/accumulated/horses/{horse_id}.json`
- 構造（例）
```json
{
  "horse_id": "2018101234",
  "jra_van_ids": { "horse": "JVID_HORSE" },
  "updated_at": "2025-08-23T09:00:00+09:00",
  "history": [
    {
      "race_id": "202503020811",
      "date": "2025-08-17",
      "venue": "札幌",
      "surface": "芝",
      "distance_m": 2000,
      "going": "良",
      "time": "2:01.5",
      "last3f": 34.8,
      "passing_orders": [3,3,3,2],
      "final_corner_position": 2,
      "jockey": "横山典",
      "weight_carried": 57.0,
      "body_weight": 486,
      "body_weight_diff": -2,
      "odds": 25.6,
      "finish_position": 1
    }
  ],
  "features": {
    "last3f_mean_3": 35.1,
    "pace_type": "瞬発",
    "course_distance_perf": { "札幌-芝2000": { "runs": 3, "win": 1, "in3": 2 } },
    "recency_days": 28
  }
}
```

---

## フロー/コンポーネント
- 取得
  - Phase 1: `history_backfill`（organizedスキャン）
  - Phase 2: `jravan_adapter`（SDK）/ `target_adapter`（CSV）
- 蓄積
  - `accumulator_cli`：`horse-history fetch --date 2025/08/23 --source organized|jravan|target --runs 3|10`
- 統合
  - `integrator_cli`：`race_info.horses[].history_features` を付与
- 生成
  - `markdown_cli`：出走表に簡易指標列、展開セクションに適合サマリを追加

---

## 実装タスク（Phase 1）
1) accumulator_cli（organizedバックフィル）を実装（直近3走）
2) integrator_cli で `history_features` を各馬にマージ
3) markdown_cli に「適性/割安」列を追加（表示のみ）
4) 週末一括コマンドに backfill ステップを追加

## 実装タスク（Phase 2）
1) jravan_adapter で 10〜12走取得（JVIDマッピング/正規化）
2) 差分更新・キャッシュ（既存JSONへupsert）
3) 前日夜間バッチ（対象馬プリフェッチ）

---

## 受入基準
- Phase 1: 直近3走の特徴量が MD新聞に表示され、表示崩れなし。生成時間の増分が許容範囲（+5%以内）。
- Phase 2: 10〜12走の履歴蓄積が安定運用され、週末対象馬の事前取得が成功。MDの精度指標（上位EV回収）向上。

## リスク・配慮
- ライセンス順守（JRA-VAN/TARGET）
- ID正規化と同名馬対策
- 欠損値の安全処理（表示は寛容、学習は厳格）
