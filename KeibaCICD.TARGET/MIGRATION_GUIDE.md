# データ管理改善 - 移行ガイド

## 概要

KeibaCICDプロジェクトのデータ管理を改善し、環境変数による統一的なパス管理を実現しました。

## 変更内容

### 環境変数の整理

#### 変更前
```powershell
$env:LOG_DIR = "E:\share\KEIBA-CICD\logs"
$env:DATA_ROOT= "E:\share\KEIBA-CICD\data2"
$env:DATA_ROOT = "E:\share\KEIBA-CICD\data2"          # 冗長
$env:JV_DATA_ROOT_DIR = "C:\TFJV"
```

#### 変更後
```powershell
# 必要な環境変数は2つだけ
$env:DATA_ROOT= "E:\share\KEIBA-CICD\data2"  # 競馬データ全般
$env:JV_DATA_ROOT_DIR = "C:\TFJV"                       # JRA-VAN生データ
```

**削除された環境変数**:
- `DATA_ROOT` - `KEIBA_DATA_ROOT_DIR` と重複のため削除
- `LOG_DIR` - `KEIBA_DATA_ROOT_DIR/logs` に統一

### ディレクトリ構造

```
E:\share\KEIBA-CICD\data2\
├── logs\                    # ログファイル（全プロジェクト共通）
├── races\                   # レースデータ（keibabook）
├── horses\                  # 馬データ（keibabook）
├── target\                  # TARGET関連データ（新規）
│   ├── race_type_standards.json
│   ├── training_summary\
│   └── analysis\
└── jravan\                  # JraVanSync関連データ（将来用）
```

## 移行手順

### 1. 環境変数の更新

PowerShellで以下を実行（永続化する場合は、システム環境変数に設定）:

```powershell
# 古い環境変数を削除
Remove-Item Env:DATA_ROOT -ErrorAction SilentlyContinue
Remove-Item Env:LOG_DIR -ErrorAction SilentlyContinue

# 新しい環境変数を設定
$env:DATA_ROOT= "E:\share\KEIBA-CICD\data2"
$env:JV_DATA_ROOT_DIR = "C:\TFJV"
```

永続化（システム環境変数に設定）:

```powershell
[System.Environment]::SetEnvironmentVariable("KEIBA_DATA_ROOT_DIR", "E:\share\KEIBA-CICD\data2", "User")
[System.Environment]::SetEnvironmentVariable("JV_DATA_ROOT_DIR", "C:\TFJV", "User")
```

### 2. 既存データの移行

#### 2.1 ドライラン（確認のみ）

```powershell
cd E:\share\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.TARGET
python scripts/migrate_data.py --dry-run
```

#### 2.2 実際の移行

```powershell
python scripts/migrate_data.py
```

#### 2.3 強制上書き（既存ファイルがある場合）

```powershell
python scripts/migrate_data.py --force
```

### 3. 動作確認

#### 3.1 共通設定の確認

```powershell
cd E:\share\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.TARGET
python common/config.py
```

出力例:
```
============================================================
KeibaCICD.TARGET Configuration
============================================================
KEIBA_DATA_ROOT_DIR: E:\share\KEIBA-CICD\data2
JV_DATA_ROOT_DIR:    C:\TFJV

Directories:
  - Target:  E:\share\KEIBA-CICD\data2\target
  - Logs:    E:\share\KEIBA-CICD\data2\logs
  - Races:   E:\share\KEIBA-CICD\data2\races
  - Horses:  E:\share\KEIBA-CICD\data2\horses

JRA-VAN Data:
  - DE_DATA: C:\TFJV\DE_DATA
  - SE_DATA: C:\TFJV\SE_DATA
  - CK_DATA: C:\TFJV\CK_DATA
============================================================
```

#### 3.2 TARGETスクリプトのテスト

```powershell
# レースタイプ基準値算出（出力先が target/ になっているか確認）
python scripts/calculate_race_type_standards_jv.py --years 2025 --output test_output.json

# 出力先を確認
ls E:\share\KEIBA-CICD\data2\target\test_output.json
```

## 影響を受けるスクリプト

### 変更されたスクリプト

