# KeibaCICD ドメインモデル設計書

> **策定日**: 2026-02-07
> **策定者**: カカシ（AI相談役）
> **対象**: v4.0 Domain Layer

---

## 🎯 ドメインモデルの目的

競馬予想システムにおけるビジネスロジックとドメイン知識を明確に定義し、以下を実現する：

1. **予想精度の向上**: 正確なビジネスルールに基づく評価
2. **保守性の向上**: ドメイン知識を一元管理
3. **再利用性**: 複数のユースケースで同じロジックを利用
4. **テスタビリティ**: ドメインロジックを独立してテスト可能

---

## 📦 エンティティ（Entities）

### 1. Training（調教）

**責務**: 調教データの評価とビジネスルール

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Training:
    """
    調教エンティティ

    1頭の馬の1回の調教データを表す。
    評価ロジック（好タイム、ラップ分類など）を内包。
    """
    # 基本属性
    date: str              # 調教日（YYYYMMDD）
    time: str              # 調教時刻（HHMM）
    horse_id: str          # 馬ID（JRA-VAN 10桁）
    center: str            # トレセン（"美浦" or "栗東"）
    location: str          # 場所（"坂路" or "コース"）

    # タイムデータ
    time_4f: float         # 4Fタイム（秒）
    time_3f: float         # 3Fタイム（秒）
    time_2f: float         # 2Fタイム（秒）

    # ラップデータ
    lap_1: float           # 最後の1F（秒）
    lap_2: float           # ラップ2F-1F（秒）
    lap_3: float           # ラップ3F-2F（秒）
    lap_4: float           # ラップ4F-3F（秒）

    # 設定
    config: 'TrainingConfig'

    # ビジネスルール
    @property
    def is_good_time(self) -> bool:
        """
        好タイム判定

        Returns:
            True: 基準値より速い（好タイム）
            False: 基準値以下
        """
        return self.time_4f < self.config.good_time_threshold

    @property
    def acceleration(self) -> str:
        """
        加速評価

        lap_1とlap_2を比較し、加速・減速・同タイムを判定

        Returns:
            "+": 加速（lap_1 < lap_2）
            "=": 同タイム（lap_1 == lap_2）
            "-": 減速（lap_1 > lap_2）
        """
        if self.lap_1 < self.lap_2:
            return "+"
        elif self.lap_1 > self.lap_2:
            return "-"
        else:
            return "="

    @property
    def lap_class(self) -> str:
        """
        ラップ分類（S/A/B/C/D + 加速記号）

        基準値からの差分に基づいて評価

        Returns:
            "S+", "A-", "B=", etc.
        """
        base_lap = self.config.base_lap
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
        """
        SS昇格判定

        好タイム + S分類 + (加速 or 同タイム) → SS

        Returns:
            "SS" or lap_class
        """
        if not self.is_good_time:
            return self.lap_class

        if self.lap_class in ("S+", "S="):
            return "SS"

        return self.lap_class

    @property
    def speed_class(self) -> str:
        """
        スピード分類（S/A/B/C/D）

        4Fタイムに基づく絶対評価

        Returns:
            "S", "A", "B", "C", "D"
        """
        threshold = self.config.good_time_threshold

        if self.time_4f < threshold - 2.0:
            return "S"
        elif self.time_4f < threshold:
            return "A"
        elif self.time_4f < threshold + 2.0:
            return "B"
        elif self.time_4f < threshold + 4.0:
            return "C"
        else:
            return "D"

    def to_dict(self) -> dict:
        """辞書形式に変換（JSON出力用）"""
        return {
            "date": self.date,
            "time": self.time,
            "horse_id": self.horse_id,
            "center": self.center,
            "location": self.location,
            "time_4f": self.time_4f,
            "lap_1": self.lap_1,
            "speed_class": self.speed_class,
            "lap_class": self.lap_class,
            "upgraded_lap_class": self.upgraded_lap_class,
            "is_good_time": self.is_good_time,
        }
```

---

### 2. Horse（馬）

**責務**: 馬の情報と履歴管理

```python
from dataclasses import dataclass
from typing import List

