#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
統一モデルローダー

model_registry.json を唯一の真実としてモデルのロード・パス解決・バージョン一覧を提供する。
個別の load_model_and_meta() / load_obstacle_model() / load_closing_model() を置き換える。

Usage:
    from ml.model_loader import load_model, list_models, list_versions

    # ライブモデルをロード
    bundle = load_model("polaris")

    # 特定バージョンをロード
    bundle = load_model("polaris", version="7.9")

    # 全モデル一覧
    models = list_models()

    # 特定モデルのバージョン一覧
    versions = list_versions("polaris")
"""

import json
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core import config


# ---------------------------------------------------------------------------
# ModelBundle: モデル一式を保持する値オブジェクト
# ---------------------------------------------------------------------------

@dataclass
class ModelBundle:
    """ロードされたモデル一式"""
    name: str                            # "polaris", "enif", "eclipse"
    version: str                         # "polaris-2.0", "obstacle-v2.5b"
    model_p: object = None               # LightGBM Booster (Place/主分類)
    model_w: object = None               # LightGBM Booster (Win) — optional
    model_ar: object = None              # LightGBM Booster (着差回帰) — optional
    calibrators: Optional[dict] = None   # {'cal_p': ..., 'cal_w': ...}
    meta: dict = field(default_factory=dict)
    source: str = "live"                 # "live" or "archive"

    @property
    def features(self) -> list:
        """特徴量リスト（meta構造の差異を吸収）"""
        # polaris系: features_value
        fv = self.meta.get('features_value', [])
        if fv:
            return fv
        # enif系: features_p (obstacle metaの形式)
        fp = self.meta.get('features_p', [])
        if fp:
            return fp
        return []

    @property
    def features_per_model(self) -> Optional[dict]:
        return self.meta.get('features_per_model')

    @property
    def has_win(self) -> bool:
        return self.model_w is not None

    @property
    def has_ar(self) -> bool:
        return self.model_ar is not None

    @property
    def has_calibrators(self) -> bool:
        return self.calibrators is not None

    def summary(self) -> str:
        parts = [f"{self.name} v{self.version}"]
        parts.append(f"P({len(self.features)}f)")
        if self.has_win:
            parts.append("+W")
        if self.has_ar:
            parts.append("+AR")
        if self.has_calibrators:
            parts.append("+Cal")
        parts.append(f"[{self.source}]")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Registry: model_registry.json の読み書き
# ---------------------------------------------------------------------------

_registry_cache: Optional[dict] = None


def _registry_path() -> Path:
    return config.ml_dir() / "model_registry.json"


def _load_registry(force_reload: bool = False) -> dict:
    global _registry_cache
    if _registry_cache is not None and not force_reload:
        return _registry_cache

    path = _registry_path()
    if not path.exists():
        raise FileNotFoundError(
            f"model_registry.json が見つかりません: {path}\n"
            "モデルレジストリを初期化してください"
        )
    with open(path, encoding='utf-8') as f:
        _registry_cache = json.load(f)
    return _registry_cache


def _save_registry(data: dict) -> None:
    global _registry_cache
    path = _registry_path()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    _registry_cache = data


def invalidate_cache() -> None:
    """レジストリキャッシュをクリア（テストやリロード用）"""
    global _registry_cache
    _registry_cache = None


# ---------------------------------------------------------------------------
# パス解決
# ---------------------------------------------------------------------------

def _resolve_model_dir(model_name: str, version: Optional[str] = None) -> Path:
    """モデルのディレクトリパスを解決する。

    新構造: ml/models/{model_name}/live/ or ml/models/{model_name}/archive/{version}/
    旧構造: ml/ (live) or ml/versions/v{version}/ (archive) — フォールバック
    """
    ml_dir = config.ml_dir()
    registry = _load_registry()
    model_entry = registry.get('models', {}).get(model_name)

    if model_entry is None:
        available = list(registry.get('models', {}).keys())
        raise ValueError(
            f"モデル '{model_name}' はレジストリに存在しません。"
            f"利用可能: {available}"
        )

    if version is None or version == "live":
        # ライブモデル
        # 新構造を優先チェック
        new_path = ml_dir / "models" / model_name / "live"
        if new_path.exists() and (new_path / "meta.json").exists():
            return new_path

        # 旧構造フォールバック: model_entry の meta_file から推定
        meta_file = model_entry.get('meta_file', 'model_meta.json')
        if (ml_dir / meta_file).exists():
            return ml_dir
        raise FileNotFoundError(
            f"モデル '{model_name}' のライブディレクトリが見つかりません。\n"
            f"  新構造: {new_path}\n"
            f"  旧構造: {ml_dir / meta_file}"
        )
    else:
        # アーカイブ版
        # 新構造
        new_path = ml_dir / "models" / model_name / "archive" / version
        if new_path.exists():
            return new_path

        # 旧構造: model_registry の versions 配列から dir を検索
        for v_entry in model_entry.get('versions', []):
            if v_entry['version'] == version:
                v_dir = v_entry.get('dir')
                if v_dir:
                    old_path = ml_dir / "versions" / v_dir
                    if old_path.exists():
                        return old_path

        # 旧構造フォールバック: v{version}
        old_path = ml_dir / "versions" / f"v{version}"
        if old_path.exists():
            return old_path

        raise FileNotFoundError(
            f"モデル '{model_name}' のバージョン '{version}' が見つかりません。\n"
            f"利用可能: {[v['version'] for v in model_entry.get('versions', [])]}"
        )


# ---------------------------------------------------------------------------
# ファイル名マッピング（モデル種別ごとの命名規則）
# ---------------------------------------------------------------------------

# 新構造では全モデル統一: model_p.txt, model_w.txt, model_ar.txt, meta.json, calibrators.pkl
# 旧構造ではモデル種別ごとにファイル名が異なる

_LEGACY_FILE_MAP = {
    "polaris": {
        "model_p": "model_p.txt",
        "model_w": "model_w.txt",
        "model_ar": "model_ar.txt",
        "meta": "model_meta.json",
        "calibrators": "calibrators.pkl",
    },
    "enif": {
        "model_p": ["model_obstacle_p.txt", "model_obstacle.txt"],  # v2 → v1 fallback
        "model_w": "model_obstacle_w.txt",
        "model_ar": None,
        "meta": "model_obstacle_meta.json",
        "calibrators": ["calibrators_obstacle.pkl", "calibrator_obstacle.pkl"],
    },
    "eclipse": {
        "model_p": "model_closing.txt",
        "model_w": None,
        "model_ar": None,
        "meta": "model_closing_meta.json",
        "calibrators": "calibrator_closing.pkl",
    },
}

# 新構造の統一ファイル名
_STANDARD_FILES = {
    "model_p": "model_p.txt",
    "model_w": "model_w.txt",
    "model_ar": "model_ar.txt",
    "meta": "meta.json",
    "calibrators": "calibrators.pkl",
}


def _find_file(model_dir: Path, model_name: str, file_key: str) -> Optional[Path]:
    """ファイルパスを解決。新構造 → 旧構造フォールバック。"""
    # 新構造の統一名
    standard = _STANDARD_FILES.get(file_key)
    if standard and (model_dir / standard).exists():
        return model_dir / standard

    # 旧構造のモデル固有名
    legacy = _LEGACY_FILE_MAP.get(model_name, {}).get(file_key)
    if legacy is None:
        return None

    if isinstance(legacy, list):
        for candidate in legacy:
            if (model_dir / candidate).exists():
                return model_dir / candidate
        return None
    else:
        path = model_dir / legacy
        return path if path.exists() else None


# ---------------------------------------------------------------------------
# メインAPI: load_model
# ---------------------------------------------------------------------------

def load_model(model_name: str, version: Optional[str] = None) -> ModelBundle:
    """モデルをロードして ModelBundle を返す。

    Args:
        model_name: "polaris", "enif", "eclipse" など
        version: バージョン文字列。None/"live" = ライブモデル。

    Returns:
        ModelBundle
    """
    import lightgbm as lgb

    model_dir = _resolve_model_dir(model_name, version)
    source = "live" if (version is None or version == "live") else "archive"

    # Meta
    meta_path = _find_file(model_dir, model_name, "meta")
    if meta_path is None:
        raise FileNotFoundError(
            f"メタファイルが見つかりません: {model_dir}\n"
            f"  探索: {_STANDARD_FILES['meta']}, "
            f"{_LEGACY_FILE_MAP.get(model_name, {}).get('meta', '?')}"
        )
    with open(meta_path, encoding='utf-8') as f:
        meta = json.load(f)

    ver_label = meta.get('version', version or '?')

    # Model P (必須)
    p_path = _find_file(model_dir, model_name, "model_p")
    if p_path is None:
        raise FileNotFoundError(
            f"Placeモデルが見つかりません: {model_dir}"
        )
    model_p = lgb.Booster(model_file=str(p_path))
    print(f"[ModelLoader] {model_name} P loaded: {p_path.name}")

    # Model W (optional)
    model_w = None
    w_path = _find_file(model_dir, model_name, "model_w")
    if w_path is not None:
        model_w = lgb.Booster(model_file=str(w_path))
        print(f"[ModelLoader] {model_name} W loaded: {w_path.name}")

    # Model AR (optional)
    model_ar = None
    ar_path = _find_file(model_dir, model_name, "model_ar")
    if ar_path is not None:
        model_ar = lgb.Booster(model_file=str(ar_path))
        print(f"[ModelLoader] {model_name} AR loaded: {ar_path.name}")

    # Calibrators (optional)
    calibrators = None
    cal_path = _find_file(model_dir, model_name, "calibrators")
    if cal_path is not None:
        with open(cal_path, 'rb') as f:
            calibrators = pickle.load(f)
        print(f"[ModelLoader] {model_name} calibrators loaded: {cal_path.name}")

    if meta.get('has_calibrators') and calibrators is None:
        print(f"[WARN] {model_name} meta says calibrators exist but not found")

    bundle = ModelBundle(
        name=model_name,
        version=ver_label,
        model_p=model_p,
        model_w=model_w,
        model_ar=model_ar,
        calibrators=calibrators,
        meta=meta,
        source=source,
    )
    print(f"[ModelLoader] {bundle.summary()}")
    return bundle


def load_model_safe(model_name: str, version: Optional[str] = None) -> Optional[ModelBundle]:
    """load_model のエラー安全版。ロード失敗時は None を返す。"""
    try:
        return load_model(model_name, version)
    except (FileNotFoundError, ValueError) as e:
        print(f"[ModelLoader] {model_name} not available: {e}")
        return None


# ---------------------------------------------------------------------------
# 照会API
# ---------------------------------------------------------------------------

def get_active_version(model_name: str) -> Optional[str]:
    """レジストリからモデルのアクティブバージョンを返す"""
    registry = _load_registry()
    entry = registry.get('models', {}).get(model_name)
    if entry:
        return entry.get('active_version')
    return None


def list_models() -> List[dict]:
    """全登録モデルの概要リストを返す"""
    registry = _load_registry()
    result = []
    for name, entry in registry.get('models', {}).items():
        result.append({
            'name': name,
            'display_name': entry.get('name', name),
            'category': entry.get('category', ''),
            'description': entry.get('description', ''),
            'active_version': entry.get('active_version'),
            'version_count': len(entry.get('versions', [])),
        })
    return result


def list_versions(model_name: str) -> List[dict]:
    """特定モデルの全バージョンをリストする"""
    registry = _load_registry()
    entry = registry.get('models', {}).get(model_name)
    if entry is None:
        return []

    active = entry.get('active_version')
    versions = []
    for v in entry.get('versions', []):
        versions.append({
            **v,
            'is_active': v['version'] == active,
        })
    return versions


# ---------------------------------------------------------------------------
# レジストリ更新API（experiment系から呼ぶ）
# ---------------------------------------------------------------------------

def register_version(
    model_name: str,
    version: str,
    *,
    description: str = "",
    p_auc: Optional[float] = None,
    w_auc: Optional[float] = None,
    features: Optional[int] = None,
    archive_dir: Optional[str] = None,
    set_active: bool = False,
) -> None:
    """新バージョンをレジストリに登録する"""
    registry = _load_registry(force_reload=True)
    models = registry.setdefault('models', {})
    entry = models.get(model_name)
    if entry is None:
        raise ValueError(f"モデル '{model_name}' はレジストリに存在しません")

    # バージョンエントリ
    v_entry = {
        'version': version,
        'dir': archive_dir,
    }
    if description:
        v_entry['description'] = description
    if p_auc is not None:
        v_entry['p_auc'] = round(p_auc, 4)
    if w_auc is not None:
        v_entry['w_auc'] = round(w_auc, 4)
    if features is not None:
        v_entry['features'] = features

    # 既存バージョンの更新 or 新規追加
    existing_idx = None
    for i, v in enumerate(entry.get('versions', [])):
        if v['version'] == version:
            existing_idx = i
            break

    versions = entry.setdefault('versions', [])
    if existing_idx is not None:
        versions[existing_idx] = v_entry
    else:
        versions.insert(0, v_entry)

    if set_active:
        entry['active_version'] = version

    _save_registry(registry)
    print(f"[ModelLoader] Registered {model_name} v{version}"
          f"{' [ACTIVE]' if set_active else ''}")


def set_active_version(model_name: str, version: str) -> None:
    """アクティブバージョンを変更する"""
    registry = _load_registry(force_reload=True)
    entry = registry.get('models', {}).get(model_name)
    if entry is None:
        raise ValueError(f"モデル '{model_name}' はレジストリに存在しません")

    known = [v['version'] for v in entry.get('versions', [])]
    if version not in known:
        raise ValueError(f"バージョン '{version}' は登録されていません。既知: {known}")

    entry['active_version'] = version
    _save_registry(registry)
    print(f"[ModelLoader] {model_name} active version → {version}")
