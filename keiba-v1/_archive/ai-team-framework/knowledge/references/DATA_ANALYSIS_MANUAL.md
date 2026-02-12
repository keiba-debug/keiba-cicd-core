# データ分析マニュアル プログラムソース 参考資料

> **出典**: `C:\KEIBA-CICD\データ分析マニュアル\プログラムソース`（第2〜6章）
> **作成日**: 2026-02-08
> **目的**: v3.2-v3.3 ML基盤整備に向けた分析手法の参照資料

---

## 1. マニュアル全体構成

| 章 | テーマ | ファイル数 | 概要 |
|----|--------|-----------|------|
| 第2章 | Python基礎 + JRA-VANコード体系 | 8 | 日付計算、コース辞書、コード変換 |
| 第3章 | SQLデータアクセス + ユーティリティ | 25 | ecore.db接続、4テーブル操作、前走/脚質判定 |
| 第4章 | オッズ×ファクター回収率分析 | 30+ | 23ファクター×10競馬場×コースの多次元回収率集計 |
| 第5章 | 属性別集計 | 2 | 23軸多次元集計の基盤 |
| 第6章 | 条件フィルタ + 検証 | 4 | 段階的フィルタリング、アンサンブル投票、バックテスト |

---

## 2. ecore.db テーブル構造

JRA-VAN SQLiteデータベースの4主テーブル。現在KeibaCICDがCSV/JSONで扱うデータの原型。

### N_RACE（レース基本情報）
```
PK的: Year, MonthDay, JyoCD, RaceNum
主要カラム:
  - GradeCD      : グレード（A=G1, B=G2, C=G3）
  - TrackCD      : トラックコード（芝/ダート・方向・回り）
  - Kyori        : 距離（メートル）
  - BabaCD       : 馬場状態（1=良, 2=稍重, 3=重, 4=不良）
  - SyubetuCD    : 競走種別
  - JyuryoCD     : 重量種別（1=ハンデ, 2=別定, 3=馬齢, 4=定量）
  - JyokenCD5    : 競走条件（新馬/未勝利/1勝〜3勝/オープン）
  - DataKubun    : データ区分（7=JRA確定）
  - LapTime1-25  : ラップタイム
  - CornerJyuni1-4: コーナー通過順位
```

### N_UMA_RACE（出走馬情報）
```
PK的: Year, MonthDay, JyoCD, RaceNum, KettoNum
主要カラム:
  - Umaban         : 馬番
  - Wakuban        : 枠番（1-8）
  - Ninki          : 人気順（"01"〜"18"）
  - Odds           : 単勝オッズ（×10の整数値）
  - KakuteiJyuni   : 確定着順
  - HaronTimeL3    : 上がり3F（×10の整数値）
  - KyakusituKubun : 脚質（1=逃, 2=先行, 3=差し, 4=追込）
  - Barei          : 馬齢
  - SexCD          : 性別
  - Bataiju        : 馬体重
  - BataijuSa      : 馬体重増減
  - KettoNum       : 血統登録番号（→ N_UMA結合キー）
```

### N_UMA（馬マスタ）
```
PK: KettoNum（血統登録番号）
主要カラム:
  - Bamei          : 馬名
  - 血統: Ketto3InfoHansyokuNum1〜（父/母/父父/父母/母父/母母）
  - Kyakusitu1-4   : 生涯脚質分布（逃/先/差/追の各回数）
  - SogoChakukaisu1-6: 着別カウント
  - RuikeiHonsyoHeiti: 累計本賞金
```

### N_HARAI（払戻情報）
```
PK的: Year, MonthDay, JyoCD, RaceNum
主要カラム:
  - PayTansyoUmaban1-3  + PayTansyoPay1-3   : 単勝（馬番+払戻金）
  - PayFukusyoUmaban1-3 + PayFukusyoPay1-3  : 複勝
  - PayUmarenUmaban1-3  + PayUmarenPay1-3   : 馬連
  - PaySanrentanUmaban1-6 + PaySanrentanPay1-6: 三連単
  - DataKubun: 2=確定
```

### テーブル間リレーション
```
N_RACE ──(Year,MonthDay,JyoCD,RaceNum)──→ N_UMA_RACE
N_RACE ──(Year,MonthDay,JyoCD,RaceNum)──→ N_HARAI
N_UMA_RACE ──(KettoNum)──→ N_UMA
```

