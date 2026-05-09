"""§14.2 関係者特徴量テスト

§8.2 のリーク防止ロジック (base + delta - expired) を厳密に検証する。
合成 history_cache + 事前ビルドした 2024-07 snapshot を tmp_path に置いて検証。

期待値の手計算詳細は _synthetic_fixture.py のコメント参照。
"""
from __future__ import annotations

import pytest

from analysis.niigata1000 import features
from analysis.niigata1000 import snapshot_builder as sb
from analysis.niigata1000.tests._synthetic_fixture import build_synthetic_history


@pytest.fixture(scope="module")
def synthetic_cache() -> dict:
    return build_synthetic_history()


@pytest.fixture(scope="module")
def snapshot_root_with_2024_07(synthetic_cache, tmp_path_factory):
    """2024-07 snapshot を tmp ディレクトリに永続化"""
    root = tmp_path_factory.mktemp("snapshots")
    snap = sb.build_relation_snapshot("2024-07", synthetic_cache)
    sb.write_snapshot(snap, root=root)
    return root


# ----------------------------------------------------------------------------
# (a) base + delta - expired ロジックの最終的な合算
# ----------------------------------------------------------------------------

def test_jockey_J_A_at_cutoff_2024_08_15(synthetic_cache, snapshot_root_with_2024_07):
    """J_A: cutoff='2024-08-15' で n=6, top3=5, strong=1

    内訳:
      base (2024-07 snapshot, 窓 2022-08-01~2024-07-31): A+B+D = n=5 top3=4 strong=1
      delta (2024-08-01~2024-08-14): C = n=2 top3=2 strong=0
      expired (2022-08-01~2022-08-15, cutoff_2y=2022-08-16): D = n=1 top3=1 strong=0
      合算: n=6 top3=5 strong=1
    """
    feat = features.compute_relation_features(
        jockey_code="J_A",
        trainer_code=None,
        cutoff_date="2024-08-15",
        history_cache=synthetic_cache,
        snapshot_root=snapshot_root_with_2024_07,
    )
    assert feat["jockey_choku_n"] == 6
    assert feat["jockey_choku_top3_rate"] == pytest.approx(5 / 6)
    assert feat["jockey_choku_strong_rate"] == pytest.approx(1 / 6)


def test_trainer_T_A_at_cutoff_2024_08_15(synthetic_cache, snapshot_root_with_2024_07):
    """T_A: cutoff='2024-08-15' で n=6, top3=5, strong=1 (J_A と対称)"""
    feat = features.compute_relation_features(
        jockey_code=None,
        trainer_code="T_A",
        cutoff_date="2024-08-15",
        history_cache=synthetic_cache,
        snapshot_root=snapshot_root_with_2024_07,
    )
    assert feat["trainer_choku_n"] == 6
    assert feat["trainer_choku_top3_rate"] == pytest.approx(5 / 6)
    assert feat["trainer_choku_strong_rate"] == pytest.approx(1 / 6)


# ----------------------------------------------------------------------------
# (b) §14.5 サンプル閾値: n<5 で rate は None
# ----------------------------------------------------------------------------

def test_jockey_J_B_below_threshold_returns_none_rates(
    synthetic_cache, snapshot_root_with_2024_07
):
    """J_B: cutoff='2024-08-15' で n=3 (< 5) → rate は None

    内訳:
      base J_B: A(n=2 top3=1) + D(n=1 top3=1) = n=3 top3=2 strong=0
      delta J_B: C H_C2 (finish=4) = n=1 top3=0 strong=0
      expired J_B: D H_D2 = n=1 top3=1 strong=0
      合算: n=3+1-1=3, top3=2+0-1=1, strong=0
      n=3 < 5 → 全 rate は None
    """
    feat = features.compute_relation_features(
        jockey_code="J_B",
        trainer_code=None,
        cutoff_date="2024-08-15",
        history_cache=synthetic_cache,
        snapshot_root=snapshot_root_with_2024_07,
    )
    assert feat["jockey_choku_n"] == 3
    assert feat["jockey_choku_top3_rate"] is None
    assert feat["jockey_choku_strong_rate"] is None


# ----------------------------------------------------------------------------
# (c) §8.2 同月内リーク防止: 2024-07 snapshot 単独では月内ラッパが入らない
# ----------------------------------------------------------------------------

