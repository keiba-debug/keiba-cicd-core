# パーサー出力スキーマ設計書

## 📋 概要

Python版パーサー（7種類）の出力JSONスキーマを文書化。
C#移行時の互換性確保と、IntegrationService / MarkdownService のテスト基準となる。

---

## 0. 互換の合格基準（共通）

### 必須一致（Must）
- トップレベルのキー名
- 配列の構造（entries/horses/results 等）
- 馬番・馬名・レースID等の識別子

### 許容差分（May）
- `null` と 「キー省略」の違い
- 空文字列 `""` と `null` の違い
- 全角/半角数字の表記揺れ（C#側で正規化）

### 不一致扱い（Fail）
- 必須キーの欠損
- 配列が空（**ファイルが存在し、パース成功したにもかかわらず空**の場合）
  - ファイル未取得（存在しない）は「未取得」扱いで別途処理
- 型の不一致（文字列を数値で返す等）

---

## 0.1 馬番の型統一ルール

パーサーごとに馬番の型が異なる（文字列/int混在）ため、**IntegrationService側で統一**する。

| パーサー | 馬番キー | 型 |
|---------|---------|-----|
| SyutubaParser | `馬番` | string |
| DanwaParser | `馬番` | string |
| SeisekiParser | `馬番` | string |
| CyokyoParser | `horse_number` | int |
| SyoinParser | `horse_number` | int |
| PaddokParser | `horse_number` | int |

### 統一方針

```csharp
// IntegrationService / 各Parserでの変換ルール
// - 入力は string / int どちらでも受け付ける
// - 内部では常に int horseNumber に正規化
// - ToIntSafe() で全角数字・非数字混入にも対応

public static int? ToIntSafe(object? value)
{
    if (value is int intVal) return intVal;
    if (value is string strVal)
    {
        // 全角→半角変換
        strVal = ConvertToHalfWidth(strVal);
        // 数字のみ抽出
        var digitsOnly = new string(strVal.Where(char.IsDigit).ToArray());
        if (int.TryParse(digitsOnly, out var result))
            return result;
    }
    return null;
}
```

---

## 0.2 JSONシリアライズ方針

### 日本語キー vs snake_case の使い分け

| 対象 | 方針 |
|------|------|
| 日本語キー（`馬番`, `馬名`, `騎手`等） | **必ず `[JsonPropertyName]` で明示** |
| 英語キー（`horse_number`, `race_id`等） | `JsonNamingPolicy.SnakeCaseLower` で自動変換 |

### 設定例

```csharp
public static readonly JsonSerializerOptions JsonOptions = new()
{
    WriteIndented = true,
    Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,  // 英語キーのみ適用
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
};

// 日本語キーは必ず明示
public class HorseEntry
{
    [JsonPropertyName("馬番")]  // ← naming policyに依存せず固定
    public string HorseNumber { get; set; }
    
    [JsonPropertyName("馬名")]  // ← naming policyに依存せず固定
    public string HorseName { get; set; }
    
    public string? UmaCd { get; set; }  // → 自動で uma_cd になる
}
```

---

## 1. NitteiParser（日程パーサー）

### 1.1 用途
レース開催日程・開催場所・レースIDの一覧を取得

### 1.2 出力スキーマ

```json
{
  "date": "20250101",
  "kaisai_data": {
    "東京": [
      {
        "race_no": "1R",
        "race_name": "2歳未勝利",
        "course": "芝・1600m",
        "race_id": "202501010101",
        "start_time": "09:55",
        "start_at": "2025-01-01T09:55:00+09:00"
      }
    ],
    "中山": [...]
  },
  "total_races": 36,
  "kaisai_count": 3
}
```

### 1.3 フィールド詳細

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `date` | string | ✅ | 日付（YYYYMMDD形式） |
| `kaisai_data` | object | ✅ | 開催場所名をキー、レース配列を値 |
| `total_races` | int | ✅ | 全レース数 |
| `kaisai_count` | int | ✅ | 開催場所数 |

#### kaisai_data[場所名][] のフィールド

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `race_no` | string | ✅ | レース番号（"1R"形式） |
| `race_name` | string | ✅ | レース名 |
| `course` | string | ✅ | コース情報（"芝・1600m"形式） |
| `race_id` | string | ✅ | 12桁のレースID |
| `start_time` | string | ❌ | 発走時刻（"HH:MM"形式） |
| `start_at` | string | ❌ | ISO8601形式の発走日時 |

### 1.4 C#対応クラス

