# 調教パターン分析 機械学習設計書

## 📋 ドキュメント情報

| 項目 | 内容 |
|------|------|
| **作成日** | 2025年12月14日 |
| **バージョン** | 1.0 |
| **目的** | コース別・調教師別の有効な調教パターンを発見する |

---

## 1. 目標と期待される成果

### 1.1 分析目標

| 目標 | 説明 | 期待される成果 |
|------|------|---------------|
| **コース別有効パターン** | 東京芝1600mなど特定条件で好走する調教パターン | コース適性に基づく調教評価 |
| **調教師別パターン** | 各調教師の得意な仕上げ方と結果の相関 | 調教師別の信頼度スコア |
| **時系列パターン** | レース直前の調教強度と結果の関係 | 最適な調教間隔・強度の発見 |

### 1.2 ビジネス価値

```
入力: 調教データ + レース条件 + 調教師情報
  ↓
分析: 機械学習モデル
  ↓
出力: 「この調教パターンは東京芝1600mで高い成功率」
      「この調教師のこの仕上げ方は◎」
```

---

## 2. 利用可能なデータ

### 2.1 競馬ブックデータ（既存）

| データソース | 主要フィールド | 用途 |
|-------------|---------------|------|
| **CyokyoParser** | attack_explanation, short_review, training_arrow | 調教評価 |
| **SeisekiParser** | 着順, タイム, 通過順位, 上がり | 目的変数（成功/失敗） |
| **SyutubaParser** | コース, 距離, 馬場状態 | レース条件 |
| **NitteiParser** | 開催場所, レースID | コース分類 |

### 2.2 JRA-VANデータ（将来統合予定）

| データ | 内容 | 追加価値 |
|--------|------|---------|
| 調教タイム | 坂路/CW/ポリトラック等のタイム | 定量的評価 |
| 調教師ID | 調教師マスタ | 調教師別集計 |
| 馬場状態 | 良/稍重/重/不良 | 条件分岐 |
| 過去成績 | 全レース履歴 | 馬の能力評価 |

### 2.3 データ統合イメージ

```sql
-- 分析用統合ビュー例
CREATE VIEW ml.TrainingAnalysis AS
SELECT 
    r.race_id,
    r.course_type,        -- 芝/ダート
    r.distance,           -- 距離
    r.venue,              -- 開催場所
    t.trainer_id,         -- 調教師ID
    t.trainer_name,       -- 調教師名
    cy.training_arrow,    -- 調教矢印（↑↗→↘↓）
    cy.short_review,      -- 短評（好仕上がり等）
    cy.attack_explanation,-- 攻め解説テキスト
    s.finish_position,    -- 着順（目的変数）
    s.time,               -- 走破タイム
    s.last_3f             -- 上がり3F
FROM keibabook.Races r
JOIN keibabook.TrainingData cy ON r.race_id = cy.race_id
JOIN keibabook.Results s ON r.race_id = s.race_id AND cy.horse_number = s.horse_number
LEFT JOIN jravan.Trainers t ON ...;
```

---

## 3. 機械学習アプローチ

### 3.1 問題設定

| アプローチ | 問題タイプ | 目的変数 | 適用場面 |
|-----------|-----------|---------|---------|
| **分類** | Binary/Multi-class | 3着以内（1/0）、着順区分 | 勝率予測 |
| **回帰** | 連続値予測 | 着順、タイム差 | 細かい順位予測 |
| **クラスタリング** | 教師なし | - | パターン発見 |
| **パターンマイニング** | 相関分析 | - | ルール抽出 |

### 3.2 推奨アプローチ（段階的）

#### Phase 1: 探索的データ分析（EDA）
```python
# 調教矢印と着順の相関分析
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 調教矢印別の成績集計
arrow_stats = df.groupby(['venue', 'course_type', 'training_arrow']).agg({
    'is_top3': 'mean',      # 3着以内率
    'finish_position': 'mean',  # 平均着順
    'count': 'size'
}).reset_index()

# ヒートマップで可視化
pivot = arrow_stats.pivot_table(
    index='training_arrow', 
    columns=['venue', 'course_type'], 
    values='is_top3'
)
sns.heatmap(pivot, annot=True, cmap='RdYlGn')
```

