# Z:/KEIBA-CICD/data 等のパス設定一覧

`Z:/KEIBA-CICD/data`・`Z:/KEIBA-CICD/data2` および **Y:/**（JV データ用）がどこで設定されているかの調査結果です。

---

## 1. 環境変数（推奨の変更方法）

| 環境変数 | 用途 | デフォルト（未設定時） |
|----------|------|------------------------|
| **KEIBA_DATA_ROOT_DIR** | データルート（keibabook・TARGET 等） | 各ファイルで異なる（下記参照） |
| **DATA_ROOT** | WebViewer のみ（調教保存等） | `Z:/KEIBA-CICD/data2` |
| **JV_DATA_ROOT_DIR** | JRA-VAN（JV）データのルート（TARGET・WebViewer） | **`Y:/`** |

**変更例（PowerShell）**

```powershell
$env:DATA_ROOT= "D:/MyData/KEIBA-CICD"
$env:DATA_ROOT = "D:/MyData/KEIBA-CICD"
$env:JV_DATA_ROOT_DIR = "D:/JV"   # Y:/ を変える場合
```

**.env で設定する場合**

- `keiba-cicd-core/.env` または `KeibaCICD.keibabook/.env` に  
  `KEIBA_DATA_ROOT_DIR=Z:/KEIBA-CICD/data2` を記載  
- `config_manager.py` や `Config`（keibabook）は `.env` を読み込む

---

## 2. 中核となる設定ファイル

### 2.1 KeibaCICD.keibabook（Python）

| ファイル | 役割 | デフォルト値 |
|----------|------|--------------|
| **KeibaCICD.keibabook/src/utils/config.py** | `Config.get_data_root_dir()` / `get_data_dir()` | 環境変数が無い場合は `PROJECT_ROOT / "data"` |
| **KeibaCICD.keibabook/src/config/data_paths.py** | `DataPathConfig` の `base_path` | **`Z:/KEIBA-CICD/data`**（ハードコード） |
| **tools/config_manager.py** | 設定表示・環境変数一覧 | 環境変数 `KEIBA_DATA_ROOT_DIR` 等を参照 |

- 多くの Python コードは `os.getenv('KEIBA_DATA_ROOT_DIR', '...')` で参照し、フォールバックだけファイルごとに `Z:/KEIBA-CICD/data` や `Z:/KEIBA-CICD/data2` が混在しています。

### 2.2 KeibaCICD.WebViewer（Next.js）

| ファイル | 役割 | デフォルト値 |
|----------|------|--------------|
| **KeibaCICD.WebViewer/src/app/api/training/save/route.ts** | 調教保存先のルート | **`process.env.DATA_ROOT \|\| 'Z:/KEIBA-CICD/data2'`** |
| **KeibaCICD.WebViewer/src/lib/config.ts** | JV ルート・BABA パス | **JV_DATA_ROOT_DIR**（未設定時 `Y:/`）、**BABA_DATA_PATH** = `JV_DATA_ROOT_DIR/_BABA` |

- WebViewer の「データルート」は **DATA_ROOT** のみで、`KEIBA_DATA_ROOT_DIR` は使いません。
- **BABA**（クッション値・含水率 CSV）の場所は常に **JV_DATA_ROOT_DIR のサブディレクトリ _BABA 以下**（`config.ts` で `path.join(JV_DATA_ROOT_DIR, '_BABA')` として導出）。

### 2.3 KeibaCICD.TARGET（Python）

| ファイル | 役割 | デフォルト値 |
|----------|------|--------------|
| **KeibaCICD.TARGET/scripts/parse_jv_race_data.py** | JVレースデータの出力先ルート | **`_get_env_path("KEIBA_DATA_ROOT_DIR", "Z:/KEIBA-CICD/data2")`** |

### 2.4 ワークスペース

| ファイル | 役割 |
|----------|------|
| **_keiba.code-workspace** | マルチルートの `path` に **`Z:/KEIBA-CICD`** を記載（フォルダ参照用） |

### 2.5 Y:/（JV データ・JRA-VAN 用）

| 環境変数 | デフォルト | 参照するプロジェクト |
|----------|------------|----------------------|
| **JV_DATA_ROOT_DIR** | **Y:/** | TARGET（parse_jv_race_data.py, parse_jv_horse_data.py）、WebViewer（training/summary, training/save, debug/umdata, debug/training、**BABA 読み込み**） |

- **環境変数で変えられる箇所**: 上記のスクリプト・API は `JV_DATA_ROOT_DIR` 未設定時は `Y:/` を使用。設定すれば Y:/ 以外のドライブ・パスに変更可能。
- **ハードコードのままの箇所**（環境変数非対応）:
  - **tools/target_data_parser.py** … `TARGET_DATA_ROOT = Path("Y:/")`
  - **KeibaCICD.TARGET/scripts/** の一部 … `Y:/TXT`、`Y:/DE_DATA`、`Y:/_temp` 等を直接指定（generate_race_marks.py, debug_dr_file.py, batch_analyze.py, analyze_*.py 等）。これらは **JV_DATA_ROOT_DIR** を読まず、Y:/ を変えても影響しない。

---

## 3. ファイル別「Z:/KEIBA-CICD/data」出現箇所（要約）

### デフォルトが `Z:/KEIBA-CICD/data` のファイル

- **KeibaCICD.keibabook/src/config/data_paths.py**  
  - `DataPathConfig(base_path="Z:/KEIBA-CICD/data")`
- **KeibaCICD.keibabook/src/integrator/markdown_generator.py**  
  - `os.getenv('KEIBA_DATA_ROOT_DIR', 'Z:/KEIBA-CICD/data')` が複数箇所
- **KeibaCICD.keibabook/src/scrapers/jockey_scraper.py**  
  - `os.getenv('KEIBA_DATA_ROOT_DIR', 'Z:/KEIBA-CICD/data')`
- **KeibaCICD.keibabook/src/scrapers/jockey_stats_aggregator.py**  
  - 同上
- **KeibaCICD.keibabook/src/scrapers/horse_profile_manager.py**  
  - `base_path: str = "Z:/KEIBA-CICD"`、内部で `data` / `data2` を併用
- **KeibaCICD.keibabook/src/scrapers/horse_detail_scraper.py**  
  - `Z:/KEIBA-CICD/data/horses/cache` 等（ハードコード）
- **KeibaCICD.keibabook/src/scrapers/horse_past_races_fetcher.py**  
  - `Z:/KEIBA-CICD/data/horses/past_races` 等（ハードコード）
- **KeibaCICD.keibabook/src/scrapers/create_horse_index.py**  
  - `Z:/KEIBA-CICD/data/temp` 等（ハードコード）
- **KeibaCICD.keibabook/scripts/migrate_data_structure.py**  
  - `--base-path` デフォルト `Z:/KEIBA-CICD/data`
- その他、ドキュメント・スクリプト・テスト内の例示パス多数

### デフォルトが `Z:/KEIBA-CICD/data2` のファイル

- **KeibaCICD.WebViewer/src/app/api/training/save/route.ts**  
  - `DATA_ROOT` 未設定時: `Z:/KEIBA-CICD/data2`
- **KeibaCICD.TARGET/scripts/parse_jv_race_data.py**  
  - `KEIBA_DATA_ROOT_DIR` 未設定時: `Z:/KEIBA-CICD/data2`
- **KeibaCICD.keibabook/src/horse_profile_cli.py**  
  - 一部で `os.getenv('KEIBA_DATA_ROOT_DIR', 'Z:/KEIBA-CICD/data2')`
- **KeibaCICD.keibabook/src/scrapers/horse_profile_manager.py**  
  - `KEIBA_DATA_ROOT_DIR` 未設定時は `base_path / "data2"`
- **運用サポート.md**  
  - デフォルト記載: `Z:/KEIBA-CICD/data2/`
- **KeibaCICD.WebViewer/README.md**  
  - 同上

---

## 4. まとめ：設定を変えるとき

1. **環境変数で統一する（推奨）**  
   - **KEIBA_DATA_ROOT_DIR** … Python（keibabook・TARGET・tools）  
   - **DATA_ROOT** … WebViewer の API  
   - 両方とも同じルート（例: `Z:/KEIBA-CICD/data2`）にすると運用しやすいです。

2. **ハードコードされているパス**  
   - `data_paths.py` の `base_path` デフォルト  
   - `horse_profile_manager.py` / `horse_detail_scraper.py` 等の `Z:/KEIBA-CICD/data/...`  
   - これらは環境変数未使用のため、変更する場合は該当ファイルの修正が必要です。

3. **ドキュメント・README**  
   - `運用サポート.md`、`KeibaCICD.WebViewer/README.md`、`docs/web-viewer-requirements.md` 等に `Z:/KEIBA-CICD/data` / `data2` の記載があります。実機のパスを変える場合はドキュメントも合わせて更新すると分かりやすいです。

---

## 5. プロジェクト別：設定が必要か？

| プロジェクト | 参照する環境変数 | .env の読み込み元 | 設定が必要？ |
|--------------|------------------|--------------------|--------------|
| **KeibaCICD.keibabook** | **KEIBA_DATA_ROOT_DIR** | `KeibaCICD.keibabook/.env` | ✅ 必要（パスを変える場合） |
| **KeibaCICD.WebViewer** | **DATA_ROOT**（別名）<br>**JV_DATA_ROOT_DIR**（Y:/ の代わり） | `KeibaCICD.WebViewer/.env` または `.env.local`（Next.js の仕様） | ✅ 必要（**DATA_ROOT** は keibabook と別変数）<br>Y:/ を変える場合は **JV_DATA_ROOT_DIR** も設定 |
| **KeibaCICD.TARGET** | **KEIBA_DATA_ROOT_DIR**<br>**JV_DATA_ROOT_DIR**（Y:/ の代わり） | ① `KeibaCICD.keibabook/.env`<br>② `KeibaCICD.TARGET/.env`（先に見つかった方） | ✅ keibabook の .env を読めば KEIBA は追加不要<br>Y:/ を変える場合は **JV_DATA_ROOT_DIR** を設定 |

### 結論

- **keibabook と TARGET** は同じ **KEIBA_DATA_ROOT_DIR** を使う。  
  - 運用: **KeibaCICD.keibabook/.env** に `KEIBA_DATA_ROOT_DIR=...` を1つ書けば、keibabook と TARGET の両方に効く（TARGET は keibabook の .env を読むため）。
- **WebViewer** だけ **DATA_ROOT** を使う。  
  - パスを変える場合は **KeibaCICD.WebViewer** 側で **DATA_ROOT** の設定が別途必要（システム環境変数か `KeibaCICD.WebViewer/.env.local` など）。

### 1か所でまとめて設定したい場合

**システム環境変数**（またはユーザー環境変数）に次を設定すると、3プロジェクトとも同じルートで動かせます。

- `KEIBA_DATA_ROOT_DIR` = 例: `Z:/KEIBA-CICD/data2`
- `DATA_ROOT` = 例: `Z:/KEIBA-CICD/data2`（WebViewer 用）
- `JV_DATA_ROOT_DIR` = 例: `Y:/`（JV データ用。Y:/ のままなら未設定でよい）

この場合、各プロジェクトの .env に同じ内容を書く必要はありません。

---

*最終更新: 調査時点のコードベースに基づく*