def test_no_intra_month_leak_with_delta_aggregation(
    synthetic_cache, snapshot_root_with_2024_07
):
    """cutoff='2024-08-04' (Race C 当日) では Race C は含まれない (cutoff当日除外)。

    内訳 J_A:
      base: A+B+D = n=5 top3=4 strong=1
      delta (2024-08-01~2024-08-03): なし → n=0
      expired (2022-08-01~2022-08-15, cutoff_2y=2022-08-05): A+D 含むか?
        cutoff_2y = 2024-08-04 - 730 days = 2022-08-05
        expired range = [2022-08-01, 2022-08-05) → empty? D は 2022-08-10 で範囲外
      合算: n=5 top3=4 strong=1
    """
    feat = features.compute_relation_features(
        jockey_code="J_A",
        trainer_code=None,
        cutoff_date="2024-08-04",
        history_cache=synthetic_cache,
        snapshot_root=snapshot_root_with_2024_07,
    )
    # cutoff当日除外: Race C は含まれない
    assert feat["jockey_choku_n"] == 5  # base そのまま


def test_intra_month_delta_includes_only_pre_cutoff(
    synthetic_cache, snapshot_root_with_2024_07
):
    """cutoff='2024-08-05' なら Race C (2024-08-04) は delta に含まれる"""
    feat = features.compute_relation_features(
        jockey_code="J_A",
        trainer_code=None,
        cutoff_date="2024-08-05",
        history_cache=synthetic_cache,
        snapshot_root=snapshot_root_with_2024_07,
    )
    # base 5 + delta(C: J_A=2) - expired(0) = 7
    assert feat["jockey_choku_n"] == 7


# ----------------------------------------------------------------------------
# (d) None 入力 / 不在 actor の挙動
# ----------------------------------------------------------------------------

def test_none_jockey_and_trainer_returns_zeros(
    synthetic_cache, snapshot_root_with_2024_07
):
    feat = features.compute_relation_features(
        jockey_code=None,
        trainer_code=None,
        cutoff_date="2024-08-15",
        history_cache=synthetic_cache,
        snapshot_root=snapshot_root_with_2024_07,
    )
    assert feat["jockey_choku_n"] == 0
    assert feat["jockey_choku_top3_rate"] is None
    assert feat["jockey_choku_strong_rate"] is None
    assert feat["trainer_choku_n"] == 0
    assert feat["trainer_choku_top3_rate"] is None
    assert feat["trainer_choku_strong_rate"] is None


def test_unknown_jockey_returns_zero(synthetic_cache, snapshot_root_with_2024_07):
    feat = features.compute_relation_features(
        jockey_code="J_UNKNOWN",
        trainer_code="T_UNKNOWN",
        cutoff_date="2024-08-15",
        history_cache=synthetic_cache,
        snapshot_root=snapshot_root_with_2024_07,
    )
    assert feat["jockey_choku_n"] == 0
    assert feat["trainer_choku_n"] == 0


# ----------------------------------------------------------------------------
# (e) base snapshot 不在エラー
# ----------------------------------------------------------------------------

def test_missing_base_snapshot_raises(synthetic_cache, tmp_path):
    """前月 snapshot がない場合は明示的に FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        features.compute_relation_features(
            jockey_code="J_A",
            trainer_code="T_A",
            cutoff_date="2024-08-15",
            history_cache=synthetic_cache,
            snapshot_root=tmp_path,  # 何もない
        )


# ----------------------------------------------------------------------------
# (return shape) 全6キーが存在する
# ----------------------------------------------------------------------------

EXPECTED_RELATION_KEYS = {
    "jockey_choku_n",
    "jockey_choku_top3_rate",
    "jockey_choku_strong_rate",
    "trainer_choku_n",
    "trainer_choku_top3_rate",
    "trainer_choku_strong_rate",
}


def test_relations_return_keys_stable(synthetic_cache, snapshot_root_with_2024_07):
    feat = features.compute_relation_features(
        jockey_code="J_A",
        trainer_code="T_A",
        cutoff_date="2024-08-15",
        history_cache=synthetic_cache,
        snapshot_root=snapshot_root_with_2024_07,
    )
    assert set(feat.keys()) == EXPECTED_RELATION_KEYS