#### Phase 2: 特徴量エンジニアリング
```python
# 調教関連の特徴量作成
def create_training_features(df):
    features = {}
    
    # 1. 調教矢印のエンコーディング
    arrow_map = {'↑': 2, '↗': 1, '→': 0, '↘': -1, '↓': -2}
    features['training_arrow_score'] = df['training_arrow'].map(arrow_map)
    
    # 2. 短評からのキーワード抽出
    keywords = ['好仕上', '上昇', '変わり身', '平凡', '不安']
    for kw in keywords:
        features[f'review_has_{kw}'] = df['short_review'].str.contains(kw, na=False).astype(int)
    
    # 3. 攻め解説のテキスト特徴量（TF-IDF）
    from sklearn.feature_extraction.text import TfidfVectorizer
    tfidf = TfidfVectorizer(max_features=50)
    text_features = tfidf.fit_transform(df['attack_explanation'].fillna(''))
    
    # 4. 調教師別の過去成績
    features['trainer_win_rate'] = df.groupby('trainer_id')['is_win'].transform('mean')
    features['trainer_top3_rate'] = df.groupby('trainer_id')['is_top3'].transform('mean')
    
    # 5. コース×調教師の相性
    features['trainer_course_rate'] = df.groupby(
        ['trainer_id', 'venue', 'course_type']
    )['is_top3'].transform('mean')
    
    return pd.DataFrame(features)
```

#### Phase 3: モデル構築
```python
from sklearn.model_selection import train_test_split, cross_val_score
from lightgbm import LGBMClassifier
import shap

# データ分割
X_train, X_test, y_train, y_test = train_test_split(
    features, target, test_size=0.2, random_state=42
)

# LightGBMモデル（勾配ブースティング）
model = LGBMClassifier(
    n_estimators=500,
    learning_rate=0.05,
    max_depth=6,
    num_leaves=31,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=5,
    random_state=42
)

# 交差検証
cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='roc_auc')
print(f"CV AUC: {cv_scores.mean():.4f} (+/- {cv_scores.std()*2:.4f})")

# 訓練
model.fit(X_train, y_train)

# 特徴量重要度（SHAP値）
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)
shap.summary_plot(shap_values, X_test)
```

#### Phase 4: パターン抽出
```python
# コース×調教師×調教評価のパターン分析
pattern_analysis = df.groupby([
    'venue',           # 開催場所
    'course_type',     # 芝/ダート
    'distance_category', # 短距離/中距離/長距離
    'trainer_id',      # 調教師
    'training_arrow'   # 調教評価
]).agg({
    'is_top3': ['mean', 'count'],
    'is_win': 'mean'
}).reset_index()

# 統計的に有意なパターンのみ抽出
pattern_analysis.columns = ['_'.join(col).strip('_') for col in pattern_analysis.columns]
significant_patterns = pattern_analysis[
    (pattern_analysis['is_top3_count'] >= 30) &  # サンプル数30以上
    (pattern_analysis['is_top3_mean'] >= 0.4)    # 3着以内率40%以上
]

print("有効な調教パターン:")
print(significant_patterns.sort_values('is_top3_mean', ascending=False).head(20))
```

---

## 4. 技術スタック

### 4.1 選択肢比較

| オプション | 学習 | 推論 | コスト | 推奨度 |
|-----------|------|------|--------|--------|
| **A: ML.NET（推奨）** | C# | C# | 無料 | ⭐⭐⭐ |
| **B: Azure AutoML + C#** | Azure | C# (ONNX) | 従量課金 | ⭐⭐⭐ |
| **C: Python + C#** | Python | C# (ONNX) | 無料 | ⭐⭐ |