@dataclass
class Horse:
    """
    馬エンティティ

    1頭の馬の基本情報と履歴を管理
    """
    # 基本属性
    horse_id: str          # 馬ID（JRA-VAN 10桁）
    name: str              # 馬名
    age: int               # 年齢
    sex: str               # 性別（"牡", "牝", "せん"）
    trainer: str           # 調教師名
    trainer_location: str  # 調教師所属（"美浦" or "栗東"）

    # 履歴（遅延ロード）
    _trainings: List[Training] = None
    _race_results: List['RaceResult'] = None

    def get_recent_trainings(self, days: int = 14) -> List[Training]:
        """
        直近の調教履歴を取得

        Args:
            days: 遡る日数

        Returns:
            直近の調教リスト（新しい順）
        """
        # 実装省略（リポジトリから取得）
        ...

    def get_training_pattern(self) -> 'TrainingPattern':
        """
        調教パターンを取得

        直近3回の調教（最終、土日、1週前）を分析

        Returns:
            TrainingPattern
        """
        trainings = self.get_recent_trainings(14)
        final = trainings[0] if len(trainings) > 0 else None
        weekend = self._find_weekend_training(trainings)
        week_ago = self._find_week_ago_training(trainings)

        return TrainingPattern(
            final=final,
            weekend=weekend,
            week_ago=week_ago
        )

    def get_race_history(self, limit: int = 5) -> List['RaceResult']:
        """
        出走履歴を取得

        Args:
            limit: 取得件数

        Returns:
            直近の出走結果リスト
        """
        # 実装省略
        ...
```

---

### 3. Race（レース）

**責務**: レース情報と出走馬の管理

```python
from dataclasses import dataclass
from typing import List
from datetime import date

@dataclass
class Race:
    """
    レースエンティティ

    1つのレースの情報と出走馬を管理
    """
    # 基本属性
    race_id: str           # レースID（JRA-VAN 16桁）
    date: date             # 開催日
    track: str             # 競馬場（"東京", "中山", etc.）
    race_number: int       # レース番号（1-12）
    race_name: str         # レース名
    grade: str             # グレード（"G1", "G2", "G3", "OP", "L", ""）

    # レース条件
    distance: int          # 距離（メートル）
    surface: str           # 馬場（"芝", "ダート"）
    track_condition: str   # 馬場状態（"良", "稍重", "重", "不良"）

    # 出走馬
    entries: List['RaceEntry']

    @property
    def is_graded(self) -> bool:
        """重賞レースかどうか"""
        return self.grade in ("G1", "G2", "G3")

    def get_favorites(self, top_n: int = 3) -> List['RaceEntry']:
        """
        人気上位馬を取得

        Args:
            top_n: 取得件数

        Returns:
            人気順の出走馬リスト
        """
        sorted_entries = sorted(self.entries, key=lambda e: e.popularity)
        return sorted_entries[:top_n]

    def get_pace_prediction(self) -> 'Pace':
        """
        ペース予想

        Returns:
            Pace（"H", "M", "S"）
        """
        # 実装省略（逃げ馬の数、距離などから判定）
        ...
```

---

### 4. RaceEntry（出走馬）

**責務**: 1頭の出走情報

```python
@dataclass
class RaceEntry:
    """
    出走馬エンティティ

    レースにおける1頭の馬の情報
    """
    # 基本属性
    horse: Horse           # 馬情報
    gate_number: int       # 枠番
    horse_number: int      # 馬番
    jockey: str            # 騎手名
    weight: float          # 馬体重（kg）
    burden_weight: float   # 負担重量（kg）

    # オッズ（レース確定後に設定）
    odds: float = None     # 単勝オッズ
    popularity: int = None # 人気順位

    # 予想（Domain Serviceで設定）
    prediction: 'Prediction' = None

    @property
    def has_weight_increase(self) -> bool:
        """馬体重が増加しているか"""
        # 前走と比較（実装省略）
        ...
```

---

### 5. Prediction（予想）

**責務**: 1頭の予想結果

```python
@dataclass
class Prediction:
    """
    予想エンティティ

    1頭の馬の予想結果
    """
    entry: RaceEntry       # 出走馬
    win_prob: float        # 勝率（0.0-1.0）
    place_prob: float      # 複勝率（0.0-1.0）
    expected_value: float  # 期待値
    confidence: float      # 信頼度（0.0-1.0）

    # 根拠
    training_score: float  # 調教スコア
    form_score: float      # 馬体調スコア
    pace_score: float      # ペース適性スコア

    @property
    def should_bet(self) -> bool:
        """
        馬券購入推奨かどうか

        期待値 > 1.0 かつ 信頼度 > 0.6

        Returns:
            True: 購入推奨
            False: 見送り
        """
        return self.expected_value > 1.0 and self.confidence > 0.6

    @property
    def bet_type(self) -> str:
        """
        推奨馬券種

        Returns:
            "単勝", "複勝", "馬連", "見送り"
        """
        if self.win_prob > 0.3:
            return "単勝"
        elif self.place_prob > 0.5:
            return "複勝"
        elif self.expected_value > 1.2:
            return "馬連"
        else:
            return "見送り"
