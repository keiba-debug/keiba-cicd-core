# keiba-ai

**AI競馬予想システム - エキスパートチーム**

このプロジェクトは、機械学習と購入戦略を組み合わせた競馬予想AIシステムです。

---

## 🎯 目的

**毎週の競馬予想でプラス収支を実現し、推理エンターテインメントとして競馬を楽しむ**

- 予想精度だけでなく、購入戦略・資金管理を重視
- 期待値ベースの機械的な判断
- トライアンドエラーで継続的に改善

---

## 🏗️ プロジェクト構成

```
keiba-ai/
  ├─ ml/                    # 機械学習
  │   ├─ models/            # 訓練済みモデル
  │   ├─ scripts/           # 学習・予測スクリプト
  │   └─ notebooks/         # 実験用Notebook
  │
  ├─ betting/               # 購入戦略
  │   ├─ evaluator.py       # 期待値計算エンジン
  │   ├─ strategist.py      # 購入戦略（ケリー基準）
  │   ├─ odds_manager.py    # オッズ管理
  │   └─ executor.py        # 実行記録
  │
  ├─ analysis/              # 分析・バックテスト
  │   └─ backtest.py        # バックテスト
  │
  └─ docs/                  # ドキュメント
      ├─ BETTING_STRATEGY_FRAMEWORK.md
      └─ ODDS_MANAGEMENT.md
```

---

## 👥 エキスパートチーム

| エージェント | 愛称 | 役割 |
|------------|------|------|
| PREDICTOR | アルテタ | ML予想 |
| EVALUATOR | シノ | 期待値計算 |
| STRATEGIST | シカマル | 購入戦略・リスク管理 |
| EXECUTOR | サイ | 実行記録 |
| ANALYST | ひなた | 結果分析 |
| LEARNER | ナルト | 継続的改善 |

詳細: [ai-team/experts/TEAM_ROSTER.md](../ai-team/experts/TEAM_ROSTER.md)

---

## 🔗 依存関係

### keiba-cicd-core/KeibaCICD.TARGET を参照

このプロジェクトは、既存の `KeibaCICD.TARGET` プロジェクトの共通ライブラリを使用します。

```python
import sys
from pathlib import Path

# KeibaCICD.TARGET を参照
target_root = Path(__file__).resolve().parents[2] / "keiba-cicd-core" / "KeibaCICD.TARGET"
sys.path.insert(0, str(target_root))

# JRA-VANライブラリを使用
from common.jravan import (
    get_horse_id_by_name,
    analyze_horse_training,
    get_horse_info
)
```

---

## 🚀 クイックスタート

### 1. 環境セットアップ

```powershell
cd E:\share\KEIBA-CICD\_keiba\keiba-ai

# 必要なライブラリをインストール
pip install -r requirements.txt
```

### 2. EVALUATOR（期待値計算）のテスト

```powershell
python betting/evaluator.py
```

### 3. STRATEGIST（購入戦略）のテスト

```powershell
python betting/strategist.py
```

### 4. EXECUTOR（実行記録）のテスト

```powershell
python betting/executor.py
```

### 5. ANALYST（バックテスト）のテスト

```powershell
python analysis/backtest.py
```

### 6. LEARNER（継続的改善）のテスト

```powershell
python learning/learner.py
```

---

## 📊 システムフロー

```
1. データ収集（キバ）
   ↓
2. ML予想（アルテタ）
   ↓
3. 期待値計算（シノ）
   ↓
4. 購入戦略（シカマル）
   ↓
5. 実行記録（サイ）
   ↓
6. 結果分析（ひなた）
   ↓
7. 改善提案（ナルト）
```

---

## 🎯 開発ロードマップ

### Phase 1: コアエンジン実装 ✅ **完了**

- ✅ EVALUATOR - 期待値計算エンジン（シノ）
- ✅ STRATEGIST - ケリー基準・リスク管理（シカマル）
- ✅ EXECUTOR - 実行記録システム（サイ）

### Phase 2: バックテスト（進行中）

- ✅ 過去データでシミュレーション（ひなた）
- ✅ 回収率計算・パフォーマンス分析
- ✅ 戦略評価・改善提案

### Phase 3: 実運用（進行中）

- ⏳ 週次サイクルの確立
- ⏳ 自動化
- ✅ 継続的改善（ナルト）

---

## 📚 ドキュメント

- [購入戦略フレームワーク](docs/BETTING_STRATEGY_FRAMEWORK.md)
- [オッズ管理ガイド](docs/ODDS_MANAGEMENT.md)
- [機械学習プラン](../keiba-cicd-core/KeibaCICD.TARGET/ml/LEARNING_PLAN.md)

---

## 🤝 貢献

このプロジェクトは、ふくだ君とカカシ（AI相談役）が中心となって開発しています。

- オーナー: ふくだ君
- 技術リーダー: カカシ (Claude Sonnet 4.5)
- エキスパートチーム: アルテタ、シノ、シカマル、サイ、ひなた、ナルト、ベンゲル、キバ

---

## 📝 ライセンス

Private Project

---

*作成日: 2026-01-30*
*最終更新: 2026-01-31 - Phase 3 進行中（ナルト実装完了、データ仕様書作成完了）*