### 4.2 推奨構成: ML.NET（C#で完結）

| レイヤー | 技術 | 用途 |
|---------|------|------|
| **データ処理** | C# + LINQ | 前処理・特徴量エンジニアリング |
| **機械学習** | ML.NET + LightGBM | 分類・回帰モデル |
| **テキスト分析** | ML.NET Tokenizers | 攻め解説のNLP |
| **可視化** | Blazor + Chart.js | EDA・結果表示 |
| **推論** | ML.NET ネイティブ | 高速推論 |
| **データベース** | SQL Server + EF Core | データ統合・集計 |

### 4.3 NuGetパッケージ（.NET 10）

```xml
<ItemGroup>
  <!-- ML.NET コア -->
  <PackageReference Include="Microsoft.ML" Version="4.0.0" />
  <!-- LightGBM（高性能勾配ブースティング） -->
  <PackageReference Include="Microsoft.ML.LightGbm" Version="4.0.0" />
  <!-- AutoML（自動モデル選択） -->
  <PackageReference Include="Microsoft.ML.AutoML" Version="0.22.0" />
  <!-- テキスト分析（攻め解説用） -->
  <PackageReference Include="Microsoft.ML.Tokenizers" Version="0.24.0" />
  <!-- ONNX（Azure AutoML出力読み込み用） -->
  <PackageReference Include="Microsoft.ML.OnnxRuntime" Version="1.18.0" />
</ItemGroup>
```

### 4.4 ML.NETでの実装例

```csharp
using Microsoft.ML;
using Microsoft.ML.Trainers.LightGbm;

public class TrainingPatternTrainer
{
    private readonly MLContext _mlContext = new();
    
    public ITransformer TrainModel(string dataPath)
    {
        // 1. データ読み込み
        var dataView = _mlContext.Data.LoadFromTextFile<TrainingData>(
            dataPath, separatorChar: ',', hasHeader: true);
        
        // 2. データ分割
        var split = _mlContext.Data.TrainTestSplit(dataView, testFraction: 0.2);
        
        // 3. パイプライン構築
        var pipeline = _mlContext.Transforms
            // カテゴリ変数のエンコーディング
            .Categorical.OneHotEncoding("VenueEncoded", nameof(TrainingData.Venue))
            .Append(_mlContext.Transforms.Categorical.OneHotEncoding(
                "CourseTypeEncoded", nameof(TrainingData.CourseType)))
            .Append(_mlContext.Transforms.Categorical.OneHotEncoding(
                "TrainingArrowEncoded", nameof(TrainingData.TrainingArrow)))
            // 特徴量結合
            .Append(_mlContext.Transforms.Concatenate("Features",
                "VenueEncoded", "CourseTypeEncoded", "TrainingArrowEncoded",
                nameof(TrainingData.Distance), 
                nameof(TrainingData.TrainerWinRate)))
            // LightGBM分類器
            .Append(_mlContext.BinaryClassification.Trainers.LightGbm(
                new LightGbmBinaryTrainer.Options
                {
                    NumberOfLeaves = 31,
                    NumberOfIterations = 500,
                    LearningRate = 0.05f,
                    Deterministic = true
                }));
        
        // 4. 訓練
        var model = pipeline.Fit(split.TrainSet);
        
        // 5. 評価
        var predictions = model.Transform(split.TestSet);
        var metrics = _mlContext.BinaryClassification.Evaluate(predictions);
        Console.WriteLine($"AUC: {metrics.AreaUnderRocCurve:F4}");
        Console.WriteLine($"Accuracy: {metrics.Accuracy:F4}");
        
        return model;
    }
    
    public void SaveModel(ITransformer model, DataViewSchema schema, string path)
    {
        _mlContext.Model.Save(model, schema, path);
    }
}

// データクラス
public class TrainingData
{
    [LoadColumn(0)] public string Venue { get; set; } = "";
    [LoadColumn(1)] public string CourseType { get; set; } = "";
    [LoadColumn(2)] public float Distance { get; set; }
    [LoadColumn(3)] public string TrainingArrow { get; set; } = "";
    [LoadColumn(4)] public float TrainerWinRate { get; set; }
    [LoadColumn(5)] public bool IsTop3 { get; set; }
}
```