---

## 3. 前走ファクター6種（第4.6章）

現在のKeibaCICDの`recentFormMap`に追加すべきファクター群。

### 3.1 前走距離差（zensoKyoriSa）
```
計算: 今走距離 - 前走距離

分類（11帯）:
  -1000以下 | -800 | -600 | -400 | -200 | 0 | +200 | +400 | +600 | +800 | +1000以上

活用: 距離短縮（マイナス）/延長（プラス）の有利不利を定量化
```

### 3.2 芝/ダート転換（zensoShibaDart）
```
4パターン:
  芝→芝 | 芝→ダート | ダート→芝 | ダート→ダート

判定: TrackCD >= 23 ならダート、それ以外は芝
活用: 芝↔ダート切替時の成績変動を分析
```

### 3.3 前走上がり順位（zensoAgariJyuni）
```
計算手順:
  1. 前走レースの全出走馬のHaronTimeL3を取得
  2. 昇順ソート（速い順）
  3. 当該馬の順位を返却

活用: 末脚能力の定量化（着順より実力を反映しやすい）
```

### 3.4 レース間隔（RaceInterval）
```
計算: int((日数差 + 1) / 7) - 1 [週単位]

例: 3日→0週（同週）、11日→1週、28日→3週
活用: 休み明け/連闘の影響を分析
```

### 3.5 前走オッズ（zensoOdds）
```
前走の単勝オッズ帯を分類
活用: 前走での市場評価と今走成績の相関分析
```

### 3.6 前走着順（zensoJyuni）
```
前走の確定着順
活用: 前走成績の連続性（巻き返し/反動）を分析
```

---

## 4. 脚質判定ロジック（第3章 utility.py）

過去N戦から動的に脚質を推定する関数。現在のKyakusituKubun直接表示より精度向上が見込める。

```python
def getUmaKyakushitu(KettoNum, Year="", MonthDay="", num=10):
    """
    モード1: Year/MonthDay省略 → N_UMA.Kyakusitu1-4（生涯成績）参照
    モード2: Year/MonthDay指定 → 過去num戦のKyakusituKubun集計

    ロジック:
      逃げ数, 先行数, 差し数, 追込数 を集計
      if (逃+先) > (差+追):
          return 1 if 逃 >= 先 else 2  # 前傾脚質
      else:
          return 3 if 差 > 追 else 4   # 後傾脚質

    戻り値: 1(逃) / 2(先行) / 3(差し) / 4(追込) / 0(データなし)
    """
```

**KeibaCICDへの適用**: 調教分析テーブルや馬詳細で「推定脚質」として表示。直近5-10戦ベースで算出すれば、脚質転換した馬も検出可能。

---

## 5. アンサンブル投票システム（第6章）

### 5.1 概要

第6章の`All_kenshou.py`で実装されているスコアリング手法。複数条件にマッチするごとにポイント(m)を加算し、投票口数として使う。

### 5.2 処理フロー

```
Step 1: 基本フィルタ（必須条件）
  - ハンデ戦除外（JyuryoCD != "1"）
  - G2除外（GradeCD != "B"）
  - 6歳以下（Barei <= 6）
  - 1-6枠（Wakuban <= 6）
  - 特定体重帯除外
  - 特定体重増減除外
  - 距離差 -400〜0m

Step 2: ポイント加算（差し脚質の場合）
  m = 0
  m += 1 if SyubetuCD in ["13","14"]    # 3上/4上戦
  m += 1 if HinbaGentei                  # 牝馬限定戦
  m += 1 if JyuryoCD == "4"             # 定量戦
  m += 1 if JyokenCD5 in ["010","016"]  # 2勝/3勝クラス
  m += 1 if BabaCD in ["3","4"]         # 重/不良馬場
  m += 1 if Barei in [5,6]             # 5・6歳
  m += 1 if SexCD == "2"               # 牝馬
  m += 1 if 体重450-500kg              # 特定体重帯
  m += 1 if Interval in [3,9-12]       # 特定間隔
  m += 1 if zensoJyoCD in ["08","09"]  # 前走京都・阪神
  m += 1 if zensoOdds in [特定値]       # 前走特定オッズ
  m += 1 if zensoJyuni in [4,6,8,9]    # 前走特定着順
  m += 1 if zensoAgariJyuni in [2,5,9] # 前走上がり順位

Step 3: 投票
  if m > 0: m口分ベット
  的中時: 払戻 × m
```

