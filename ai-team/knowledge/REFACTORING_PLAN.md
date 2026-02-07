# KeibaCICD リファクタリング計画書

> **策定日**: 2026-02-07
> **策定者**: カカシ（AI相談役）
> **対象**: v3.1 → v4.0への段階的移行

---

## 🎯 基本方針

### 原則

1. **既存コードを壊さない**: 新旧両方が動く期間を設ける
2. **段階的移行**: 一度に全てを変更しない
3. **テストで検証**: 各Phaseで動作確認
4. **ロールバック可能**: 問題が出たら元に戻せる

### 戦略

- **Strangler Fig Pattern**: 新しいコードで古いコードを徐々に置き換える
- **Feature Flag**: 新機能をON/OFFできるようにする
- **並行稼働**: 新旧ロジックを並行して動かし、結果を比較

---

## 📅 全体スケジュール

| Phase | 期間 | バージョン | 主な作業 | 工数 |
|-------|------|-----------|---------|------|
| Phase 0 | 2026/02 | v3.1 | ドキュメント整備 | 2日 |
| Phase 1 | 2026/03 | v3.2 | Domain層抽出 | 5日 |
| Phase 2 | 2026/04 | v3.3 | Application層整備 | 7日 |
| Phase 3 | 2026/05 | v3.4 | Infrastructure整理 | 5日 |
| Phase 4 | 2026/06 | v4.0 | ML導入 | 10日 |
| Phase 5 | 2026/07 | v4.1 | MCP連携 | 5日 |

**合計**: 約34日（実作業日）

---

## 📝 Phase 0: ドキュメント整備（v3.1）

### 目的

将来の方向性を明確にし、段階的移行の土台を作る

### 作業内容

- [x] ARCHITECTURE_V4.md作成（v4.0設計ビジョン）
- [x] REFACTORING_PLAN.md作成（本ドキュメント）
- [ ] DOMAIN_MODEL.md作成（ドメインモデル設計）
- [ ] UPGRADE_PLAN.mdに追記（v3.1以降の計画）

### 成果物

- 3つのドキュメント
- チーム（将来的に）への説明資料

### 完了条件

- ✅ 全ドキュメントが作成されている
- ✅ 他のドキュメント（ARCHITECTURE.md等）と整合性がある

---

## 🏗️ Phase 1: Domain層抽出（v3.2）

### 目的

評価ロジックをInfrastructure層から分離し、テスト可能にする

### 作業内容（詳細）

#### 1.1 ディレクトリ構造作成

```bash
mkdir -p keiba-cicd-core/KeibaCICD.Domain/training
mkdir -p keiba-cicd-core/KeibaCICD.Domain/race
mkdir -p keiba-cicd-core/KeibaCICD.Domain/common
```

#### 1.2 TrainingConfig作成

**ファイル**: `KeibaCICD.Domain/training/config.py`

```python
from dataclasses import dataclass

@dataclass
class TrainingConfig:
    """調教評価の基準値設定"""
    center: str  # "美浦" or "栗東"
    location: str  # "坂路" or "コース"

    # 好タイム基準（秒）
    good_time_threshold: float

    # ラップ分類の基準（秒）
    lap_s_threshold: float  # S評価の基準（基準値 - この値）
    lap_a_threshold: float  # A評価の基準
    lap_b_threshold: float  # B評価の基準

    @classmethod
    def for_miho_slope(cls) -> 'TrainingConfig':
        """美浦坂路の基準値"""
        return cls(
            center="美浦",
            location="坂路",
            good_time_threshold=52.9,
            lap_s_threshold=1.5,
            lap_a_threshold=0.5,
            lap_b_threshold=0.0,
        )

    @classmethod
    def for_ritto_slope(cls) -> 'TrainingConfig':
        """栗東坂路の基準値"""
        return cls(
            center="栗東",
            location="坂路",
            good_time_threshold=52.9,
            lap_s_threshold=1.5,
            lap_a_threshold=0.5,
            lap_b_threshold=0.0,
        )
```