### 4.5 ML.NET AutoML（自動モデル選択）

```csharp
using Microsoft.ML.AutoML;

public class AutoMLTrainer
{
    private readonly MLContext _mlContext = new();
    
    public async Task<ITransformer> TrainWithAutoMLAsync(string dataPath)
    {
        var dataView = _mlContext.Data.LoadFromTextFile<TrainingData>(
            dataPath, separatorChar: ',', hasHeader: true);
        
        var split = _mlContext.Data.TrainTestSplit(dataView, testFraction: 0.2);
        
        // AutoML設定
        var settings = new BinaryClassificationExperimentSettings
        {
            MaxExperimentTimeInSeconds = 600,  // 最大10分
            OptimizingMetric = BinaryClassificationMetric.AreaUnderRocCurve
        };
        
        // AutoML実行（複数アルゴリズムを自動比較）
        var experiment = _mlContext.Auto()
            .CreateBinaryClassificationExperiment(settings);
        
        var result = await experiment.ExecuteAsync(
            split.TrainSet, 
            labelColumnName: nameof(TrainingData.IsTop3));
        
        Console.WriteLine($"Best Algorithm: {result.BestRun.TrainerName}");
        Console.WriteLine($"Best AUC: {result.BestRun.ValidationMetrics.AreaUnderRocCurve:F4}");
        
        return result.BestRun.Model;
    }
}
```

### 4.6 Azure AutoML（クラウド版）

最高精度を追求する場合や、大規模データの場合はAzure AutoMLも選択肢：

```csharp
// Azure AutoMLで訓練したONNXモデルを読み込む
using Microsoft.ML.OnnxRuntime;

public class AzureModelPredictor
{
    private readonly InferenceSession _session;
    
    public AzureModelPredictor(string onnxPath)
    {
        _session = new InferenceSession(onnxPath);
    }
    
    public float PredictTop3Probability(float[] features)
    {
        var inputTensor = new DenseTensor<float>(features, new[] { 1, features.Length });
        var inputs = new[] { NamedOnnxValue.CreateFromTensor("input", inputTensor) };
        
        using var results = _session.Run(inputs);
        return results.First().AsTensor<float>()[1];
    }
}
```

### 4.7 Python環境（オプション: EDA・実験用）

Pythonが必要な場合のみ：

```bash
# requirements.txt（オプション）
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
lightgbm>=4.0.0
matplotlib>=3.8.0
seaborn>=0.13.0
jupyter>=1.0.0
```

---

## 5. 実装ロードマップ

### 5.1 フェーズ計画

| Phase | 期間 | 内容 | 成果物 |
|-------|------|------|--------|
| **Phase 1** | 1-2週間 | データ収集・EDA | 分析レポート、可視化ダッシュボード |
| **Phase 2** | 2-3週間 | 特徴量エンジニアリング | 特徴量パイプライン |
| **Phase 3** | 2-3週間 | モデル構築・評価 | 学習済みモデル（.onnx） |
| **Phase 4** | 1-2週間 | パターン抽出・レポート | パターンカタログ |
| **Phase 5** | 1-2週間 | C#統合・本番化 | 推論API |

### 5.2 Phase 1 詳細（EDA）

```python
# Jupyter Notebook構成
notebooks/
├── 01_data_collection.ipynb      # データ読み込み・結合
├── 02_training_analysis.ipynb    # 調教データ分析
├── 03_course_analysis.ipynb      # コース別分析
├── 04_trainer_analysis.ipynb     # 調教師別分析
└── 05_pattern_discovery.ipynb    # パターン発見
```

---