```csharp
public class NitteiData
{
    public string Date { get; set; } = string.Empty;
    public Dictionary<string, List<RaceSchedule>> KaisaiData { get; set; } = new();
    public int TotalRaces { get; set; }
    public int KaisaiCount { get; set; }
}

public class RaceSchedule
{
    public string RaceNo { get; set; } = string.Empty;
    public string RaceName { get; set; } = string.Empty;
    public string Course { get; set; } = string.Empty;
    public string RaceId { get; set; } = string.Empty;
    public string? StartTime { get; set; }
    public string? StartAt { get; set; }
}
```

---

## 2. SyutubaParser（出馬表パーサー）

### 2.1 用途
出馬表情報（馬・騎手・印・AI指数・展開予想）を取得

### 2.2 出力スキーマ

```json
{
  "race_info": {
    "title": "出馬表 | 2025年1月1日東京1R | 競馬ブック",
    "race_condition": "2歳未勝利",
    "track": "芝",
    "distance": 1600
  },
  "horses": [
    {
      "馬番": "1",
      "枠番": "1",
      "馬名": "ホース名",
      "馬名_clean": "ホース名",
      "umacd": "1234567890",
      "馬名_link": "/umainfo/1234567890",
      "騎手": "騎手名",
      "厩舎": "厩舎名",
      "本誌": "◎",
      "短評": "好調",
      "本誌印": "◎",
      "本誌印ポイント": 8,
      "総合印ポイント": 15,
      "AI指数": "100",
      "AI指数ランク": "1",
      "人気指数": "90",
      "marks_by_person": {
        "CPU": "◎",
        "本誌": "○",
        "牟田雅": "▲"
      }
    }
  ],
  "horse_count": 18,
  "ai_data": {
    "entries": [
      {
        "rank": "1",
        "horse_number": "1",
        "horse_name": "ホース名",
        "popularity_index": "90",
        "ai_index": "100"
      }
    ]
  },
  "tenkai_data": {
    "pace": "M",
    "positions": {
      "逃げ": ["1", "2"],
      "先行": ["3", "4", "5"],
      "差し": ["6", "7"],
      "追込": ["8"]
    },
    "description": "内枠有利の展開..."
  },
  "race_comment": "本紙の見解テキスト..."
}
```

### 2.3 フィールド詳細

#### race_info

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `title` | string | ❌ | ページタイトル |
| `race_condition` | string | ❌ | レース条件 |
| `track` | string | ❌ | "芝" or "ダ" |
| `distance` | int | ❌ | 距離（メートル） |

#### horses[]

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `馬番` | string | ✅ | 馬番号 |
| `枠番` | string | ❌ | 枠番号 |
| `馬名` | string | ✅ | 馬名（HTMLそのまま） |
| `馬名_clean` | string | ❌ | 馬名（クリーン） |
| `umacd` | string | ❌ | 馬コード |
| `騎手` | string | ❌ | 騎手名 |
| `本誌` | string | ❌ | 本誌印（◎○▲△穴注） |
| `短評` | string | ❌ | 短評コメント |
| `本誌印ポイント` | int | ❌ | 本誌印のポイント |
| `総合印ポイント` | int | ❌ | 複数予想者の合計ポイント |
| `AI指数` | string | ❌ | AI指数値 |
| `marks_by_person` | object | ❌ | 予想者別印 |

#### tenkai_data

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `pace` | string | ❌ | ペース（H/M/S） |
| `positions` | object | ❌ | 脚質別馬番配列 |
| `description` | string | ❌ | 展開解説 |

### 2.4 C#対応クラス

```csharp
public class SyutubaData
{
    public RaceInfo RaceInfo { get; set; } = new();
    public List<HorseEntry> Horses { get; set; } = new();
    public int HorseCount { get; set; }
    public AiData? AiData { get; set; }
    public TenkaiData? TenkaiData { get; set; }
    public string? RaceComment { get; set; }
}

public class HorseEntry
{
    [JsonPropertyName("馬番")]
    public string HorseNumber { get; set; } = string.Empty;
    
    [JsonPropertyName("馬名")]
    public string HorseName { get; set; } = string.Empty;
    
    [JsonPropertyName("馬名_clean")]
    public string? HorseNameClean { get; set; }
    
    [JsonPropertyName("umacd")]
    public string? UmaCd { get; set; }
    
    [JsonPropertyName("騎手")]
    public string? Jockey { get; set; }
    
    [JsonPropertyName("本誌")]
    public string? HonshiMark { get; set; }
    
    [JsonPropertyName("短評")]
    public string? ShortComment { get; set; }
    
    [JsonPropertyName("本誌印ポイント")]
    public int? HonshiMarkPoint { get; set; }
    
    [JsonPropertyName("総合印ポイント")]
    public int? AggregateMarkPoint { get; set; }
    
    [JsonPropertyName("marks_by_person")]
    public Dictionary<string, string>? MarksByPerson { get; set; }
}
```