### 5.3 検証結果（マニュアル記載の例）

```
7層フィルタ適用後: 東京芝1400m 1人気
  233レース中96的中 → 回収率 105.8%

アンサンブル投票適用後:
  単独条件(m=1) → 基本回収率
  複合条件(m>1) → 投票加算回収率（相乗効果あり）
```

### 5.4 KeibaCICDへの応用

`patterns.json`（v3.2-v3.3計画）の構造として：

```json
{
  "pattern_id": "sashi_jyoken_01",
  "base_filters": {
    "JyuryoCD": {"exclude": ["1"]},
    "GradeCD": {"exclude": ["B"]},
    "Barei": {"max": 6},
    "Wakuban": {"max": 6}
  },
  "scoring_rules": [
    {"field": "SyubetuCD", "values": ["13","14"], "points": 1},
    {"field": "BabaCD", "values": ["3","4"], "points": 1},
    {"field": "zensoJyoCD", "values": ["08","09"], "points": 1}
  ],
  "min_score": 1,
  "backtest_result": {
    "period": "2010-2019",
    "win_rate": 0.412,
    "roi": 1.058
  }
}
```

---

## 6. 多次元回収率分析テンプレート（第4章）

### 6.1 統一テンプレート構造

第4章の全30+スクリプトは同一の構造を踏襲している：

```python
# 1. ファクター配列定義
Factors = ["01", "02", "03", ...]

# 2. ネスト辞書初期化
data[JyoCD][TrackCD+Kyori][Factor][OddsInt] = [総数, 1着, 2着, 3着]

# 3. SQL検索 & 集計
for Year in range(2010, 2020):
    for JyoCD in ["01".."10"]:
        for Course in Courses[JyoCD]:
            RACEs = getRACEs(SQL条件)
            for RACE in RACEs:
                UMA_RACEs = getShiteiRaceUMA_RACEs(RACE)
                HARAI = getHARAI(RACE)
                for UMA_RACE in UMA_RACEs:
                    Factor = extract_factor(UMA_RACE)
                    OddsInt = classify_odds(UMA_RACE["Odds"])
                    data[...][Factor][OddsInt][0] += 1
                    if 着順 <= 3:
                        data[...][Factor][OddsInt][着順] += 1

# 4. 回収率計算
的中率 = 1着数 / 総数 × 100
回収率 = 払戻額 / 総数

# 5. ファイル出力
# 行: オッズ帯、列: ファクター値、セル: 回収率
```

### 6.2 分析済みファクター一覧（23軸）

**レース条件系（6軸）**
| ファクター | フィールド | 分類 |
|-----------|----------|------|
| 競走種別 | SyubetuCD | 新馬/未勝利/500万下/1000万下/1600万下 |
| 重量種別 | JyuryoCD | ハンデ/別定/馬齢/定量 |
| グレード | GradeCD | G1/G2/G3/リステッド/オープン/条件戦 |
| 馬場状態 | BabaCD | 良/稍重/重/不良 |
| 競走条件 | JyokenCD5 | 各クラス |
| 牝馬限定 | HinbaGentei | True/False |

**馬属性系（7軸）**
| ファクター | フィールド | 分類 |
|-----------|----------|------|
| 馬齢 | Barei | 2歳〜7歳以上 |
| 性別 | SexCD | 牡/牝/騙 |
| 枠番 | Wakuban | 1-8枠 |
| 馬体重 | Bataiju | 430kg未満〜530kg以上（11帯） |
| 馬体重変化 | BataijuSa | -24kg〜+24kg（±8kg単位） |
| 脚質 | Kyakushitu | 逃/先行/差し/追込 |
| オッズ | Odds | 1倍〜100倍以上（19帯） |

**前走系（6軸）** → セクション3参照

**コース系（4軸）**
| ファクター | フィールド | 分類 |
|-----------|----------|------|
| トラック | TrackCD | 芝左内/芝左外/芝右内/芝右外/ダート左/ダート右 |
| 距離 | Kyori | 各競馬場の設定距離 |
| 競馬場 | JyoCD | 01(札幌)〜10(小倉) |
| レース間隔 | RaceInterval | 0週〜21週以上 |