#### 1.3 Training Entity作成

**ファイル**: `KeibaCICD.Domain/training/training.py`

```python
from dataclasses import dataclass
from .config import TrainingConfig

@dataclass
class Training:
    """調教エンティティ（ビジネスロジック含む）"""
    date: str
    time: str
    horse_id: str
    center: str
    location: str
    time_4f: float
    time_3f: float
    time_2f: float
    lap_1: float
    lap_2: float
    lap_3: float
    lap_4: float
    config: TrainingConfig

    @property
    def is_good_time(self) -> bool:
        """好タイム判定"""
        return self.time_4f < self.config.good_time_threshold

    @property
    def acceleration(self) -> str:
        """加速評価（+/=/−）"""
        if self.lap_1 < self.lap_2:
            return "+"  # 加速
        elif self.lap_1 > self.lap_2:
            return "-"  # 減速
        else:
            return "="  # 同じ

    @property
    def lap_class(self) -> str:
        """ラップ分類（S/A/B/C/D + 加速記号）"""
        # 基準値相対ロジック
        base_lap = 13.4  # 美浦坂路の場合
        diff = base_lap - self.lap_1

        if diff >= self.config.lap_s_threshold:
            rank = "S"
        elif diff >= self.config.lap_a_threshold:
            rank = "A"
        elif diff >= self.config.lap_b_threshold:
            rank = "B"
        elif diff >= -0.5:
            rank = "C"
        else:
            rank = "D"

        return rank + self.acceleration

    @property
    def upgraded_lap_class(self) -> str:
        """SS昇格判定"""
        if not self.is_good_time:
            return self.lap_class

        # S+ or S= の場合のみSS昇格
        if self.lap_class in ("S+", "S="):
            return "SS"

        return self.lap_class

    @property
    def speed_class(self) -> str:
        """スピード分類（S/A/B/C/D）"""
        # タイム4Fに基づく評価
        if self.time_4f < self.config.good_time_threshold - 2.0:
            return "S"
        elif self.time_4f < self.config.good_time_threshold:
            return "A"
        elif self.time_4f < self.config.good_time_threshold + 2.0:
            return "B"
        elif self.time_4f < self.config.good_time_threshold + 4.0:
            return "C"
        else:
            return "D"
```

#### 1.4 既存コードの修正（段階的移行）

**ファイル**: `KeibaCICD.TARGET/scripts/parse_ck_data.py`

```python
# 新Domain層をインポート（オプション）
try:
    from KeibaCICD.Domain.training.training import Training as DomainTraining
    from KeibaCICD.Domain.training.config import TrainingConfig
    USE_DOMAIN_LAYER = True
except ImportError:
    USE_DOMAIN_LAYER = False
    print("[parse_ck_data] Domain layer not available, using legacy logic")

@dataclass
class TrainingRecord:
    """既存のクラス（互換性のため残す）"""
    date: str
    time: str
    horse_id: str
    center: str
    location: str
    time_4f: float
    # ... 他のフィールド

    @property
    def upgraded_lap_class(self) -> str:
        """SS昇格判定（新Domain層を使う）"""
        if USE_DOMAIN_LAYER:
            # 新Domain層を使用
            config = TrainingConfig.for_miho_slope() if self.center == "美浦" else TrainingConfig.for_ritto_slope()
            domain_training = DomainTraining(
                date=self.date,
                time=self.time,
                horse_id=self.horse_id,
                center=self.center,
                location=self.location,
                time_4f=self.time_4f,
                time_3f=self.time_3f,
                time_2f=self.time_2f,
                lap_1=self.lap_1,
                lap_2=self.lap_2,
                lap_3=self.lap_3,
                lap_4=self.lap_4,
                config=config
            )
            return domain_training.upgraded_lap_class

        # フォールバック：既存のロジック
        if not self.is_good_time:
            return self.lap_class
        if self.lap_class in ("S+", "S="):
            return "SS"
        return self.lap_class
```

#### 1.5 単体テスト作成

