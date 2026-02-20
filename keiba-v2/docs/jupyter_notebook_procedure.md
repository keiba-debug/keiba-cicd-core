# keiba-v2 ML を Jupyter Notebook で実行する手順

keiba-v2 の機械学習パイプラインを、Jupyter Notebook を使ってステップごとに視覚的に実行・検証するための手順です。

---

## Cursor 上で実行できるか？

**はい、Cursor 上で実行できます。**

Cursor は VS Code ベースのため、Jupyter Notebook の実行機能が統合されています。

| 方法 | 説明 |
|------|------|
| **Cursor 内蔵** | `.ipynb` ファイルを開き、セルをそのまま実行可能。追加エディタ不要。 |
| **ブラウザの Jupyter** | `jupyter notebook` または `jupyter lab` で起動する従来の方法。Cursor とは別タブで開く。 |

**推奨**: 基本的には **Cursor 内蔵の Notebook サポート** を使えば、同一エディタでコード編集とノートブック実行ができます。

> **拡張機能**: Cursor は Jupyter 対応を内蔵していますが、未インストールの場合は「Jupyter」拡張機能（Microsoft 製）を入れてください。拡張機能パネルで「Jupyter」で検索してインストールします。

---

## 前提条件

- Python 3.10 以上
- keiba-v2 の依存パッケージがインストール済み
- 学習用データ（`C:/KEIBA-CICD/data3` など）が用意されていること

---

## 1. Jupyter 関連のインストール

keiba-v2 の仮想環境（venv）がある場合は、その環境で以下を実行します。

```bash
cd c:\KEIBA-CICD\_keiba\keiba-cicd-core
pip install jupyter ipykernel matplotlib
```

- `jupyter` … ノートブック実行用
- `ipykernel` … Cursor がノートブック用に Python カーネルを利用するために必要
- `matplotlib` … グラフ・可視化用（任意だが推奨）

---

## 2. Cursor で Notebook を開く

1. Cursor でプロジェクトフォルダを開く（`c:\KEIBA-CICD\_keiba`）
2. メニュー **File → New File** をクリック
3. 右下の言語選択で **「Jupyter Notebook」** を選ぶ  
   または、ファイル名を `.ipynb` で保存して Notebook として開く
4. 右上の **カーネル選択** で、keiba-v2 用の Python 環境（venv など）を指定する

---

## 3. ノートブックの構成例

以下のセルを順に実行すると、ML パイプラインを段階的に確認できます。

### セル1: パス設定とインポート

```python
import sys
from pathlib import Path

# keiba-v2 をパスに追加
# ノートブックが keiba-v2 直下にある場合: Path.cwd() でOK
# 別の場所にある場合は絶対パスを指定
ROOT = Path(r"c:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2")
sys.path.insert(0, str(ROOT))

from core import config
print(f"ML dir: {config.ml_dir()}")
print(f"Masters dir: {config.masters_dir()}")
```

> **補足**: ノートブックの作業ディレクトリが `keiba-v2` 直下なら `ROOT = Path.cwd()` でも構いません。

### セル2: experiment モジュールの main を一括実行（動作確認）

```python
# 既存の experiment をそのまま実行
from ml.experiment import main
main()  # argparse なしで呼ぶ場合の挙動は experiment.py に依存
```

※ `main()` が `argparse` を前提としている場合は、ターミナルから `python -m ml.experiment` で一括実行し、ノートブックでは後述のステップ分割を利用します。

### セル3以降: ステップ分割で実行する場合

`experiment.py` の処理を分割して、各セルで中間結果を確認する方法です。

```python
# 例: データ読み込み〜特徴量まで
from ml.experiment import ...  # 必要な関数をインポート
# （experiment.py の関数構成に応じて、具体的な呼び出しを記述）
```

`experiment.py` の `main()` 内で使われている関数を確認し、それらをセルごとに呼び出す形で構成します。

---

## 4. 実行環境の選び方（Cursor / ブラウザ）

| 項目 | Cursor 内蔵 | ブラウザ (jupyter notebook) |
|------|-------------|-----------------------------|
| 起動 | `.ipynb` を開くだけ | ターミナルで `jupyter notebook` |
| カーネル | 右上で Python 環境を選択 | 起動時に自動選択 |
| 編集・実行 | セルを選択して Shift+Enter | 同様 |
| デバッグ | Cursor のデバッガ利用可能 | 制限あり |

**結論**: 通常は **Cursor 内蔵の Notebook** だけで十分です。ブラウザの Jupyter は、サーバー環境でリモート実行する場合などに使います。

---

## 5. トラブルシューティング

### カーネルが選べない

- `ipykernel` がインストールされているか確認: `pip list | findstr ipykernel`
- Cursor を再起動してから、再度カーネルを選択する

### `ModuleNotFoundError: No module named 'ml'` が出る

- `sys.path` に keiba-v2 のルートが含まれているか確認
- ノートブックの作業ディレクトリが `keiba-v2` 直下になるように開く、またはセル1で `sys.path.insert(0, str(ROOT))` を確実に実行する

### データファイルが見つからない

- `config.ml_dir()` / `config.masters_dir()` が指すパスにデータが存在するか確認
- 環境変数や `config` モジュールの設定を確認する

---

## 6. 次のステップ

- `experiment.py` の `main()` を読み、処理の流れを把握する
- 学習・評価部分をセルに分解し、特徴量重要度や ROC 曲線をノートブック上で可視化する
- `predict.py` や `backtest_vb.py` のロジックをノートブック上で試す

---

## 参考リンク

- [VS Code の Jupyter 拡張機能](https://code.visualstudio.com/docs/datascience/jupyter-notebooks)（Cursor も同様に利用可能）
- keiba-v2 ML: `keiba-cicd-core/keiba-v2/ml/`