1. **KeibaCICD.TARGET/scripts/**
   - `calculate_race_type_standards_jv.py` - 出力先が `target/` に変更
   - `parse_jv_race_data.py` - データパスが統一
   - `get_race_training.py` - データパスが統一
   - `parse_ck_data.py` - CK_DATAパスが統一

2. **KeibaCICD.keibabook/src/utils/config.py**
   - `get_log_dir()` - デフォルトが `KEIBA_DATA_ROOT_DIR/logs` に変更

3. **KeibaCICD.WebViewer/src/lib/config.ts**
   - `DATA_ROOT` を `KEIBA_DATA_ROOT_DIR` に統一（後方互換性のため `DATA_ROOT` もエイリアスとして提供）
   - `PATHS` に `logs` と `target` を追加

4. **KeibaCICD.WebViewer/src/lib/data/**
   - `horse-race-index.ts` - config.ts からインポート
   - `integrated-horse-reader.ts` - config.ts からインポート（4箇所）

5. **KeibaCICD.WebViewer/src/app/api/training/save/route.ts**
   - config.ts からインポート

### 新規作成されたファイル

1. **KeibaCICD.TARGET/common/config.py**
   - 共通設定モジュール（全スクリプトで使用）

2. **KeibaCICD.TARGET/scripts/migrate_data.py**
   - データ移行スクリプト

## トラブルシューティング

### Q: 移行後、古いデータが見つからない

A: 環境変数が正しく設定されているか確認してください:

```powershell
$env:KEIBA_DATA_ROOT_DIR
# 出力: E:\share\KEIBA-CICD\data2
```

### Q: ログファイルが出力されない

A: ログディレクトリが作成されているか確認:

```powershell
Test-Path "E:\share\KEIBA-CICD\data2\logs"
# 出力: True

# 存在しない場合は作成
mkdir "E:\share\KEIBA-CICD\data2\logs"
```

### Q: TARGETスクリプトがエラーになる

A: 共通設定モジュールが正しくインポートされているか確認:

```powershell
cd E:\share\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.TARGET
python -c "from common.config import get_target_data_dir; print(get_target_data_dir())"
```

## ロールバック手順

変更を元に戻す場合:

### 1. 環境変数を元に戻す

```powershell
$env:DATA_ROOT = "E:\share\KEIBA-CICD\data2"
$env:LOG_DIR = "E:\share\KEIBA-CICD\logs"
```

### 2. 変更されたファイルを復元

Git経由で元のファイルに戻す:

```powershell
cd E:\share\KEIBA-CICD\_keiba
git checkout HEAD -- keiba-cicd-core/KeibaCICD.TARGET/scripts/
git checkout HEAD -- keiba-cicd-core/KeibaCICD.keibabook/src/utils/config.py
```

## USE_NEW_DATA_STRUCTURE について

### 現在の状態

`.env` ファイルで `USE_NEW_DATA_STRUCTURE=true` が設定されており、新しいデータ構造を使用しています。

- **新構造**: `races/YYYY/MM/DD/` - 日付別にレースデータを保存
- **旧構造**: `race_ids/`, `temp/` - フラットな構造

### 推奨事項

現在は新構造で運用されているため、このまま維持することを推奨します。もし旧構造に戻す必要がある場合は、`.env` ファイルで `USE_NEW_DATA_STRUCTURE=false` に変更してください。

## 次のステップ

この改善により、以下が可能になりました:

1. ✅ データパスの統一管理（TARGET, keibabook, WebViewer）
2. ✅ 環境変数の簡素化（2つだけ: `KEIBA_DATA_ROOT_DIR`, `JV_DATA_ROOT_DIR`）
3. ✅ ログファイルの一元管理（`KEIBA_DATA_ROOT_DIR/logs`）
4. ✅ WebViewerの環境変数統一（`DATA_ROOT` → `KEIBA_DATA_ROOT_DIR`）

次の改善項目:
- [ ] データベース導入（PostgreSQL, MongoDB）
- [ ] データ取得部分のAPI化（FastAPI）
- [ ] JraVanSyncとの統合

---

*最終更新: 2026-01-30*