```

---

## 🔧 値オブジェクト（Value Objects）

### TrainingConfig（調教評価設定）

```python
@dataclass(frozen=True)
class TrainingConfig:
    """
    調教評価の基準値設定（値オブジェクト）

    トレセンと場所によって基準値が異なる
    """
    center: str            # "美浦" or "栗東"
    location: str          # "坂路" or "コース"
    good_time_threshold: float  # 好タイム基準（秒）
    base_lap: float        # ラップ基準値（秒）
    lap_s_threshold: float # S評価の閾値
    lap_a_threshold: float # A評価の閾値
    lap_b_threshold: float # B評価の閾値

    @classmethod
    def for_miho_slope(cls) -> 'TrainingConfig':
        """美浦坂路の基準値"""
        return cls(
            center="美浦",
            location="坂路",
            good_time_threshold=52.9,
            base_lap=13.4,
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
            base_lap=13.4,
            lap_s_threshold=1.5,
            lap_a_threshold=0.5,
            lap_b_threshold=0.0,
        )
```

### TrainingPattern（調教パターン）

```python
@dataclass
class TrainingPattern:
    """
    調教パターン（値オブジェクト）

    直近3回の調教（最終、土日、1週前）
    """
    final: Training        # 最終追切
    weekend: Training      # 土日追切
    week_ago: Training     # 1週前追切

    @property
    def has_all(self) -> bool:
        """3回とも揃っているか"""
        return all([self.final, self.weekend, self.week_ago])

    @property
    def is_improving(self) -> bool:
        """調教が良化しているか"""
        if not self.has_all:
            return False
        # 最終が最も良い評価
        return self.final.upgraded_lap_class >= self.weekend.upgraded_lap_class
```

---

## 🏢 ドメインサービス（Domain Services）

エンティティ単独では表現できないビジネスロジックを実装

### 1. TrainingEvaluationService

**責務**: 調教パターンの総合評価

```python
class TrainingEvaluationService:
    """
    調教評価ドメインサービス

    複数の調教データから総合評価を行う
    """

    def evaluate_training_pattern(
        self,
        pattern: TrainingPattern
    ) -> 'TrainingEvaluation':
        """
        調教パターンを評価

        Args:
            pattern: 調教パターン（最終、土日、1週前）

        Returns:
            TrainingEvaluation
        """
        if not pattern.has_all:
            return TrainingEvaluation(
                score=0.0,
                rank="不明",
                comment="データ不足"
            )

        # 最終追切の評価
        final_score = self._calculate_score(pattern.final)

        # 継続性の評価
        consistency = self._evaluate_consistency(pattern)

        # 総合スコア
        total_score = final_score * 0.6 + consistency * 0.4

        return TrainingEvaluation(
            score=total_score,
            rank=self._score_to_rank(total_score),
            comment=self._generate_comment(pattern)
        )

    def _calculate_score(self, training: Training) -> float:
        """1回の調教をスコア化（0.0-1.0）"""
        # SS=1.0, S+=0.9, S==0.85, S-=0.8, ...
        class_score_map = {
            "SS": 1.0,
            "S+": 0.9,
            "S=": 0.85,
            "S-": 0.8,
            "A+": 0.7,
            "A=": 0.65,
            "A-": 0.6,
            # ... 省略
        }
        return class_score_map.get(training.upgraded_lap_class, 0.5)

    def _evaluate_consistency(self, pattern: TrainingPattern) -> float:
        """継続性の評価（0.0-1.0）"""
        # 3回とも良い評価が続いているか
        scores = [
            self._calculate_score(pattern.final),
            self._calculate_score(pattern.weekend),
            self._calculate_score(pattern.week_ago)
        ]
        return sum(scores) / len(scores)
