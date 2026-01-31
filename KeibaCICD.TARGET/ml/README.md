# 機械学習モジュール

競馬予測AIの機械学習コンポーネント

## ⚠️ このモジュールの位置づけ

- **目的**: 機械学習の実験・学習用
- **用途**: モデル開発、特徴量試行、学習プロセスの理解
- **対象**: ふくだ君が機械学習を学びながら競馬予測モデルを開発
- **実運用**: 完成したモデルは `keiba-ai/models/production/` へデプロイ予定

**このディレクトリは「実験場」です。自由に試行錯誤してください。**

---

## 📁 ディレクトリ構造

```
ml/
├── README.md                 # このファイル
├── LEARNING_PLAN.md         # 学習プラン（詳細ガイド）
├── requirements.txt         # 必要なライブラリ
│
├── notebooks/               # Jupyter Notebook（学習用）
│   ├── 00_getting_started.ipynb
│   ├── 01_data_exploration.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_model_training.ipynb
│   ├── 04_model_evaluation.ipynb
│   └── 05_backtest.ipynb
│
├── scripts/                 # 本番用スクリプト
│   ├── 01_data_preparation.py
│   ├── 02_feature_engineering.py
│   ├── 03_model_training.py
│   ├── 04_backtest.py
│   └── 05_prediction.py
│
├── models/                  # 学習済みモデル
│   ├── lightgbm_model.pkl
│   ├── scaler.pkl
│   └── model_info.json
│
└── data/                    # 学習用データ
    ├── training/            # 学習データ
    └── predictions/         # 予測結果
```

## 🚀 クイックスタート

### 1. 環境セットアップ

```powershell
cd E:\share\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.TARGET\ml

# 必要なライブラリをインストール
pip install -r requirements.txt
```

### 2. 学習プランに従って進める

[**LEARNING_PLAN.md**](./LEARNING_PLAN.md) を開いて、Phase 0から順に進めてください。

各Phaseで以下のサイクルを回します：

```
理論を読む → Jupyter Notebookで実装 → 結果を確認 → 理解を深める
```

### 3. Jupyter Notebook起動

```powershell
jupyter notebook
```

ブラウザが開いたら、`notebooks/00_getting_started.ipynb` から始めます。

## 📚 学習の流れ

| Phase | 内容 | 期間 | ノートブック |
|-------|------|------|--------------|
| 0 | 環境構築と基礎理解 | 1日 | 00_getting_started.ipynb |
| 1 | データ理解と可視化 | 2-3日 | 01_data_exploration.ipynb |
| 2 | 特徴量エンジニアリング | 3-4日 | 02_feature_engineering.ipynb |
| 3 | はじめての機械学習モデル | 2-3日 | 03_model_training.ipynb |
| 4 | モデル評価とチューニング | 3-4日 | 04_model_evaluation.ipynb |
| 5 | バックテストと運用 | 2-3日 | 05_backtest.ipynb |

**合計**: 約2週間

## 🎯 ゴール

このモジュールを完了すると、以下ができるようになります：

- ✅ 機械学習の基礎概念を理解する
- ✅ 競馬データから特徴量を設計する
- ✅ ロジスティック回帰とLightGBMでモデルを訓練する
- ✅ モデルを評価し、チューニングする
- ✅ バックテストで回収率を計算する
- ✅ 新しいレースの予測を行う
- ✅ 実運用可能な予測システムを構築する

## 💡 学習のコツ

### 1. 手を動かす

理論を読むだけでなく、必ずコードを実行して結果を確認してください。

### 2. 失敗を恐れない

エラーが出たら、エラーメッセージを読んで原因を探りましょう。
失敗から学ぶことが最も効果的です。

### 3. 可視化する

グラフを描いて、データやモデルの挙動を目で見て確認しましょう。

### 4. 記録を残す

気づいたことや疑問をNotebookにメモとして残しましょう。

### 5. 繰り返す

一度で完璧に理解する必要はありません。
何度も繰り返すうちに理解が深まります。

## 🔧 トラブルシューティング

### ライブラリのインポートエラー

```python
ModuleNotFoundError: No module named 'xxx'
```

**解決策**:
```powershell
pip install xxx
```

### common.jravanが見つからない

```python
ModuleNotFoundError: No module named 'common'
```

**解決策**:
```python
import sys
sys.path.insert(0, '..')  # 親ディレクトリをパスに追加
```

### Jupyter Notebookが起動しない

**解決策**:
```powershell
pip install jupyter
jupyter notebook
```

### 日本語フォントが表示されない（グラフ）

**解決策**:
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['MS Gothic']
plt.rcParams['axes.unicode_minus'] = False
```

## 📖 参考リソース

### ドキュメント

- [LEARNING_PLAN.md](./LEARNING_PLAN.md) - 詳細な学習プラン
- [../docs/jravan/README.md](../docs/jravan/README.md) - JRA-VANデータ仕様
- [../docs/jravan/QUICK_REFERENCE.md](../docs/jravan/QUICK_REFERENCE.md) - よく使う関数

### 外部リソース

- [scikit-learn公式ドキュメント](https://scikit-learn.org/)
- [LightGBM公式ドキュメント](https://lightgbm.readthedocs.io/)
- [pandas公式ドキュメント](https://pandas.pydata.org/)

## 🤝 サポート

質問や問題があれば、以下を確認してください：

1. **LEARNING_PLAN.md** の該当箇所を再読
2. **エラーメッセージ** をGoogle検索
3. **サンプルコード** を参考にする

## 📝 進捗チェックリスト

学習の進捗を記録しましょう：

- [ ] Phase 0: 環境構築完了
- [ ] Phase 1: データ理解完了
- [ ] Phase 2: 特徴量エンジニアリング完了
- [ ] Phase 3: モデル学習完了
- [ ] Phase 4: モデル評価完了
- [ ] Phase 5: バックテスト完了
- [ ] 卒業課題: 総合演習完了

---

**それでは、[LEARNING_PLAN.md](./LEARNING_PLAN.md) を開いて、Phase 0から始めましょう！** 🚀

---

*作成日: 2026-01-30*