## 6. 分析観点の詳細

### 6.1 コース別分析

| 分析観点 | 内容 | 仮説例 |
|---------|------|--------|
| コース形態 | 直線/小回り/大回り | 小回りコースでは坂路調教が有効 |
| 距離 | 短距離/中距離/長距離 | 長距離では持久力系調教が重要 |
| 馬場 | 芝/ダート | ダートはパワー系調教 |
| 坂 | 急坂/平坦 | 急坂コースでは坂路調教 |

```python
# コース別調教パターン分析
course_patterns = df.groupby([
    'venue', 
    'course_type', 
    'distance_category',
    'training_arrow'
]).apply(lambda x: pd.Series({
    'win_rate': (x['finish_position'] == 1).mean(),
    'top3_rate': (x['finish_position'] <= 3).mean(),
    'avg_position': x['finish_position'].mean(),
    'sample_size': len(x)
})).reset_index()

# 東京芝1600mで最も有効な調教パターン
tokyo_turf_1600 = course_patterns[
    (course_patterns['venue'] == '東京') & 
    (course_patterns['course_type'] == '芝') &
    (course_patterns['distance_category'] == '中距離')
].sort_values('top3_rate', ascending=False)
```

### 6.2 調教師別分析

| 分析観点 | 内容 | 仮説例 |
|---------|------|--------|
| 仕上げパターン | 叩き良化/一発仕上げ | 調教師Aは叩いて良くなる |
| 調教強度 | 強め/普通/軽め | 調教師Bの強め調教は信頼度高い |
| コース適性 | 得意コース | 調教師Cは東京で成績良好 |
| 調教矢印の信頼度 | ↑の実際の成績 | 調教師Dの↑は的中率80% |

```python
# 調教師別の調教矢印信頼度
trainer_arrow_reliability = df.groupby(['trainer_id', 'training_arrow']).apply(
    lambda x: pd.Series({
        'predicted_good': len(x[x['training_arrow'].isin(['↑', '↗'])]),
        'actual_top3': len(x[x['finish_position'] <= 3]),
        'reliability': (x['finish_position'] <= 3).mean() if len(x) > 0 else 0,
        'sample_size': len(x)
    })
).reset_index()

# 調教師の「↑評価」の信頼度ランキング
arrow_up_reliability = trainer_arrow_reliability[
    (trainer_arrow_reliability['training_arrow'] == '↑') &
    (trainer_arrow_reliability['sample_size'] >= 20)
].sort_values('reliability', ascending=False)
```

### 6.3 テキスト分析（攻め解説）

```python
# 攻め解説のキーワード分析
from collections import Counter
import re

# キーワード抽出
positive_keywords = ['好時計', '軽快', '意欲的', '絶好調', '上昇', '変わり身']
negative_keywords = ['重苦しい', '平凡', '物足りない', '不安', '太め']

def extract_sentiment(text):
    if pd.isna(text):
        return 0
    score = 0
    for kw in positive_keywords:
        if kw in text:
            score += 1
    for kw in negative_keywords:
        if kw in text:
            score -= 1
    return score

df['training_sentiment'] = df['attack_explanation'].apply(extract_sentiment)

# センチメントと成績の相関
sentiment_performance = df.groupby('training_sentiment').agg({
    'is_top3': 'mean',
    'finish_position': 'mean',
    'count': 'size'
})
```

---

## 7. 評価指標

### 7.1 モデル評価

| 指標 | 説明 | 目標値 |
|------|------|--------|
| **AUC-ROC** | 分類性能の総合指標 | 0.65以上 |
| **Precision@K** | 上位K件の精度 | 0.40以上 |
| **Recall@3** | 3着以内馬の捕捉率 | 0.50以上 |
| **Profit Factor** | 回収率 | 1.0以上（黒字） |

### 7.2 パターンの有効性評価

