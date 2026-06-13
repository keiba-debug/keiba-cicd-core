# E-001 品質メタ標準化 仕様書 v1.2（Session 153 確定版）

> **v1.2 変更（Session 153 / カカシ確定）**: ①未決 Q1（主要metric）= シズネ仮置きを承認・確定（§5/§8）②未決 Q3（E-002減点の主役）= **ci95.lower 一本＋selected/source 個別係数**で確定（§7/§8）③確認2への対応として **coverage 検証ステップ**を運用配線に追加（§6）④**E-002 のスコープを「低信頼減点（precision）」に純化**し、疲労・条件悪化による凡走リスク割引は `danger-model-project` に別建て（§7）。これで E-001 は仕様 done、実装は E-010 へ。
> v1.1（Session 152）: v1.0草案へのシズネ独立レビュー `E001_review_shizune.md`（🔴4/🟡11/🟢7、全指摘 file:line 裏取り済み）を全面反映。
> 関連: [[02_enhancement_backlog]] E-001/E-010 / メモリ `analysis-reuse-project`・`danger-model-project` / 先行事例=Session152 の `cache_freshness` メタ（鮮度の標準化）。本件は「信頼性」の標準化。

## 0. 原則（S-12）

**quality は精度（precision）のメタであり、妥当性（bias）は保証しない。** 分母の定義（例: 出遅れ率は hassou コメント有レースのみが分母）・選抜バイアス・データ鮮度は quality では直らない。分母定義は各分析の責任。E-006 の表示文言でも「CI付き＝正しい数字」と誤読させないこと。

## 1. 目的

各分析JSONの統計エントリに「**その推定値どれだけ信用できるか**」を表す共通メタを付ける。今は `sample_count` 止まりで「n=3のたまたま勝率50%」と「n=300の確かな勝率50%」を区別できず、**E-002 低信頼データ減点 / E-005 理由タグ / E-006 信頼度ヘッダ**の判定材料が無い。bridge_review 8本全部が「CI95欠落」を指摘＝全オプションの共通ボトルネック。

## 2. 共通スキーマ（統計エントリに `quality` 入れ子で付与）

```json
"quality": {
  "metric": "top3_rate",                       // ★必須: どの指標のCIか（B-1）
  "ci95": { "lower": 0.231, "upper": 0.448 },  // 算出不能なら null
  "effective_n": 81,                           // 常に raw 観測数 n（n+α+β ではない）
  "stability_flag": "stable",                  // stable | drift | insufficient
  "algo": "wilson_binomial",                   // 下記4種
  "selected": true,                            // 任意: 多数候補からの選抜エントリ（S-4）
  "source": "fallback:G1",                     // 任意: fallback時のみ（S-6）
  "original_n": 9                              // 任意: fallback時の固有n（S-6）
}
```

- Phase 1 は**分析ごとに主要 metric 1つ**（§5表）。複数指標が要る場合は `"quality": {"top3_rate": {...}}` の指標名キー形式に拡張。
- `selected=true`（調教師 best_patterns・接戦 ranking 等、多数比較からの選抜）のエントリは、E-002 で点推定でなく **ci95.lower を入力に使う**（勝者の呪いの部分相殺、S-4）。根治（split-sample/FDR）はスコープ外と明記。

## 3. 算出アルゴリズム

| algo | 適用 | 必要データ | 式 |
|---|---|---|---|
| `wilson_binomial` | 率・非選抜・n大 | hits, n | Wilson score（z=1.96） |
| `bayesian_beta_binomial` | 率・小標本/選抜系/平滑化済み系列 | hits, n, **指標別prior（必須）** | 事後 Beta(α+hits, β+n−hits) の 2.5/97.5%ile |
| `mean_se` | **連続量**（RPCI・**IDM**） | mean, stdev, n（RPCIは weights） | mean ± t·SE（n≥30 は z=1.96、n<30 は t分布 N-1） |
| `none` | 上記不可 | — | ci95 = null |

### 指標別 prior（B-4 — 一律デフォルト禁止・必須引数）

汎用則: **α = base_rate×S, β = (1−base_rate)×S, S ≈ 10〜13**（事前=10走分程度の重み）。「踏襲」すべきは定数でなくこの設計哲学（`build_sire_stats.py:39-43` が既に win/top3 で使い分け済み）。

