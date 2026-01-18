# PCI分析とレース印

## 1. PCI（ペースチェンジ指数）とは

### 1.1 定義

**PCI = Pace Change Index（ペースチェンジ指数）**

上がり3ハロン（残り600m）を分岐点として、**前半と後半の速度変化を数値化**したもの。

```
PCI = 後半速度 / 前半速度 × 50（調整済み）
```

### 1.2 数値の意味

| PCI値 | 意味 | ペース傾向 |
|:---:|:---|:---|
| **< 50** | 後半が遅くなった | 前傾ラップ（ハイペース） |
| **≒ 50** | 前後半が同程度 | 平均ペース |
| **> 50** | 後半が速くなった | 後傾ラップ（スローペース） |

### 1.3 具体例

| PCI | 解釈 |
|:---:|:---|
| 40 | 前半飛ばして後半バテた（ハイペース逃げ馬など） |
| 50 | 一定ペースで走り切った |
| 60 | 道中脚を溜めて直線で加速（差し・追込馬など） |

---

## 2. PCI関連指標

### 2.1 PCI3（レースペース指標）

**定義**: そのレースの**上位3頭（入線順）のPCI平均値**

| PCI3値 | レース特性 |
|:---:|:---|
| **低い（< 48）** | 前傾ラップ → 先行有利レース |
| **中間（48-52）** | 平均ペース → 展開次第 |
| **高い（> 52）** | 後傾ラップ → 差し追込有利レース |

**活用**: レースのペースを客観的に評価できる

### 2.2 RPCI（レースラップPCI）

**定義**: レース全体のラップタイムから算出したPCI

- 個別馬のPCIではなく、レース自体のペースを表す
- ラップタイムが公開されているレースで利用可能

---

## 3. レース分類への活用

### 3.1 PCI × 着順 マトリクス

PCIと着順を組み合わせてレースの特性を分類：

| 着順＼PCI | 低PCI（< 48） | 中PCI（48-52） | 高PCI（> 52） |
|:---:|:---:|:---:|:---:|
| **上位着** | 前傾で粘り切り | 平均ペース好走 | スロー直線勝負 |
| **中位着** | 前傾に巻き込まれ | 凡走 | 届かず |
| **下位着** | バテ | 完敗 | 追走できず |

### 3.2 レース特性パターン

#### パターン A: 前傾ラップレース

```
特徴:
- PCI3 < 48
- 先行馬のPCIが低い（40前後）
- 差し馬のPCIが高め
- 前残り or 差し届く の二極化

評価対象:
- 上位入線の先行馬 → タフさ評価◎
- 追い込んできた馬 → 展開向いた△
- バテた先行馬 → ペース判断要注意
```

#### パターン B: スローの上がり勝負

```
特徴:
- PCI3 > 52
- 逃げ馬のPCIも高め
- 上位馬のPCIが揃って高い
- 上がり3F勝負

評価対象:
- 差し切った馬 → 末脚評価◎
- 前で粘った馬 → 位置取りの巧さ◎
- 届かなかった馬 → 展開不利△
```

#### パターン C: 平均ペース

```
特徴:
- PCI3 ≒ 50
- 各馬のPCIに大きなバラつきなし
- 実力通りの結果が出やすい

評価対象:
- 上位馬 → 能力評価◎
- 下位馬 → 能力不足
```

#### パターン D: 極端なハイペース崩れ

```
特徴:
- PCI3は高いが、先行馬のPCIが極端に低い
- 逃げ馬が大敗（PCI < 40）
- 差し追込が上位独占

評価対象:
- 差し切った馬 → 展開利あり△
- バテた先行馬 → 次走狙い目◎
- 出遅れ馬 → 結果オーライ
```

---

## 4. レース印への反映

### 4.1 レース印の構成

TARGETでは**レース印1～3**の3つを設定可能。

| レース印 | 用途案 | 設定タイミング |
|:---|:---|:---|
| **レース印1** | レースペース分類 | レース後 |
| **レース印2** | 展開評価 | レース後 |
| **レース印3** | 予想用フラグ | レース前 |

### 4.2 レース印1: ペース分類記号

| 記号 | 意味 | 条件 |
|:---:|:---|:---|
| **H** | ハイペース | PCI3 < 46 |
| **h** | やや前傾 | PCI3: 46-48 |
| **M** | 平均ペース | PCI3: 48-52 |
| **s** | ややスロー | PCI3: 52-54 |
| **S** | スローペース | PCI3 > 54 |