---

## 7. 段階的検証フレームワーク（第5-6章）

### 4段階アプローチ

```
1. 発見（Discovery）     : All_shukei.py
   → 23軸で無条件集計、どの属性に相関があるか発見

2. 最適化（Optimization） : All_shukei_joken.py
   → 7層のネスト条件で段階的フィルタリング
   → 各段階で回収率変化を計測

3. 特化（Specialization）: All_kenshou_kyakushitu.py
   → 特定脚質（差し）に条件最適化

4. 検証（Validation）    : 年度別回収率でバックテスト
   → 年度ごとの回収率推移で過学習チェック
```

### 各段階の出力例

```
Step1: 無条件 → 回収率 85.6%
Step2: +ハンデ除外 → 86.9%
Step3: +G2除外 → 86.9%
Step4: +6歳以下 → 86.9%
Step5: +1-6枠 → 97.0%
Step6: +体重帯除外 → 99.3%
Step7: +体重増減除外 → 100.3%
Step8: +距離差制限 → 105.8%
```

各段階で回収率がどう変化するかを追跡し、有効な条件を特定する。

---

## 8. KeibaCICD実装優先度マッピング

### v3.2-v3.3（ML基盤整備）向け

| 優先度 | 要素 | 実装先 | 根拠 |
|--------|------|--------|------|
| **高** | 前走距離差 | recentFormMap拡張 | 予測精度に直結 |
| **高** | 前走上がり順位 | recentFormMap拡張 | 着順より実力を反映 |
| **高** | アンサンブル条件スコアリング | patterns.json | パターン辞書構築の基盤 |
| **中** | レース間隔（週単位） | レース一覧/詳細 | 休養明け判定 |
| **中** | 動的脚質判定（過去N戦） | 調教分析テーブル | 脚質転換検出 |
| **中** | 芝/ダート転換フラグ | recentFormMap拡張 | 転換時の成績変動 |

### v5.0（期待値計算）向け

| 優先度 | 要素 | 実装先 | 根拠 |
|--------|------|--------|------|
| **高** | 多次元回収率マトリクス | 期待値エンジン | オッズ vs 実績の乖離度 |
| **高** | 段階的検証フレームワーク | バックテスト機能 | 過学習防止 |
| **中** | 年度別回収率推移 | training_history.db | トレンド変化検出 |

---

## 9. TrackCDコード体系（参考）

```
10 : 芝・直線（新潟のみ）
11 : 芝・左・内回り
12 : 芝・左・外回り
13 : 芝・左・内→外
14 : 芝・左・外→内
17 : 芝・右・内回り
18 : 芝・右・外回り
21 : 芝・右・2周（中山3600m）
23 : ダート・左
24 : ダート・右
29 : ダート・直線
51+ : 障害
```

---

## 10. SQLクエリパターン集

### レース検索
```sql
SELECT * FROM N_RACE
WHERE DataKubun = '7' AND Year = '2019' AND GradeCD = 'A'
ORDER BY JyoCD DESC, MonthDay ASC
```

### 出走馬検索（JRA + 地方 + 海外）
```sql
SELECT * FROM N_UMA_RACE
WHERE DataKubun IN ('7','A','B')
  AND Year = '{Year}' AND MonthDay = '{MonthDay}'
  AND JyoCD = '{JyoCD}' AND RaceNum = '{RaceNum}'
ORDER BY Umaban ASC
```

### 特定馬の全競走歴
```sql
SELECT * FROM N_UMA_RACE
WHERE DataKubun = '7' AND KettoNum = '{KettoNum}'
ORDER BY Year DESC, MonthDay DESC
```

### 前走データ取得
```sql
SELECT * FROM N_UMA_RACE
WHERE KettoNum = '{KettoNum}'
  AND DataKubun IN ('7','A','B')
  AND Ninki != '00'
  AND (Year < '{Year}' OR (Year = '{Year}' AND MonthDay < '{MonthDay}'))
ORDER BY Year DESC, MonthDay DESC
LIMIT 1
```

### 払戻情報取得
```sql
SELECT * FROM N_HARAI
WHERE DataKubun = '2'
  AND Year = '{Year}' AND MonthDay = '{MonthDay}'
  AND JyoCD = '{JyoCD}' AND RaceNum = '{RaceNum}'
```