---

## 3. CyokyoParser（調教パーサー）

### 3.1 用途
調教情報（攻め解説・短評・矢印）を取得

### 3.2 出力スキーマ

```json
{
  "race_info": {
    "race_name": "東京1R 2歳未勝利",
    "date_info": "2025年1月1日"
  },
  "training_data": [
    {
      "race_id": "202501010101",
      "horse_number": 1,
      "horse_name": "ホース名",
      "attack_explanation": "坂路で好時計をマーク。動きも軽快で...",
      "short_review": "好仕上がり",
      "training_arrow": "↗"
    }
  ]
}
```

### 3.3 フィールド詳細

#### training_data[]

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `race_id` | string | ❌ | 12桁のレースID |
| `horse_number` | int | ✅ | 馬番号 |
| `horse_name` | string | ❌ | 馬名 |
| `attack_explanation` | string | ❌ | 攻め解説 |
| `short_review` | string | ❌ | 短評 |
| `training_arrow` | string | ❌ | 矢印（→↗↘↑↓） |

### 3.4 C#対応クラス

```csharp
public class CyokyoData
{
    public RaceInfoBasic RaceInfo { get; set; } = new();
    public List<TrainingEntry> TrainingData { get; set; } = new();
}

public class TrainingEntry
{
    public string? RaceId { get; set; }
    public int HorseNumber { get; set; }
    public string? HorseName { get; set; }
    public string? AttackExplanation { get; set; }
    public string? ShortReview { get; set; }
    public string? TrainingArrow { get; set; }
}
```

---

## 4. DanwaParser（厩舎談話パーサー）

### 4.1 用途
厩舎の話（調教師コメント）を取得

### 4.2 出力スキーマ

```json
{
  "race_info": {
    "race_name": "東京1R 2歳未勝利",
    "date_info": "2025年1月1日"
  },
  "danwa_data": [
    {
      "馬番": "1",
      "馬名": "ホース名",
      "厩舎": "〇〇厩舎",
      "調教師": "田中太郎",
      "コメント": "状態は良好で...",
      "談話": "状態は良好で...",
      "展望": "勝ち負けを期待"
    }
  ]
}
```

### 4.3 フィールド詳細

#### danwa_data[]

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `馬番` | string | ✅ | 馬番号（文字列） |
| `馬名` | string | ✅ | 馬名 |
| `厩舎` | string | ❌ | 厩舎名 |
| `調教師` | string | ❌ | 調教師名 |
| `コメント` | string | ❌ | 談話内容 |
| `談話` | string | ❌ | 談話内容（別名） |
| `展望` | string | ❌ | 今後の展望 |

### 4.4 C#対応クラス

```csharp
public class DanwaData
{
    public RaceInfoBasic RaceInfo { get; set; } = new();
    public List<DanwaEntry> DanwaData { get; set; } = new();
}

public class DanwaEntry
{
    [JsonPropertyName("馬番")]
    public string HorseNumber { get; set; } = string.Empty;
    
    [JsonPropertyName("馬名")]
    public string HorseName { get; set; } = string.Empty;
    
    [JsonPropertyName("厩舎")]
    public string? Stable { get; set; }
    
    [JsonPropertyName("調教師")]
    public string? Trainer { get; set; }
    
    [JsonPropertyName("コメント")]
    public string? Comment { get; set; }
    
    [JsonPropertyName("談話")]
    public string? Danwa { get; set; }
    
    [JsonPropertyName("展望")]
    public string? Tenbou { get; set; }
}
```

---

## 5. SeisekiParser（成績パーサー）

### 5.1 用途
レース結果・配当・ラップを取得

### 5.2 出力スキーマ