### 4.3 レース印2: 展開パターン

| 記号 | 意味 | 説明 |
|:---:|:---|:---|
| **前** | 前残り | 先行馬が上位独占 |
| **差** | 差し決着 | 差し追込が上位独占 |
| **混** | 混戦 | 先行・差し混在 |
| **崩** | ペース崩壊 | 先行馬総崩れ |
| **逃** | 逃げ切り | 逃げ馬が勝利 |

### 4.4 判定ロジック例

```python
def classify_race(pci3, winner_pci, winner_position):
    """
    レースを分類してレース印を返す
    
    Args:
        pci3: 上位3頭のPCI平均
        winner_pci: 勝ち馬のPCI
        winner_position: 勝ち馬の4角位置（1=先頭、2=好位...）
    
    Returns:
        (pace_mark, pattern_mark): レース印1, レース印2
    """
    # ペース分類
    if pci3 < 46:
        pace_mark = "H"
    elif pci3 < 48:
        pace_mark = "h"
    elif pci3 < 52:
        pace_mark = "M"
    elif pci3 < 54:
        pace_mark = "s"
    else:
        pace_mark = "S"
    
    # 展開パターン
    if winner_position <= 2 and pci3 < 48:
        pattern_mark = "前"
    elif winner_position <= 2 and pci3 >= 52:
        pattern_mark = "逃"
    elif winner_position >= 5 and pci3 >= 50:
        pattern_mark = "差"
    elif winner_pci < 40 and pci3 > 52:
        pattern_mark = "崩"
    else:
        pattern_mark = "混"
    
    return pace_mark, pattern_mark
```

---

## 5. 活用シナリオ

### 5.1 次走予想への活用

| 前走レース印 | 今回の狙い方 |
|:---|:---|
| **H-崩** | バテた先行馬の巻き返し狙い |
| **S-差** | 届かなかった差し馬の再評価 |
| **M-混** | 素直に実力評価 |
| **H-前** | 前残りした馬の能力信頼 |

### 5.2 コース・条件別傾向分析

```
例: 中山芝2000m
- レース印「S」が多い → スローになりやすいコース
- レース印「差」が多い → 差し有利コース

→ このコースでは差し馬を重視
```

### 5.3 騎手・調教師別傾向

```
例: 武豊騎手
- 騎乗レースのレース印「S」が多い → スローに落とすのが上手い
- 4角1番手でレース印「逃」が多い → 逃げ切り率高い

→ この騎手が逃げるときは信頼度UP
```

---

## 6. 実装計画

### 6.1 データ取得

| データ項目 | 取得元 | 備考 |
|:---|:---|:---|
| 各馬PCI | TARGET/JRA-VAN | 戦歴データに含まれる |
| PCI3 | 算出 | 上位3頭のPCI平均 |
| RPCI | TARGET/JRA-VAN | ラップタイムから算出 |
| 4角位置 | seiseki_*.json | 通過順位から抽出 |

### 6.2 スクリプト構成

```
KeibaCICD.TARGET/scripts/
├── pci_analyzer.py          # PCI分析
├── race_classifier.py       # レース分類
└── race_mark_generator.py   # レース印生成
```

### 6.3 処理フロー

```
1. 成績データ読み込み（seiseki_*.json）
2. 各馬のPCI算出（走破タイム、上り3Fから）
3. PCI3算出
4. レース分類
5. レース印ファイル出力（TARGET取り込み形式）
```

---

## 7. コース・距離別PCI調整値

### 7.1 調整の必要性

PCI参考.csvの分析から、以下の傾向が確認された：

| 条件 | PCI傾向 | 理由 |
|:---|:---|:---|
| **ダート短距離** | 低め（40前後） | ダッシュ力重視、前傾になりやすい |
| **ダート中長距離** | 中程度（45-50） | スタミナ配分が必要 |
| **芝短距離** | やや低め（45-50） | スピード重視 |
| **芝マイル** | 平均（50前後） | バランス型 |
| **芝中長距離** | 高め（50-55） | スローからの瞬発力勝負が多い |

→ **全コース共通の基準値（50）では正確なペース判定ができない**

### 7.2 基準値の設計方針

**3次元マスタ構造**: `競馬場 × コース(芝/ダート) × 距離`

```
pci_standards.json
└── tracks
    └── 東京
        ├── 芝
        │   ├── 1400: { standard, h_threshold, s_threshold }
        │   ├── 1600: { ... }
        │   └── ...
        └── ダート
            ├── 1300: { ... }
            └── ...
```