| metric | base_rate | prior |
|---|---|---|
| win_rate | ≈0.077 | Beta(1, 12)（既存踏襲） |
| top3_rate | 0.25 | Beta(2.5, 7.5)（既存踏襲） |
| close_win_rate | 0.50（接戦=2頭競り合いの構造上） | Beta(5, 5) |
| slow_start_rate | 0.216（=33,749/156,038） | Beta(2.6, 9.4) |

prior 定数は `quality_meta.py` に**一元化**し、`ml/features/pedigree_features.py:19-26` の複製は import に置換（E-010）。

### 整合規則（S-5）

- **rate がベイズ平滑化済みの分析（血統等）は ci95 も同じ事後分布・同一 prior で出す**。点推定とCIの生成系列を混ぜない（Wilson(raw)×事後平均の混在は小標本で点推定がCI外に出る）。
- effective_n は常に raw n。**平滑化済み分析に effective_n の追加減点を重ねない**（二重〜三重補正の禁止 → §7）。

### stability（S-2 — 恣意閾値を廃止し CI ベース判定に一本化）

- 入力: `year_data = {year: {hits, n}}`（率）/ `{year: {mean, stdev, n}}`（連続量）。None/欠損年（接戦の `close_win_rate: None` 年等）はスキップ。
- **drift ⇔ 最新年の値が全期間 ci95 の外、かつ最新年 n ≥ 20**。year_data があり上記でない → stable。
- year_data 無し or 最新年 n<20 → insufficient（「安定」と誤読させない）。
- 注意: 最新年は部分年（季節偏り）。鮮度（coverage）は§6運用配線が担保し stability と混同しない。率/連続量で同一ロジック。

### 連続量（RPCI / IDM）の規定（B-3, S-10）

- **IDM**: 対象は `winner.mean`（n=winner_count）の mean_se。`winner_count/horse_count` は≈1/頭数の構造定数で率ではない（bayesian 適用不能、B-3）。
- **RPCI**: 運用閾値が weighted_mean±0.5σ 基準のため **ci95 も weighted_mean 基準**: SE=√(Σw²σ²)/Σw、effective_n=(Σw)²/Σw²。thresholds 自体の不確実性は別物と注記。同日同コース相関で SE やや過小（N-2、注記で可）。
- 表示語彙: これは「**基準値（平均）の推定誤差**」であり「レース毎のばらつき(σ)」ではない（n=2789 で CI幅±0.04 の極狭を「安定したコース」と誤読させない、E-006 文言注意）。

## 4. 共通ヘルパ `analysis/quality_meta.py`（実装は E-010）

```python
def quality_meta(*, metric: str, algo: str,
                 hits=None, n=None, prior=None,        # 率系。bayesian は prior 必須
                 mean=None, stdev=None, weights=None,  # 連続量系
                 year_data=None, min_n=None,
                 selected=False, source=None, original_n=None) -> dict
```

- **prior にデフォルト値を置かない**（必須引数化、B-4）。
- min_n は分析別（§5表）。n < min_n → stability_flag="insufficient"（ci95 自体は出してよい）。
- **JSON walk は各 builder の責務**（実物は3〜4層ネストで一律 Dict/Array ループ不可、S-7）。ヘルパは1エントリの計算のみの純関数。
- pytest 境界: Wilson/Beta/mean_se/weighted SE/stability/None年スキップ/prior未指定エラー。
- `hits = round(rate×n)` の復元は**全面禁止**（血統条件別はベイズ事後平均で式自体が誤り、丸め誤差が静かに乗る。生カウントは builder の手元に既にある — B-2）。

## 5. 対象ファイル一覧