```json
{
  "race_info": {
    "race_name": "2025年6月1日東京11R第92回　東京優駿(ＧＩ)"
  },
  "results": [
    {
      "着順": "1",
      "馬番": "5",
      "馬名": "ホース名",
      "騎手": "騎手名",
      "タイム": "2:24.5",
      "着差": "1 1/2",
      "通過順位": "3-3-3-2",
      "上がり": "34.5",
      "人気": "1",
      "単勝オッズ": "2.5",
      "interview": "騎手インタビュー内容...",
      "memo": "次走へのメモ..."
    }
  ],
  "payouts": {
    "win": 450,
    "place": [150, 200, 300],
    "quinella": 1230,
    "exacta": 2340,
    "wide": [450, 560, 670],
    "trio": 3450,
    "trifecta": 23450
  },
  "race_details": {
    "distance": 2400,
    "track_type": "芝",
    "track_condition": "良",
    "weather": "晴",
    "start_time": "15:40",
    "grade": "G1",
    "prize_money": ["3億円", "1億2000万円"]
  },
  "laps": {
    "lap_times": ["12.3", "11.5", "12.0", "11.8", "12.1"],
    "first_1000m": "59.5",
    "pace": "M"
  }
}
```

### 5.3 フィールド詳細

#### results[]

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `着順` | string | ✅ | 着順 |
| `馬番` | string | ✅ | 馬番号 |
| `馬名` | string | ✅ | 馬名 |
| `騎手` | string | ❌ | 騎手名 |
| `タイム` | string | ❌ | 走破タイム |
| `着差` | string | ❌ | 着差 |
| `interview` | string | ❌ | 騎手インタビュー |
| `memo` | string | ❌ | 次走へのメモ |

#### payouts

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `win` | int? | ❌ | 単勝配当 |
| `place` | int[] | ❌ | 複勝配当配列 |
| `quinella` | int? | ❌ | 馬連配当 |
| `exacta` | int? | ❌ | 馬単配当 |
| `wide` | int[] | ❌ | ワイド配当配列 |
| `trio` | int? | ❌ | 三連複配当 |
| `trifecta` | int? | ❌ | 三連単配当 |

#### laps

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `lap_times` | string[] | ❌ | ラップタイム配列 |
| `first_1000m` | string | ❌ | 前半1000mタイム |
| `pace` | string | ❌ | ペース判定（H/M/S） |

### 5.4 C#対応クラス

```csharp
public class SeisekiData
{
    public RaceInfoBasic RaceInfo { get; set; } = new();
    public List<RaceResult> Results { get; set; } = new();
    public PayoutInfo Payouts { get; set; } = new();
    public RaceDetails RaceDetails { get; set; } = new();
    public LapsInfo Laps { get; set; } = new();
}

public class RaceResult
{
    [JsonPropertyName("着順")]
    public string Rank { get; set; } = string.Empty;
    
    [JsonPropertyName("馬番")]
    public string HorseNumber { get; set; } = string.Empty;
    
    [JsonPropertyName("馬名")]
    public string HorseName { get; set; } = string.Empty;
    
    [JsonPropertyName("騎手")]
    public string? Jockey { get; set; }
    
    [JsonPropertyName("タイム")]
    public string? Time { get; set; }
    
    [JsonPropertyName("interview")]
    public string? Interview { get; set; }
    
    [JsonPropertyName("memo")]
    public string? Memo { get; set; }
}

public class PayoutInfo
{
    public int? Win { get; set; }
    public List<int> Place { get; set; } = new();
    public int? Quinella { get; set; }
    public int? Exacta { get; set; }
    public List<int> Wide { get; set; } = new();
    public int? Trio { get; set; }
    public int? Trifecta { get; set; }
}
```

---

## 6. SyoinParser（前走インタビューパーサー）

### 6.1 用途
前走レースでのインタビュー・次走へのメモを取得

### 6.2 出力スキーマ

```json
{
  "race_info": {
    "title": "前走インタビュー | 東京1R | 競馬ブック",
    "keywords": "競馬,前走,インタビュー"
  },
  "interviews": [
    {
      "horse_number": 1,
      "horse_name": "ホース名",
      "waku_ban": 1,
      "jockey": "騎手名",
      "finish_position": "1着",
      "interview": "スタートで出遅れましたが...",
      "next_race_memo": "次走は距離延長で...",
      "comment": "全体コメント（後方互換用）",
      "previous_race_mention": "前走情報"
    }
  ],
  "interview_count": 18
}
```

### 6.3 フィールド詳細

#### interviews[]

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `horse_number` | int | ✅ | 馬番号 |
| `horse_name` | string | ❌ | 馬名 |
| `waku_ban` | int | ❌ | 枠番 |
| `jockey` | string | ❌ | 騎手名 |
| `finish_position` | string | ❌ | 着順（"1着"形式） |
| `interview` | string | ❌ | インタビュー内容 |
| `next_race_memo` | string | ❌ | 次走へのメモ |
| `comment` | string | ❌ | 全体コメント（後方互換） |