```

---

### 2. RacePredictionService

**責務**: レース予想の生成

```python
class RacePredictionService:
    """
    レース予想ドメインサービス

    レース全体の予想を生成
    """

    def __init__(
        self,
        training_eval_service: TrainingEvaluationService
    ):
        self.training_eval_service = training_eval_service

    def predict_race(self, race: Race) -> List[Prediction]:
        """
        レース予想

        Args:
            race: レース情報

        Returns:
            全出走馬の予想リスト
        """
        predictions = []

        for entry in race.entries:
            # 調教評価
            training_pattern = entry.horse.get_training_pattern()
            training_eval = self.training_eval_service.evaluate_training_pattern(
                training_pattern
            )

            # 馬体調評価
            form_score = self._evaluate_form(entry)

            # ペース適性
            pace = race.get_pace_prediction()
            pace_score = self._evaluate_pace_suitability(entry, pace)

            # 総合勝率計算
            win_prob = self._calculate_win_probability(
                training_score=training_eval.score,
                form_score=form_score,
                pace_score=pace_score
            )

            # 期待値計算
            expected_value = win_prob * entry.odds

            prediction = Prediction(
                entry=entry,
                win_prob=win_prob,
                place_prob=win_prob * 3,  # 簡易計算
                expected_value=expected_value,
                confidence=self._calculate_confidence(training_eval),
                training_score=training_eval.score,
                form_score=form_score,
                pace_score=pace_score
            )
            predictions.append(prediction)

        return predictions

    def get_top_picks(
        self,
        predictions: List[Prediction],
        top_n: int = 3
    ) -> List[Prediction]:
        """
        本命馬を取得

        Args:
            predictions: 全予想
            top_n: 取得件数

        Returns:
            勝率上位の予想リスト
        """
        sorted_predictions = sorted(
            predictions,
            key=lambda p: p.win_prob,
            reverse=True
        )
        return sorted_predictions[:top_n]
```

---

### 3. ExpectedValueCalculator

**責務**: 期待値計算

```python
class ExpectedValueCalculator:
    """
    期待値計算ドメインサービス

    オッズと勝率から期待値を計算
    """

    def calculate(
        self,
        win_prob: float,
        odds: float
    ) -> float:
        """
        期待値計算

        Args:
            win_prob: 勝率（0.0-1.0）
            odds: オッズ

        Returns:
            期待値（1.0以上なら投資価値あり）
        """
        return win_prob * odds

    def should_bet(
        self,
        win_prob: float,
        odds: float,
        min_ev: float = 1.0
    ) -> bool:
        """
        馬券購入推奨判定

        Args:
            win_prob: 勝率
            odds: オッズ
            min_ev: 最低期待値（デフォルト1.0）

        Returns:
            True: 購入推奨
        """
        ev = self.calculate(win_prob, odds)
        return ev >= min_ev
```

---

## 📋 ビジネスルール一覧

### 1. 好タイム基準

| トレセン | 場所 | 基準値 |
|---------|------|--------|
| 美浦 | 坂路 | 52.9秒 |
| 栗東 | 坂路 | 52.9秒 |
| 美浦 | コース | 53.0秒 |
| 栗東 | コース | 53.0秒 |

### 2. ラップ分類基準

| 評価 | 条件 |
|------|------|
| S | 基準値 - 1.5秒以下 |
| A | 基準値 - 0.5秒以下 |
| B | 基準値 ± 0秒 |
| C | 基準値 + 0.5秒以下 |
| D | 基準値 + 0.5秒超 |

### 3. SS昇格条件

```
好タイム AND (S+ OR S=) → SS
```

### 4. 期待値計算式

```
期待値 = 勝率 × オッズ
```

### 5. 馬券購入推奨条件

```
期待値 > 1.0 AND 信頼度 > 0.6
```

---

## 🔄 ドメインイベント（Domain Events）

将来的な拡張のためにイベント駆動アーキテクチャを検討

```python
@dataclass
class TrainingRecorded:
    """調教が記録された"""
    horse_id: str
    training: Training
    timestamp: datetime

@dataclass
class RacePredicted:
    """レースが予想された"""
    race_id: str
    predictions: List[Prediction]
    timestamp: datetime

@dataclass
class BetPlaced:
    """馬券が購入された"""
    race_id: str
    horse_number: int
    bet_type: str
    amount: int
    timestamp: datetime
```

---

## 📚 参考文献

- Eric Evans『ドメイン駆動設計』
- Vaughn Vernon『実践ドメイン駆動設計』
- Martin Fowler『リファクタリング』

---

**更新履歴**:
- 2026-02-07: 初版作成（カカシ）