| 分析 | 出力JSON | quality付与対象パス | 主要metric | hits/n | algo / prior | min_n | builder改修 | Phase |
|---|---|---|---|---|---|---|---|---|
| 調教師パターン | `data3/analysis/trainer_patterns.json` | `trainers.*.best_patterns[*]` | top3_rate | **builder出力に追加**（p_wins/p_top3/p_n は :362 算出済み・捨ててるだけ） | bayesian/top3 + **selected=true** | 8（既存足切り） | trainer_patterns.py 生カウント出力 | **1** |
| 調教分析 | `data3/analysis/training_analysis.json` | `overall.by_lapRank.*`（他ネストは Phase 2） | top3_rate | 同上（wins/top3 :189 算出済み） | wilson（n大・非選抜） | 5（既存） | training_analysis.py 生カウント出力 | **1** |
| 出遅れ | `data3/analysis/slow_start_analysis.json` | `jockey_ranking[*]` のみ（**horse_stats 15,208件 / recent_incidents は対象外**、S-7） | slow_start_rate | slow_starts / total_rides（直接） | wilson | 30（既存） | 不要 | **1** |
| 騎手接戦 | `data3/analysis/jockey_close_finish.json` | `ranking[*]`（close_by_track/distance は Phase 2） | close_win_rate | close_wins / close_total（直接） | bayesian/close + **selected=true** | 10（既存） | 不要 | **1**（前提: 再生成済+運用配線、S-3） |
| 血統 | `data3/indexes/sire_stats_index.json` | `sire.*` / `bms.*` / `dam.*` の baseline（条件別は生カウント無→Phase 2） | top3_rate | top3 / total_runs（直接） | **bayesian**/top3（rate が事後平均のため系列統一、S-5） | 10（既存） | 条件別生カウント出力（Phase 2） | **1**（サイズ増を E-010 実測、N-4） |
| IDM | `data3/analysis/idm_standards.json` | `by_grade.*`（`by_race_name` は count=2-4 でこそ必要→Phase 2） | winner_idm_mean（連続量） | — | mean_se | 既存(10/30)に整合 | fallback 情報の quality 複写（source/original_n、S-6） | 2-3 |
| RPCI | `data3/analysis/race_type_standards.json` | `by_distance_group.*`（courses/by_baba 等4階層は Phase 2 判断） | rpci_weighted_mean（連続量） | — | mean_se（weighted） | 10（既存） | 年別集計レイヤ（stability用、Phase 2） | 2-3 |
| コース辞典 | web 静的TS | — | — | — | none | — | — | 対象外 |

## 6. 段階実装計画

- **Phase 1（E-010）**: 前提① jockey_close_finish 再生成+`keiba-data-prep`①-2配線（S-3、Session 152 対応済み）／前提② builder 生カウント改修（trainer_patterns / training_analysis）→ `quality_meta.py`+pytest → 上記 Phase 1 の5分析に適用。**`metadata.schema_version="quality_meta/1"` と `coverage:{from_date,to_date}` を Phase 1 から必須**（S-11/S-3。slow_start には coverage 既存）。
- **Phase 2**: ネスト条件別（接戦 by_track/distance・血統条件別=builder改修後・IDM by_race_name・RPCI 階層）+ 年別集計レイヤ（RPCI/IDM/調教師）で stability 拡充。
- **Phase 3**: RPCI/IDM の mean_se 本適用。
- **Phase 4**: web 信頼度/鮮度ヘッダ（E-006）全面接続。既存 `confidence`(high/medium/low) は quality 導入後 **deprecated**（削除せず表示を quality 由来に統一、S-9）。
- **運用配線（S-3 / 確認2 確定）**: 品質メタは「生成時点の信頼性」しか語れない — **鮮度は運用配線（keiba-data-prep ①-2 に全分析の再生成）で担保**。jockey_close_finish が未配線だった（MLキャッシュ凍結と同じ構造要因）→ Session 152 で配線済み（①-2 に8分析全部入っていることを Session 153 で実体確認）。
  - **★ coverage 検証ステップ（Session 153 追加・確認2の本質）**: 「再生成が走った」と「正しい期間のデータになった」は別。Session 153 実測で **8分析中 `coverage:{from_date,to_date}` を持つのは出遅れ1つだけ**、残り7つは `created_at`（生成時刻）のみ＝「いつまでのレースが入っているか JSON から判別不能」（jockey_close_finish が 3/17 で3ヶ月凍結しても created_at では気づけなかった主因）。対策2点を E-010 で必須化:
    1. **全分析に `coverage:{from_date,to_date}` を Phase 1 から付与**（§2/§6 Phase 1。出遅れ `build_slow_start_analysis.py:313-319` が手本）。これで鮮度が JSON 自体に刻まれ「鮮度不明」が原理的に消える。
    2. **keiba-data-prep ①-2 の直後に coverage 検証**（②-4.5 の MLキャッシュ検証と同思想）: 再生成後、各分析の `coverage.to_date` が直近開催日に到達したかを確認し、未到達なら警告。これで「品質メタ付きだが鮮度不明」の常態化を防ぐ。
  - **（別件・要追検証）元データ鮮度**: ①-1 は seiseki スクレイプ中心で、確定JRDB(SED等)/確定SE_DATA は現状 ②-2 でしか落ちない疑い。IDM(JRDB依存)・血統(SE依存)が①で本当に最新元データを食っているかは E-010 とは別に検証する（[[ml-cache-staleness-incident]] 同型リスク）。

