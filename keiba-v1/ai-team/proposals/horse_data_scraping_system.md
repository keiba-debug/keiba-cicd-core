# 馬情報スクレイピングシステム設計案

## 📋 概要
出走馬の過去成績を体系的に収集・管理し、WIN5予想の精度向上を図るシステム

## 🎯 目的
1. 各馬の過去レース成績を自動収集
2. 馬ごとの傾向・特徴を蓄積
3. データベース化による予想精度向上

## 🏗️ システム構成

### 1. データ構造
```
/data/horses/
├── metadata/
│   └── horse_index.json        # 馬ID・馬名の索引
├── profiles/
│   └── {horse_id}_{馬名}.md    # 馬別プロファイル
└── cache/
    └── {race_id}/              # レース情報キャッシュ
        └── results.json
```

### 2. 馬プロファイルファイル形式
```markdown
# {馬名} ({horse_id})

## 基本情報
- **生年月日**: 2022年3月15日
- **性別**: 牡
- **毛色**: 鹿毛
- **父**: ロードカナロア
- **母**: ビューティーパーラー
- **馬主**: 〇〇オーナー
- **調教師**: 〇〇師（栗東）

## 過去成績サマリー
- **通算成績**: 8戦3勝 [3-2-1-2]
- **獲得賞金**: 8,500万円
- **重賞実績**: G2-1着、G3-2着

## レース履歴
### 2025/09/14 阪神11R ローズS (G2)
- **着順**: -
- **騎手**: 川田将雅
- **斤量**: 55kg
- **人気**: -
- **タイム**: -
- **コメント**: (レース後記入)

### 2025/05/19 東京11R オークス (G1)
- **着順**: 1着
- **騎手**: 川田将雅
- **斤量**: 55kg
- **人気**: 2番人気
- **タイム**: 2:24.1
- **上がり**: 33.5
- **コメント**: 直線外から豪快に差し切り

[以下、過去レース続く...]

## 分析データ（自動生成）
### コース適性
- **芝1600m**: [1-1-0-0] 勝率100%
- **芝1800m**: [1-0-1-0] 勝率50%
- **芝2000m**: [1-1-0-1] 勝率33%

### 馬場適性
- **良**: [3-1-1-1] 勝率50%
- **稍重**: [0-1-0-1] 勝率0%

### 騎手相性
- **川田将雅**: [2-1-0-0] 勝率67%
- **ルメール**: [1-0-1-0] 勝率50%

---
## ユーザーメモ（手動入力）
- 休み明けは割引き必要
- 坂のあるコースが得意
- スローペースだと詰まる傾向
```

## 💻 実装案

### Phase 1: 基本機能（1週間）
```python
class HorseDataScraper:
    def __init__(self):
        self.base_url = "https://p.keibabook.co.jp"
        self.cache_dir = Path("data/horses/cache")
        self.profiles_dir = Path("data/horses/profiles")

    def get_horse_profile(self, horse_id: str) -> dict:
        """馬の基本情報と過去成績を取得"""
        # 1. 馬情報ページをスクレイピング
        # 2. 過去レース一覧を取得
        # 3. 各レースの詳細を取得（キャッシュ活用）
        pass

    def update_race_results(self, race_id: str) -> None:
        """レース結果を取得して関連馬のプロファイルを更新"""
        pass

    def generate_markdown(self, horse_data: dict) -> str:
        """馬情報をMarkdown形式に変換"""
        pass
```

### Phase 2: 高度な分析機能（2週間）
```python
class HorseAnalyzer:
    def analyze_course_fitness(self, horse_id: str) -> dict:
        """コース適性を分析"""
        pass

    def analyze_pace_preference(self, horse_id: str) -> dict:
        """ペース適性を分析"""
        pass

    def predict_performance(self, horse_id: str, race_conditions: dict) -> float:
        """条件に基づく期待値を算出"""
        pass
```

### Phase 3: WIN5特化機能（1週間）
```python
class WIN5HorseSelector:
    def get_win5_horses(self, date: str) -> list:
        """WIN5対象レースの全出走馬を取得"""
        pass

    def batch_update_profiles(self, horse_ids: list) -> None:
        """複数馬のプロファイルを一括更新"""
        pass

    def generate_comparison_table(self, race_id: str) -> pd.DataFrame:
        """レース出走馬の比較表を生成"""
        pass
```

## 📊 活用例

### 明日のWIN5対象馬分析
```python
# 阪神11R出走馬の一括取得
horses = scraper.get_race_horses("202504010411")
for horse in horses:
    profile = scraper.get_horse_profile(horse['id'])
    analyzer.generate_report(profile)
```

### 結果
```
カムニャック (0936453)
- G1勝利実績あり ✓
- 阪神実績: [1-0-0-0] ✓
- 休養明け2戦目 △
- 推奨度: A

パラディレーヌ (0934420)
- 重賞3着以内: 2回 ✓
- 1800m: [2-1-0-1] ✓
- 前走凡走からの巻き返し ○
- 推奨度: B+
```

## 🚀 期待効果

1. **データ蓄積**:
   - 過去データの体系的管理
   - 傾向分析の精度向上

2. **効率化**:
   - 手動調査時間を80%削減
   - リアルタイム更新

3. **予想精度向上**:
   - 客観的データに基づく判断
   - 見落としの防止

## 📅 開発スケジュール

| フェーズ | 期間 | 内容 |
|---------|------|------|
| Phase 1 | 1週間 | 基本スクレイピング機能 |
| Phase 2 | 2週間 | 分析・レポート機能 |
| Phase 3 | 1週間 | WIN5特化機能 |
| テスト | 3日 | 統合テスト・調整 |

## 💡 追加提案

1. **AI予想モデル連携**
   - 蓄積データを機械学習に活用
   - 予想精度の継続的改善

2. **アラート機能**
   - 注目馬の出走通知
   - 好条件レースの自動検出

3. **可視化ダッシュボード**
   - 馬別成績グラフ
   - コース別勝率ヒートマップ

## 🔧 技術スタック
- Python 3.11+
- BeautifulSoup4 / Scrapy
- Pandas / NumPy
- Markdown
- SQLite（将来的なDB化）

---
*作成: 2025年9月13日*
*GUNNER & SCRAPER連携提案*