**ファイル**: `KeibaCICD.Domain/tests/test_training.py`

```python
import pytest
from KeibaCICD.Domain.training.training import Training
from KeibaCICD.Domain.training.config import TrainingConfig

def test_is_good_time():
    """好タイム判定のテスト"""
    config = TrainingConfig.for_miho_slope()
    training = Training(
        date="20260207",
        time="0800",
        horse_id="2023103073",
        center="美浦",
        location="坂路",
        time_4f=52.0,  # 好タイム
        time_3f=39.0,
        time_2f=26.0,
        lap_1=11.8,
        lap_2=12.2,
        lap_3=13.0,
        lap_4=13.0,
        config=config
    )
    assert training.is_good_time == True

def test_ss_upgrade():
    """SS昇格判定のテスト"""
    config = TrainingConfig.for_miho_slope()
    training = Training(
        date="20260207",
        time="0800",
        horse_id="2023103073",
        center="美浦",
        location="坂路",
        time_4f=52.0,  # 好タイム
        time_3f=39.0,
        time_2f=26.0,
        lap_1=11.8,  # S評価
        lap_2=12.2,  # 加速
        lap_3=13.0,
        lap_4=13.0,
        config=config
    )
    assert training.upgraded_lap_class == "SS"
```

### チェックリスト

- [ ] ディレクトリ構造作成
- [ ] TrainingConfig実装
- [ ] Training Entity実装
- [ ] 既存コードに新Domain層を統合
- [ ] 単体テスト作成（pytest）
- [ ] 既存テストが全てパス
- [ ] generate_training_summary.pyで動作確認
- [ ] WebViewerで表示確認

### 完了条件

- ✅ 全単体テストがパス
- ✅ 既存テストがパス（後方互換性確保）
- ✅ training_summary.jsonの出力が変わらない

### ロールバック手順

```python
# parse_ck_data.py で USE_DOMAIN_LAYER = False に設定
USE_DOMAIN_LAYER = False
```

---

## 📦 Phase 2: Application層整備（v3.3）

### 目的

ユースケースを明確化し、データフロー制御を集約

### 作業内容

#### 2.1 ディレクトリ構造作成

```bash
mkdir -p keiba-cicd-core/KeibaCICD.Application/use_cases
mkdir -p keiba-cicd-core/KeibaCICD.Application/ml
mkdir -p keiba-cicd-core/KeibaCICD.Application/mcp
```

#### 2.2 GenerateTrainingSummaryUseCase作成

**ファイル**: `KeibaCICD.Application/use_cases/training_summary.py`

```python
from dataclasses import dataclass
from typing import List, Dict
from KeibaCICD.Domain.training.training import Training
from KeibaCICD.TARGET.scripts.parse_ck_data import parse_ck_file

@dataclass
class TrainingSummaryDTO:
    """調教サマリのデータ転送オブジェクト"""
    horse_name: str
    final_lap: str
    final_speed: str
    detail: str

class GenerateTrainingSummaryUseCase:
    """調教サマリ生成ユースケース"""

    def execute(self, race_date: str) -> List[TrainingSummaryDTO]:
        """
        調教サマリを生成

        Args:
            race_date: レース日付（YYYY-MM-DD）

        Returns:
            調教サマリのリスト
        """
        # 1. Infrastructure: CK_DATAをパース
        ck_files = self._get_ck_files(race_date)
        raw_records = []
        for file in ck_files:
            raw_records.extend(parse_ck_file(file))

        # 2. Domain: 調教評価
        trainings = self._to_domain_trainings(raw_records)

        # 3. Application: サマリ生成
        summaries = self._generate_summaries(trainings)

        return summaries

    def _to_domain_trainings(self, raw_records) -> List[Training]:
        """生レコードをDomain Entityに変換"""
        # ... 実装 ...

    def _generate_summaries(self, trainings) -> List[TrainingSummaryDTO]:
        """調教からサマリを生成"""
        # ... 実装 ...
```

#### 2.3 CLIから呼び出す