## 7. E-002 連携（出口設計 / Q3 確定）

### スコープ純化（Session 153 確定）

- **E-002 は「統計的に低信頼な分析データの寄与を割り引く」＝精度(precision)の減点のみ**。§0 原則どおり「数字が不確か（n小・CI広）だから控えめに使う」だけを担う、薄いオプションに保つ。
- **疲労・条件悪化・休み明け・距離/コース替わり・斤量・降格ローテ等による「馬が凡走する」リスク割引は E-002 に入れない** → `danger-model-project`（凡走確率モデル）に別建て。理由: それは分析データの信頼性ではなく**馬の実体リスク（妥当性/bias 側）**で、特徴量設計・walk-forward 検証・composite割引/3着回避/荒れ予測まで要する本格モデル。E-002 に背負わせると両方が中途半端になる。
- **両者は出口だけ合流**（composite 評価への割引として）が、**入力・検証・開発ペースは完全分離**。E-002=「データが薄いから割り引く」、凡走モデル=「この馬は飛ぶから割り引く」。割引理由が別軸なのでログ・説明（E-005 理由タグ）でも区別できる。

### E-002 が使う材料（Q3 確定: ci95.lower 一本＋個別係数）

- E-002 は **metric + ci95 + effective_n（+ selected/source）だけで動ける**。stability_flag は E-006（表示）向け — E-002 の依存に入れない。
- **減点の主役 = `ci95.lower` 一本**（Q3 確定）。小標本ほど下限が自然に下がるので、CI幅・effective_n・stability を掛け合わせる多段補正は採らない。
  - `selected=true`（調教師 best_patterns・接戦 ranking 等の選抜系）は点推定でなく ci95.lower を入力（勝者の呪いの部分相殺）。
  - `source=fallback` は `original_n` を見て個別係数（借用値が減点を素通りするのを防ぐ）。
- **禁止**: 平滑化済み点推定（血統等）への effective_n 追加減点（事後平滑化＋CI幅＋小n減点の三重補正で小標本が沈み過ぎ、**過小評価馬の妙味を自分で消す**方向に働く。[[place-calibration-bias]]「相手は広く持て」と逆行）。
- algo 横断で正規化が要る場合のみ: `rel_width=(upper−lower)/指標スケール` か tier 導出表を E-002 実装時に確定（ci95.lower 主役で足りるなら不要）。

## 8. 完了条件・未決事項

- ✅ 本仕様書 v1.2（シズネレビュー全面反映＋未決3件確定）＋対象一覧（§5）
- E-010 受け入れ基準: pytest green / 対象エントリ quality 付与率100% / ci95 null 率実測 / **coverage 付与率100%＋to_date 検証**（§6）/ ファイルサイズ増実測（N-3/N-4）/ scipy 依存確認（N-7）
- **確定事項（Session 153・ふくだ「すすめてOK」承認）**:
  - ✅ **Q1（主要metric）**: §5表のとおり確定 — 調教師=top3_rate / 調教=top3_rate / 出遅れ=slow_start_rate / 血統=top3_rate / 接戦=close_win_rate。根拠=本線がワイド/複勝堅実（[[character-betting-personas]]・bet-template-lab）で買い目に直結するのは複勝圏率。win_rate は Phase 2 で複数指標キー形式が要れば追加。
  - ✅ **Q2（再生成・運用配線）**: Session 152 で①-2 配線済み＋Session 153 で coverage 検証ステップを追加（§6）。
  - ✅ **Q3（E-002減点の主役）**: `ci95.lower` 一本＋selected/source 個別係数で確定（§7）。三重補正は禁止。
- **➡ 次工程 E-010（実装）**: builder 生カウント改修（trainer_patterns / training_analysis）→ `analysis/quality_meta.py`＋pytest → Phase 1 の5分析に quality＋coverage＋schema_version 付与 → keiba-data-prep ①-2 後の coverage 検証配線。
