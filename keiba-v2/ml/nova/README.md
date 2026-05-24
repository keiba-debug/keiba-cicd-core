# ml/nova/

新馬・1勝クラス専用の **スペシャリストモデル群**。 polaris 2.0 の苦手領域 (rank_p Top1 ROI 76–83%) を救うのが目的。

設計書: [`../../docs/projects/nova_specialist_v0.md`](../../docs/projects/nova_specialist_v0.md)

## サブモデル

| 名称 | 対象 grade | 状態 |
|---|---|---|
| `nova_emerging` | 1勝クラス (653 bets/年) | **Phase 1 着手中** |
| `nova_debut` | 新馬 (576 bets/年) | Phase 2 (未着手) |

## ファイル

| ファイル | 役割 |
|---|---|
| `train_emerging.py` | 1勝クラス特化 P モデルの学習 (polaris と同じ FEATURE_COLS_ALL / PARAMS_P で grade フィルタのみ) |
| (将来) `train_debut.py` | 新馬特化 P モデルの学習 (過去走依存特徴量を除外) |
| (将来) `evaluate.py` | polaris vs nova の rank_p Top1 ROI / Brier / ECE 比較レポート |
| (将来) `predict_overlay.py` | predict.py から呼ばれる overlay (entries[].nova フィールド追加) |

## 使い方 (Phase 1)

```bash
cd keiba-cicd-core/keiba-v2

# サンプル数確認 (Test 期間だけ build → 1勝クラス何件か表示)
.venv/Scripts/python.exe -m ml.nova.train_emerging --dry-run

# フル学習 (train/val/test 全部 build → 学習 → 評価 → 保存)
.venv/Scripts/python.exe -m ml.nova.train_emerging --version 0.1
```

出力:
- `data3/ml/nova/emerging/model_p.txt`
- `data3/ml/nova/emerging/model_meta.json`
- `data3/ml/nova/emerging/training_report.json`

## Phase 1 評価基準

`training_report.json` の `diff.verdict` が:
- `🟢 polaris 上回り`: ROI +10pt 以上 → Phase 2 進行
- `🟡 同程度`: ±10pt → 失敗分析後 Phase 2 判断
- `🔴 polaris 下回り`: ROI -10pt 以下 → 設計再検討 (特徴量除外 / クラス内 ranking 化 など)