### 6.4 C#対応クラス

```csharp
public class SyoinData
{
    public RaceInfoBasic RaceInfo { get; set; } = new();
    public List<InterviewEntry> Interviews { get; set; } = new();
    public int InterviewCount { get; set; }
}

public class InterviewEntry
{
    public int HorseNumber { get; set; }
    public string? HorseName { get; set; }
    public int? WakuBan { get; set; }
    public string? Jockey { get; set; }
    public string? FinishPosition { get; set; }
    public string? Interview { get; set; }
    public string? NextRaceMemo { get; set; }
    public string? Comment { get; set; }
}
```

---

## 7. PaddokParser（パドックパーサー）

### 7.1 用途
パドック評価・馬体コメントを取得

### 7.2 出力スキーマ

```json
{
  "race_info": {
    "title": "パドック情報 | 東京1R | 競馬ブック",
    "venue": "東京",
    "keywords": "競馬,パドック"
  },
  "paddock_evaluations": [
    {
      "horse_number": 1,
      "horse_name": "ホース名",
      "comment": "馬体充実、毛艶良好...",
      "evaluation": "A",
      "mark": "◎"
    }
  ],
  "evaluation_count": 18,
  "data_status": "complete"
}
```

### 7.3 フィールド詳細

#### paddock_evaluations[]

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `horse_number` | int | ✅ | 馬番号 |
| `horse_name` | string | ❌ | 馬名 |
| `comment` | string | ❌ | パドックコメント |
| `evaluation` | string | ❌ | 評価（A/B/C/◎○▲△） |
| `mark` | string | ❌ | 印（評価と同じ場合あり） |

#### data_status

| 値 | 説明 |
|----|------|
| `complete` | データ取得成功 |
| `no_data_available` | データなし |

### 7.4 C#対応クラス

```csharp
public class PaddokData
{
    public RaceInfoBasic RaceInfo { get; set; } = new();
    public List<PaddockEvaluation> PaddockEvaluations { get; set; } = new();
    public int EvaluationCount { get; set; }
    public string DataStatus { get; set; } = "complete";
}

public class PaddockEvaluation
{
    public int HorseNumber { get; set; }
    public string? HorseName { get; set; }
    public string? Comment { get; set; }
    public string? Evaluation { get; set; }
    public string? Mark { get; set; }
}
```

---

## 8. 共通クラス

```csharp
public class RaceInfoBasic
{
    public string? RaceName { get; set; }
    public string? DateInfo { get; set; }
    public string? Title { get; set; }
    public string? Keywords { get; set; }
}

public class RaceDetails
{
    public int? Distance { get; set; }
    public string? TrackType { get; set; }
    public string? TrackCondition { get; set; }
    public string? Weather { get; set; }
    public string? StartTime { get; set; }
    public string? Grade { get; set; }
    public List<string> PrizeMoney { get; set; } = new();
}

public class LapsInfo
{
    public List<string> LapTimes { get; set; } = new();
    public string? First1000m { get; set; }
    public string? Pace { get; set; }
}
```

---

## 9. JSONシリアライズ設定（Python互換）

```csharp
public static readonly JsonSerializerOptions JsonOptions = new()
{
    WriteIndented = true,
    Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
};
```

---

## 10. テスト基準

### 10.1 互換性テスト項目

| パーサー | テスト内容 |
|---------|-----------|
| Nittei | kaisai_dataのキー数、race_idの12桁検証 |
| Syutuba | horses配列の馬番連続性、印ポイント計算 |
| Cyokyo | training_data配列、horse_numberの整数型 |
| Danwa | danwa_data配列、馬番・馬名の存在 |
| Seiseki | results配列の着順順序、payouts型検証 |
| Syoin | interviews配列、interview/next_race_memo分離 |
| Paddok | paddock_evaluations配列、data_status値 |

### 10.2 比較テスト手順

1. Python版でHTMLをパースしJSONを生成
2. C#版で同一HTMLをパースしJSONを生成
3. 両JSONを正規化（キーソート、null除去）
4. キー単位で差分比較
5. Must項目の一致を確認

---

## 11. 関連ドキュメント

- [IntegrationService詳細設計](./integration_service_design.md)
- [MarkdownGenerator詳細設計](./markdown_generator_design.md)
- [C#移行詳細設計](./csharp_migration_detailed_design.md)

