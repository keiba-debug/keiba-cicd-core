"""バージョン別アーカイブユーティリティ

MLモデルや分析結果の保存前に、既存ファイルを versions/ サブディレクトリに退避する。
- versions/{version}/ にサブディレクトリ方式でコピー（ML用）
- versions/{filename}_v{version}.json にフラット方式でコピー（分析用）
- versions/versions.json マニフェストでバージョン一覧を管理
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def _read_manifest(versions_dir: Path) -> List[Dict]:
    manifest_path = versions_dir / "versions.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return []


def _write_manifest(versions_dir: Path, entries: List[Dict]) -> None:
    manifest_path = versions_dir / "versions.json"
    manifest_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def archive_before_save(
    base_dir: Path,
    version: str,
    files: List[str],
    metadata: Optional[Dict] = None,
) -> bool:
    """対象ファイルを versions/{version}/ にコピーし、マニフェストを更新する。

    Args:
        base_dir: データディレクトリ（例: data3/ml/）
        version: バージョン文字列（例: "3.5"）
        files: アーカイブ対象のファイル名リスト
        metadata: マニフェストに追加するメタデータ

    Returns:
        True: アーカイブ実行, False: スキップ（既存 or ファイルなし）
    """
    versions_dir = base_dir / "versions"
    ver_dir = versions_dir / f"v{version}"

    # 冪等: 既にアーカイブ済みならスキップ
    if ver_dir.exists():
        return False

    # コピー対象の存在チェック
    existing = [f for f in files if (base_dir / f).exists()]
    if not existing:
        return False

    ver_dir.mkdir(parents=True, exist_ok=True)
    for fname in existing:
        shutil.copyfile(base_dir / fname, ver_dir / fname)

    # マニフェスト更新
    entries = _read_manifest(versions_dir)
    entry = {
        "version": version,
        "archived_at": datetime.now().isoformat(timespec="seconds"),
        "files": existing,
    }
    if metadata:
        entry.update(metadata)
    entries.append(entry)
    _write_manifest(versions_dir, entries)

    print(f"  [versioning] Archived v{version} → {ver_dir} ({len(existing)} files)")
    return True


def archive_flat(
    base_dir: Path,
    version: str,
    source_file: str,
    metadata: Optional[Dict] = None,
) -> bool:
    """分析ファイルをフラット構造でアーカイブする。

    versions/{stem}_v{version}.json 形式で保存。

    Args:
        base_dir: データディレクトリ（例: data3/analysis/）
        version: バージョン文字列
        source_file: アーカイブ対象のファイル名
        metadata: マニフェストに追加するメタデータ

    Returns:
        True: アーカイブ実行, False: スキップ
    """
    src_path = base_dir / source_file
    if not src_path.exists():
        return False

    versions_dir = base_dir / "versions"
    stem = Path(source_file).stem
    ext = Path(source_file).suffix
    dest_name = f"{stem}_v{version}{ext}"
    dest_path = versions_dir / dest_name

    # 冪等: 既にアーカイブ済みならスキップ
    if dest_path.exists():
        return False

    versions_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_path, dest_path)

    # マニフェスト更新
    entries = _read_manifest(versions_dir)
    entry = {
        "version": version,
        "file": source_file,
        "archived_as": dest_name,
        "archived_at": datetime.now().isoformat(timespec="seconds"),
    }
    if metadata:
        entry.update(metadata)
    entries.append(entry)
    _write_manifest(versions_dir, entries)

    print(f"  [versioning] Archived {source_file} v{version} → {dest_path.name}")
    return True


def get_versions(base_dir: Path) -> List[Dict]:
    """versions.json からバージョン一覧を返す（新しい順）。"""
    entries = _read_manifest(base_dir / "versions")
    return sorted(entries, key=lambda e: e.get("archived_at", ""), reverse=True)