```python
# パターンの統計的有意性検定
from scipy import stats

def evaluate_pattern_significance(pattern_df, baseline_rate):
    """
    パターンの有意性を検定
    baseline_rate: 全体の3着以内率（例: 0.30）
    """
    results = []
    for _, row in pattern_df.iterrows():
        n = row['sample_size']
        k = int(row['top3_rate'] * n)
        
        # 二項検定
        p_value = stats.binom_test(k, n, baseline_rate, alternative='greater')
        
        # 効果量（オッズ比）
        odds_ratio = (row['top3_rate'] / (1 - row['top3_rate'])) / \
                     (baseline_rate / (1 - baseline_rate))
        
        results.append({
            'pattern': row['pattern_name'],
            'top3_rate': row['top3_rate'],
            'sample_size': n,
            'p_value': p_value,
            'odds_ratio': odds_ratio,
            'significant': p_value < 0.05
        })
    
    return pd.DataFrame(results)
```

---

## 8. 出力形式

### 8.1 パターンカタログ

```json
{
  "pattern_id": "P001",
  "description": "東京芝1600m × 坂路好時計 × ↑評価",
  "conditions": {
    "venue": "東京",
    "course_type": "芝",
    "distance_range": [1400, 1800],
    "training_arrow": "↑",
    "keywords": ["好時計", "坂路"]
  },
  "performance": {
    "top3_rate": 0.45,
    "win_rate": 0.18,
    "sample_size": 156,
    "p_value": 0.002,
    "odds_ratio": 1.85
  },
  "recommendation": "強い買い候補"
}
```

### 8.2 調教師信頼度カタログ

```json
{
  "trainer_id": "T0001",
  "trainer_name": "〇〇調教師",
  "specialty": {
    "best_venues": ["東京", "中山"],
    "best_course_type": "芝",
    "best_distance": "中距離"
  },
  "arrow_reliability": {
    "↑": { "top3_rate": 0.52, "sample_size": 45 },
    "↗": { "top3_rate": 0.38, "sample_size": 89 },
    "→": { "top3_rate": 0.28, "sample_size": 120 }
  },
  "overall_rating": "A"
}
```

---

## 9. 注意事項・リスク

### 9.1 データ品質

| リスク | 対策 |
|--------|------|
| 調教データの欠損 | 欠損フラグを特徴量化 |
| テキストの表記揺れ | 正規化・類義語辞書 |
| サンプル数不足 | 最低30件のフィルタ |

### 9.2 過学習防止

| リスク | 対策 |
|--------|------|
| 過学習 | 交差検証、正則化 |
| リーケージ | 時系列分割（未来データ使用禁止） |
| 偏り | 階層化サンプリング |

### 9.3 運用上の注意

- **競馬は不確実性が高い**: 高精度モデルでも外れることは多い
- **馬券購入は自己責任**: 予測結果を鵜呑みにしない
- **継続的な検証**: モデルの性能劣化を監視

---

## 10. 次のステップ

### 10.1 すぐに始められること

1. **既存データの収集**
   - 競馬ブックの調教データ（CyokyoParser出力）を蓄積
   - SeisekiParserで結果データを蓄積
   - 最低3ヶ月分のデータが望ましい

2. **Jupyter環境構築**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install pandas numpy scikit-learn lightgbm matplotlib seaborn jupyter
   jupyter notebook
   ```

3. **探索的データ分析開始**
   - 調教矢印と着順の相関
   - コース別の勝率分布
   - 調教師別の成績傾向

### 10.2 C#移行後に統合

- 学習済みモデルを`.onnx`形式でエクスポート
- `KeibaCICD.Scraper.Infrastructure`に推論サービス追加
- MD新聞に「AIパターン評価」セクション追加

---

## 11. 関連ドキュメント

- [C#移行詳細設計書](./csharp_migration_detailed_design.md)
- [DB統合設計書](./database_integration_design.md)
- [パーサー出力スキーマ](./parser_output_schemas.md)
- [IntegrationService設計](./integration_service_design.md)