**ファイル**: `KeibaCICD.TARGET/scripts/generate_training_summary.py`（既存を修正）

```python
# 新Application層をインポート
try:
    from KeibaCICD.Application.use_cases.training_summary import GenerateTrainingSummaryUseCase
    USE_APPLICATION_LAYER = True
except ImportError:
    USE_APPLICATION_LAYER = False

def main():
    """メイン処理"""
    if USE_APPLICATION_LAYER:
        # 新Application層を使用
        use_case = GenerateTrainingSummaryUseCase()
        summaries = use_case.execute(race_date)
        save_json(summaries)
    else:
        # 既存のロジック
        legacy_generate_summary(race_date)
```

### チェックリスト

- [ ] Application層ディレクトリ作成
- [ ] GenerateTrainingSummaryUseCase実装
- [ ] CLIから呼び出し
- [ ] 出力JSONが同一であることを確認
- [ ] パフォーマンス測定（劣化がないこと）

### 完了条件

- ✅ 新旧ロジックの出力が100%一致
- ✅ パフォーマンス劣化なし（±10%以内）

---

## 🔧 Phase 3: Infrastructure整理（v3.4）

### 目的

Infrastructure層をパース専念に変更し、評価ロジックをDomain層に完全移譲

### 作業内容

#### 3.1 parse_ck_data.pyの整理

```python
# 評価ロジックを全てDomain層に移譲
# TrainingRecordはRawTrainingRecordに名称変更

@dataclass
class RawTrainingRecord:
    """パース結果（評価なし）"""
    date: str
    time: str
    horse_id: str
    center: str
    location: str
    time_4f: float
    time_3f: float
    time_2f: float
    lap_1: float
    lap_2: float
    lap_3: float
    lap_4: float

    # プロパティは全て削除（Domain層に移譲）
```

#### 3.2 レガシーコード削除

- [ ] TrainingRecordのプロパティ削除
- [ ] 評価ロジック削除
- [ ] 未使用関数削除

### 完了条件

- ✅ parse_ck_data.pyがパース専念になっている
- ✅ 全てのテストがパス

---

## 🤖 Phase 4: ML導入（v4.0）

### 目的

機械学習モデルを統合し、予想精度を向上

### 作業内容

#### 4.1 TrainingMLModel作成

**ファイル**: `KeibaCICD.Application/ml/training_model.py`

```python
import lightgbm as lgb
from typing import List

class TrainingMLModel:
    """調教ML予測モデル"""

    def __init__(self):
        self.model = None

    def train(self, features, labels):
        """モデル訓練"""
        self.model = lgb.LGBMClassifier()
        self.model.fit(features, labels)

    def predict(self, trainings: List[Training]) -> List[float]:
        """勝率予測"""
        features = self._extract_features(trainings)
        return self.model.predict_proba(features)[:, 1]
```

### チェックリスト

- [ ] LightGBMインストール
- [ ] TrainingMLModel実装
- [ ] 訓練データ作成
- [ ] モデル訓練
- [ ] 精度評価（AUC >= 0.7）

---

## 🔌 Phase 5: MCP連携（v4.1）

### 目的

LLMに予想補助を依頼し、説明可能性を向上

### 作業内容

- [ ] MCP Serverセットアップ
- [ ] LLMPredictionAssistant実装
- [ ] WebViewerにLLM予想を表示

---

## ⚠️ リスク管理

| リスク | 影響 | 対策 |
|-------|------|------|
| 既存機能の破壊 | 高 | 並行稼働 + テスト |
| パフォーマンス劣化 | 中 | ベンチマーク測定 |
| スケジュール遅延 | 中 | Phase単位でリリース |
| チーム理解不足 | 低 | ドキュメント整備 |

---

## 📊 進捗管理

### KPI

- **コードカバレッジ**: 80%以上
- **テスト成功率**: 100%
- **パフォーマンス**: ±10%以内
- **バグ発生率**: 月5件以下

---

**更新履歴**:
- 2026-02-07: 初版作成（カカシ）