#### 基準値項目

| 項目 | 説明 |
|:---|:---|
| `standard` | PCI基準値（この値を50に正規化） |
| `h_threshold` | ハイペース判定閾値 |
| `s_threshold` | スローペース判定閾値 |

#### 対象競馬場・コース

| 競馬場 | 芝コース数 | ダートコース数 |
|:---|:---:|:---:|
| 東京 | 8 | 4 |
| 中山 | 7 | 4 |
| 阪神 | 9 | 4 |
| 京都 | 9 | 4 |
| 中京 | 5 | 4 |
| 新潟 | 8 | 2 |
| 小倉 | 5 | 3 |
| 福島 | 4 | 3 |
| 札幌 | 5 | 3 |
| 函館 | 4 | 3 |

**基準値の算出は別途実施予定**（PCI参考.csvなど実データから統計分析）

#### フォールバック値（マスタ未設定時）

| コース | 距離帯 | 仮基準値 |
|:---|:---|:---:|
| 芝 | 短距離(〜1400m) | 48 |
| 芝 | マイル(〜1800m) | 50 |
| 芝 | 中距離(〜2200m) | 52 |
| 芝 | クラシック(〜2600m) | 53 |
| 芝 | 長距離(2600m〜) | 55 |
| ダート | 短距離(〜1400m) | 45 |
| ダート | マイル(〜1800m) | 47 |
| ダート | 中距離(1800m〜) | 50 |

### 7.3 基準値の取得ロジック

```python
import json
from pathlib import Path

class PCIStandardManager:
    """競馬場・コース・距離別PCI基準値管理"""
    
    def __init__(self, json_path: str = "data/pci_standards.json"):
        with open(json_path, encoding="utf-8") as f:
            self.data = json.load(f)
        self.tracks = self.data.get("tracks", {})
        self.fallback = self.data.get("fallback", {})
    
    def get_standard(self, track: str, surface: str, distance: int) -> dict:
        """
        競馬場・コース・距離からPCI基準値を取得
        
        Args:
            track: 競馬場（東京, 中山, ...）
            surface: コース種別（芝, ダート）
            distance: 距離（m）
        
        Returns:
            {"standard": float, "h_threshold": float, "s_threshold": float}
        """
        # マスタから検索
        if track in self.tracks:
            if surface in self.tracks[track]:
                dist_str = str(distance)
                if dist_str in self.tracks[track][surface]:
                    result = self.tracks[track][surface][dist_str]
                    if result.get("standard") is not None:
                        return result
        
        # フォールバック値を使用
        return self._get_fallback(surface, distance)
    
    def _get_fallback(self, surface: str, distance: int) -> dict:
        """フォールバック値を取得"""
        fb = self.fallback.get(surface, {})
        
        for category in ["short", "mile", "middle", "classic", "long"]:
            if category not in fb:
                continue
            cat = fb[category]
            max_d = cat.get("max_distance", 9999)
            min_d = cat.get("min_distance", 0)
            if min_d <= distance <= max_d:
                std = cat["standard"]
                return {
                    "standard": std,
                    "h_threshold": std - 4,
                    "s_threshold": std + 4
                }
        
        return {"standard": 50, "h_threshold": 46, "s_threshold": 54}
    
    def normalize_pci(self, pci: float, track: str, surface: str, distance: int) -> float:
        """PCIを正規化（基準値を50に補正）"""
        std = self.get_standard(track, surface, distance)
        return pci - (std["standard"] - 50)
```

### 7.4 正規化後のペース分類

正規化PCIを使用して、競馬場・コース・距離に依存しないペース分類を行う：

```python
def classify_pace(pci3: float, track: str, surface: str, distance: int, 
                  manager: PCIStandardManager) -> str:
    """
    正規化PCIでペース分類
    
    Args:
        pci3: 上位3頭のPCI平均
        track: 競馬場
        surface: コース種別
        distance: 距離
        manager: PCIStandardManager インスタンス
    
    Returns:
        "H", "h", "M", "s", "S" のいずれか
    """
    norm_pci3 = manager.normalize_pci(pci3, track, surface, distance)
    
    if norm_pci3 < 46:
        return "H"  # ハイペース
    elif norm_pci3 < 48:
        return "h"  # やや前傾
    elif norm_pci3 < 52:
        return "M"  # 平均ペース
    elif norm_pci3 < 54:
        return "s"  # ややスロー
    else:
        return "S"  # スローペース


# 使用例
manager = PCIStandardManager("data/pci_standards.json")

# 東京芝1600m PCI3=52 の場合
pace = classify_pace(52, "東京", "芝", 1600, manager)
# → 基準値が設定されていれば補正後の値で判定
```

### 7.5 マスタファイルの構造

**`data/pci_standards.json`** の構造：

```json
{
  "version": "1.1.0",
  "tracks": {
    "東京": {
      "芝": {
        "1600": { "standard": 51, "h_threshold": 47, "s_threshold": 55 },
        "2400": { "standard": 53, "h_threshold": 49, "s_threshold": 57 }
      },
      "ダート": {
        "1600": { "standard": 47, "h_threshold": 43, "s_threshold": 51 }
      }
    },
    "中山": { ... }
  },
  "fallback": {
    "芝": {
      "short": { "max_distance": 1400, "standard": 48 },
      "mile": { "max_distance": 1800, "standard": 50 },
      ...
    }
  },
  "pace_classification": { ... }
}
```

**ポイント**:
- 競馬場ごとに個別の基準値を設定可能
- マスタ未設定の場合は `fallback` を使用
- 基準値は実データから算出予定（現在は `null`）

### 7.6 基準値の算出方法（別途実施）

実際のレースデータを蓄積し、以下の手順で基準値を算出：

#### 算出手順

1. **データ収集**: TARGETからPCI3データを競馬場・コース・距離別にエクスポート
2. **統計分析**: 競馬場×コース×距離ごとにPCI3の平均・標準偏差を算出
3. **基準値設定**: 平均値を `standard` として設定
4. **閾値設定**: `h_threshold = 平均 - 標準偏差`, `s_threshold = 平均 + 標準偏差`

#### 算出スクリプト例

```python
def calculate_pci_standards(races: list) -> dict:
    """
    実データからPCI基準値を算出
    
    Args:
        races: レースデータリスト
               [{"track": "東京", "surface": "芝", "distance": 1600, "pci3": 51.2}, ...]
    
    Returns:
        pci_standards.json の tracks セクション形式
    """
    from collections import defaultdict
    import statistics
    
    # 競馬場×コース×距離でグルーピング
    grouped = defaultdict(list)
    for r in races:
        key = (r["track"], r["surface"], r["distance"])
        if r.get("pci3") is not None:
            grouped[key].append(r["pci3"])
    
    # 各グループの統計値を算出
    result = {}
    for (track, surface, distance), pci3_list in grouped.items():
        if len(pci3_list) < 10:  # サンプル不足はスキップ
            continue
        
        mean = statistics.mean(pci3_list)
        std = statistics.stdev(pci3_list)
        
        if track not in result:
            result[track] = {}
        if surface not in result[track]:
            result[track][surface] = {}
        
        result[track][surface][str(distance)] = {
            "standard": round(mean, 1),
            "h_threshold": round(mean - std, 1),
            "s_threshold": round(mean + std, 1),
            "sample_count": len(pci3_list)
        }
    
    return result
```

#### データソース

- **PCI参考.csv**: TARGETからエクスポートしたPCIデータ
- 必要カラム: 競馬場、コース種別、距離、PCI3（または上位3頭PCI平均）

---

## 8. 今後の拡張

### 8.1 PCI予測

過去のコース・条件別PCI傾向から、今回レースのPCI予測を行う

### 8.2 馬別PCI傾向

各馬のPCI傾向（高PCI型=差し馬、低PCI型=先行馬）を分析

### 8.3 騎手×馬場×距離 PCI傾向

条件別のPCI傾向をデータベース化

### 8.4 調整値マスタ外部ファイル化

調整値をJSONファイルで管理し、データ分析結果から自動更新

```
KeibaCICD.TARGET/data/
└── pci_standards.json   # コース・距離別PCI基準値
```

### 8.5 馬場状態による補正

良/稍重/重/不良でのPCI傾向差を分析し、馬場補正を追加

---

## 参考リンク

- [TARGET FAQ - PCI](https://targetfaq.jra-van.jp/faq/detail?site=SVKNEGBV&id=598)
- [TARGET FAQ - PCI3](https://targetfaq.jra-van.jp/faq/detail?site=SVKNEGBV&id=599)
- [TARGET FAQ - レース印](https://targetfaq.jra-van.jp/faq/detail?site=SVKNEGBV&id=592)
