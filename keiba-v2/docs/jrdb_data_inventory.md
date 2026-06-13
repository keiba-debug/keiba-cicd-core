# JRDB全データ棚卸し v2（2026-06-13 / Session 155 コード裏取り版）

> **このドキュメントはマスター（git管理）。** メモリ [[jrdb-expansion]] は参照のみ。
> v1（2026-04-01）は Session 115 以前の記述のまま乖離していたため、**全フィールドをコードで裏取りして全面改訂**。
> 裏取りソース: `jrdb/parser.py`, `jrdb/downloader.py`, `builders/build_jrdb_index.py`,
> `ml/features/jrdb_features.py`, `ml/features/track_bias_features.py`, `ml/experiment.py`

---

## 0. 6段パイプラインの考え方

JRDBデータが「モデルに効く」までには6段ある。各段で落ちる。

```
① DL          jrdb/downloader.py の DATA_TYPES に載っているか
② パース       parser.py の parse_xxx_line が return dict に入れているか
③ インデックス  build_jrdb_index.py が index[key] に格納しているか  ← ここで落ちると ④以降から見えない
④ 特徴量計算    jrdb_features.py / track_bias_features.py が値を読んで jrdb_* 特徴量にしているか
⑤ モデル投入    experiment.py の FEATURE_COLS_VALUE / P_ONLY に入っているか（MARKET除外に注意）
⑥ UI表示       web/ が predictions 経由で見せているか
```

**重要な発見（Session 155）**: KYI は ③インデックス層では約75フィールドをほぼ全部格納済み。
未活用フィールドの大半は **④特徴量計算層で書いていないだけ＝再インデックス不要、特徴量関数を書けば届く**。
一方 SRB / UKC は ③まで到達（インデックス構築済み）しているのに ④の消費がゼロ＝完全死蔵。

---

## 1. データ取得・鮮度の現状（① DL段）

### DL対応済み（downloader.py DATA_TYPES に登録、8種が実運用）

| コード | 名称 | 提供タイミング | raw最新 | 運用 |
|--------|------|--------------|---------|------|
| **SED**(+**SRB**同梱) | 成績データ＋レース分析 | 木曜午後 | 〜6/7 | keiba-data-prep ① で取得 |
| **KYI** | 競走馬データ（事前IDM） | 開催前日19時 | 〜6/7 | keiba-data-prep ② |
| **KAA** | 開催データ（馬場・バイアス）※LZH | 前日 | 〜6/7 | ② |
| **CYB** | 調教分析 | 前日 | 〜6/7 | ② |
| **CHA** | 調教本追切 | 前日 | 〜6/7 | ② |
| **KKA** | 競走馬拡張（条件別成績・血統統計） | 前日 | 〜6/7 | ② |
| **UKC** | 馬基本（血統・系統コード） | 前日 | 〜6/7 | ② |
| **JOA** | 情報データ（CID/LS/消し馬） | 前日 | 〜6/7 | ② |

> raw: `C:/KEIBA-CICD/data3/jrdb/raw/{TYPE}/`。直近は 2026-06-06 に一括DL、6/7開催分まで揃っている。

### DL対応コードはあるが未取得（downloader.py には登録済み・raw に無い）

| コード | 名称 | 中身 | 宛先候補 |
|--------|------|------|---------|
| **TYB** | 直前情報 | パドック指数・馬具変更・脚元情報・直前オッズ/印・馬体/気配コード | パドック系・[[danger-model-project]]・[[favorite-betrayal-project]] |
| **SKB** | 成績拡張 | 特記/馬具/脚元コード+各コメント40字 | 馬具変更・脚元リスク |
| **HJC** | 払戻情報 | 全券種払戻金 | バックテスト決済の照合（現状は別ソース） |

> TYB は「発走15分前提供」なので、取り込むと vb_refresh 相当の**直前処理パイプライン**が要る＝他より運用コスト重い。

### downloader 未対応（仕様書は `data3/jrdb/docs/` に48ファイル取得済み）

OZ/OW/OU/OT/OV（基準オッズ全券種）、ZE/ZK（前走スナップ）、BA（番組）、KZ/KS・CZ/CS（騎手/調教師マスタ）、MZ/MS（抹消馬）、UK（馬基本=UKCの別系統）。

---

## 2. インデックス構築状況（③段）

`builders/build_jrdb_index.py` → `C:/KEIBA-CICD/data3/indexes/jrdb_{type}_index.json`
（ML特徴量側が直読みするのはこちら。`data3/ml/` ではなく `data3/indexes/`）

| インデックス | サイズ | 最終構築 | キー形式 | エントリ概数 |
|-------------|--------|---------|---------|------------|
| jrdb_sed_index | 173 MB | 2026-06-06 | `{ketto_num}_{race_date}` | 過去成績全件 |
| jrdb_kyi_index | 500 MB | 2026-06-06 | `{ketto_num}_{race_date}` | 〜30万 |
| jrdb_kka_index | 111 MB | 2026-06-06 | `{racekey}_{umaban}` | 〜30万 |
| jrdb_cyb_index | 98 MB | 2026-06-06 | `{racekey}_{umaban}` | 〜30万 |
| jrdb_joa_index | 72 MB | 2026-06-06 | `{racekey}_{umaban}` | 〜30万 |
| jrdb_cha_index | 66 MB | 2026-06-06 | `{racekey}_{umaban}` | 〜30万 |
| **jrdb_srb_index** | 18 MB | 2026-06-06 | `{jrdb_race_key}` | 〜2万R |
| **jrdb_ukc_index** | 13 MB | 2026-06-06 | `{ketto_num}` | 〜3.7万頭 |
| jrdb_kaa_index | 0.8 MB | 2026-06-06 | `{venue_code}_{race_date}` | 開催日×場 |
| ~~jrdb_rca_index~~ | 15 MB | 2026-03-03 | — | **謎の旧インデックス**。現行 parser/builder に rca 該当なし。要素性確認・おそらくレガシー |

> **9種すべて構築済み**（v1 では「UKC index ✗」と書いていたが誤り。実際には構築されている）。

---

## 3. データ種別ごとの 使用状況サマリー

各行: パース済F数 → ④特徴量化された数 → ⑤モデル投入。★=未活用の有望フィールド。

| 種別 | パース | 特徴量化 | モデル投入 | 死蔵の度合い |
|------|-------|---------|-----------|------------|
| SED | 42 | 17 | 17 | 中（指数系は活用済、生成績・10時オッズ系が未使用） |
| KYI | ~75 | 15 | **9**（6個はMARKET除外） | **大（展開予想詳細・印コード・激走タイプ等が丸ごと未使用）** |
| KAA | 22 | 6 | 6 | 小（ほぼ活用、天候のみ未使用） |
| CYB | 22 | 5 | 5 | 中（調教タイプ・コース種別・調教量が未使用） |
| CHA | 19 | 3 | 3 | 中（乗り役・併せ相手・追切タイムが未使用） |
| KKA | 31 | 3 | 3 | **大（条件別成績20組超が未使用）** |
| JOA | 19 | 6 | 3（P専用、3個はMARKET除外気味） | 中（CID系は活用済、EM消し印・BB印が未使用） |
| **SRB** | 14 | **0** | **0** | **完全死蔵（ハロンタイム18区間・コーナー別バイアス・コメント500字）** |
| **UKC** | 20 | **0** | **0** | **完全死蔵（父系統/母父系統コード）** |

> JRDB由来のML特徴量は計 **64個**（JRDB_FEATURE_COLS 53 + TRACK_BIAS 11）。
> うち KAA由来6 + SED由来5 が track_bias_features。残り53が jrdb_features。

---

## 4. 各種別の詳細（パース済フィールド × 使用状況）

### SED（成績データ）— `parse_sed_line` 42フィールド

**✅特徴量化（17 → SED由来 jrdb_features 12 + track_bias 5）**:
`idm`(idm_last/avg3/max5/trend/std), `agari_idx`(last/avg3), `ten_idx`(last/avg3),
`deokure_adj`(deokure_count5), `furi_adj`(furi_count5), `joushou_code`(joushou_mean),
`mae/naka/ato_furi_adj`+`baba_sa`(F:P専用), `race_pace`+`horse_pace`(pace_match/mismatch),
`corner4`+`num_runners`+`finish_position`(track_bias: collapse/corner4_ratio/high_pace/bias経験)

**❌未使用（25）**: `soten`(IDMに統合), `pace_adj`/`ichi_tori_adj`/`race_adj`(補正、IDM内包),
`course_tori`, `pace_idx`/`race_pace_idx`, `front_3f`/`rear_3f`★(上がり分析), `corner1-3`,
`odds`/`popularity`/`place_odds_low`★(確定オッズ→後知恵注意), `futan`, `horse_weight`★(馬体重変動),
`abnormal`, `time_raw`, `distance`/`track_code`(条件), `jockey_code`/`trainer_code`(リンク)

### KYI（競走馬データ）— `parse_kyi_line` ~75フィールド（**インデックスにもほぼ全部格納済み**）

**✅特徴量化（15 → ただしモデル投入は実質9）**:
- D系（KYI事前指数, 9）: `pre_idm`,`sogo_idx`,`info_idx`,`jockey_idx`,`training_idx`,`stable_idx`
  → **この6個は MARKET_FEATURES で全モデル除外**（市場相関でVB差別化を壊すため、v7.0/v7.0a）。
  実際にモデルに入るのは `gekisou_idx`,`start_idx`,`deokure_rate` の3個。
- G系: `kyakushitsu`,`distance_aptitude`(P専用)

**❌未使用だがインデックス到達済み＝特徴量関数を書くだけ（再構築不要）**:
| フィールド | 内容 | 宛先候補 |
|-----------|------|---------|
| `gekisou_type`★★★ | 激走タイプ分類 | [[sirius-design]] の核 |
| `manken_idx`/`manken_mark`★★ | 万券指数/印 | sirius |
| `mark_sogo/idm/info/jockey/stable/training/gekisou`★★★ | JRDB独自印7種 | 合議系・印一致度 |
| `tokutei_*`/`sogo_*`(◎○▲△×の数)★★ | 専門紙印の集約 | 合議系 |
| `pred_dochu/3f/goal_order/diff/uchi_soto`★★★ | 展開予想詳細ポジション | eclipse/tide（展開）|
| `gekisou/ls/ten/pace/agari/position_idx_rank`★★ | 各指数の出走馬中順位 | 相対評価 |
| `koukyu_flag`★★ | 降級フラグ(1:降級,2:2段階) | polaris |
| `blinker`★★ | ブリンカー(1:初,2:再,3:継続) | polaris/sirius |
| `omo_tekisei`★★ | 重適性コード | corona/polaris |
| `turf_aptitude`/`dirt_aptitude`★★ | 芝ダ適性(◎○△) | polaris |
| `nyuukyuu_*`(何走目/何日前/年月日)★★ | 入厩情報 | 調教系・danger |
| `houboku_rank`(A-E)/`kyuusha_rank`(1-9)★★ | 放牧先/厩舎ランク | 調教系・外厩 |
| `jockey_expected_win/place_rate`★★ | 騎手期待単勝率/3着内率 | 騎手系 |
| `wakutei_weight`/`_diff`★ | 枠確定馬体重/増減 | 馬体重変動 |
| `rotation`★ | ローテ間隔(金曜日数) | 降格ローテ |
| `training_arrow`/`stable_eval`★ | 調教矢印/厩舎評価 | 調教系 |
| `yusou_kubun`★/`hizume_code`/`kyuuyou_reason`/`flags`(初芝/初ダ等) | 各種 | — |
| `ninki_idx`/`base_*odds`/`base_*popularity` | 市場系 | MARKET相当・後知恵注意 |

### SRB（成績レースデータ）— `parse_srb_line` 14フィールド — **特徴量0 / 完全死蔵**

| フィールド | 内容 | 宛先候補 |
|-----------|------|---------|
| `furlong_times`★★★ | 18区間ハロンタイム(0.1秒) | [[lap-analysis]]・ラップ系。レースレベルだが過去走join可 |
| `bias_1/2corner/mukousei/3/4corner/straight`★★★ | コーナー別トラックバイアス(内中外) | course-bias-alert・KAA補完 |
| `pace_up_position`★★ | ペースアップ位置(残りハロン) | tide（ペース分類）|
| `corner1-4_positions`★ | コーナー通過順位(文字列64字) | 構造化要・展開図 |
| `race_comment`★ | レースコメント500字 | NLP（comment-nlp構想）|

> SRBはインデックス済み（18MB, 〜2万R）。読み込み配線だけで着手可能。最もアルファが残っている領域。

### UKC（馬基本データ）— `parse_ukc_line` 20フィールド — **特徴量0 / 完全死蔵**

`sire_code`★★/`bms_code`★★（父・母父系統コード→血統モデル vega）, `sire_name`/`dam_name`/`broodmare_sire`,
`birth_date`/`sire/dam/bms_birth_year`, `sex_code`/`coat_color`, `owner_name`/`breeder_*`/`origin`, `retired_flag`。
> ketto_num キーで馬単位join可。系統コードが血統モデルの即戦力。

### CYB（調教分析）— `parse_cyb_line` 22フィールド

**✅特徴量化（5）**: `oikiri_idx`,`shiage_idx`,`shiage_change`,`training_eval`,`oikiri_idx_prev_week`
**❌未使用**: `training_type`(01-11)★, `course_type`(坂路/W/ダ…)★, `training_volume`★, `training_emphasis`(テン/中間/終い)★, `training_eval_class`(A-D)★, 各コース調教回数(turf/wood/dirt/pool…), `training_comment`(40字)

### CHA（本追切）— `parse_cha_line` 19フィールド

**✅特徴量化（3）**: `oikiri_idx`,`shimai_e_idx`,`oikiri_type`
**❌未使用**: `nori`(乗り役:本番騎乗なら好調)★★, `oikiri_aite`(併せ相手の質)★★, `ten_e`/`chukan_e`/`shimai_e`(追切タイム秒)★, `ten_e_idx`/`chukan_e_idx`★, `kai`(追切回数), `youbi`/`training_date`/`oikiri_course`

### KKA（競走馬拡張）— `parse_kka_line` 31フィールド

**✅特徴量化（3）**: `jrdb_results`(total_runs/win_rate), `dam_best_rentai`
**❌未使用（条件別成績の宝庫・各ZZ9*4=[1着,2着,3着,着外]）**:
`track_results`★★, `rotation_results`★★, `slow_pace_results`/`fast_pace_results`★★★(ペース別),
`short_dist_results`/`long_dist_results`★★(距離別), `season_results`/`weight_results`,
`s/n/h_pace_level`, `turf_distance/track/aptitude/surface/blinker`★★, `dirt_surface`,
`bms_best/place_rentai`/`dam_place_rentai`/`*_avg_distance`★(母父産駒統計→vega)

### JOA（情報データ）— `parse_joa_line` 19フィールド

**✅特徴量化（6 → P専用、CID系は polaris 2.0 の核・CID素点が重要度ダントツ1位）**:
`cid`,`cid_score`,`ls_idx`（J系）, `cid_score`/`ls_idx`の時系列（L系: last/avg3/trend/vs_avg）
**❌未使用**: `em`(消し印1:該当)★★, `bb_turf_dirt`/`bb_turf`(BB血統印)★, `bb_*_win/place_rate`(‰)★, `cid_choushi`/`cid_sani`(CID内訳), `kakutei_odds`/`kakutei_place_odds`(確定→後知恵注意)

### KAA（開催データ）— `parse_kaa_line` 22フィールド

**✅特徴量化（6）**: 芝内外/直線5区画/ダート内外/走路面コンディション → track_bias_features でほぼフル活用
**❌未使用**: `weather_code`★(天候), `kaisai_kubun`(関東/関西/ローカル), `turf_sa`/`dirt_sa`(馬場差・raw), `turf_middle`/`dirt_middle`

---

## 5. 優先度付け（宛先プロジェクト紐付け・闇雲に足さない）

> 検証ゲートは Session 153-154 の確立方針を適用:
> 新特徴量は experiment の OOS AUC / gap-ROI + ブートCI で判定。
> **「買い目層への新規介入はROIを動かさない/逆効果。効くなら特徴量、効かないなら表示・運用へ」**。
> 効果見積り（"+5%"等）は出さない — 実験でしか分からない（CIDも回したら重要度1位だった世界）。

### 着手コスト×宛先で3段

**A. 即着手可（再インデックス不要・特徴量関数のみ）**
1. **KYI 激走タイプ + 万券指数 + 印コード7種** → [[sirius-design]]（設計書で弾を待っている状態）
2. **KYI 入厩情報 + 放牧先ランク + 降級フラグ + 輸送区分** → [[danger-model-project]]（次回主要ミッションの特徴量源）
3. **KYI 展開予想詳細（道中/後3F/ゴール順位・内外）** → eclipse/tide（Nebula系展開）
4. **KKA 条件別成績（ペース別/距離別/トラック別）** → [[niche-specialist-strategy]] の条件判定

**B. 配線必要（インデックス到達済み・読み込み未配線）**
5. **SRB ハロンタイム18区間 + コーナー別バイアス** → [[lap-analysis]]・course-bias-alert。完全死蔵＝アルファ残存の本命
6. **UKC 父系統/母父系統コード** → vega（血統モデル）

**C. 新規取得＋運用パイプライン必要（重い）**
7. **TYB（パドック指数・馬具変更・脚元情報）** → パドック系・danger・favorite-betrayal。発走15分前提供のため直前処理が要る

### 進め方の推奨
1段ずつ。1特徴量グループ追加 → experiment OOS で AUC/gap-ROI + ブートCI → 効けば本採用、効かなければ表示/運用UIへ回す。
まず **A群（KYI特徴量関数、再インデックス不要）** が最小コスト。次に B群の SRB（死蔵解消＝期待値最大）。

---

## 6. v1からの主な訂正点（コード裏取り結果）

- v1「UKC index ✗」→ **誤り。9種すべてインデックス構築済み**（SRB/UKCも 6/6 構築）。死蔵は④特徴量層であって③ではない。
- v1「KYI 80フィールド・特徴量化9個」→ **インデックスには約75フィールド格納済み**。未活用は特徴量関数未実装が理由で、再構築は不要。
- KYI事前指数のうち `pre_idm/sogo/info/jockey/training/stable` の6個は **MARKET_FEATURES で全モデル除外**（v1未記載の重要事実。市場相関でVB差別化を壊すため意図的に外している）。
- SED の確定オッズ・JOA の確定オッズは「後知恵」リスクあり（[[feedback_odds_gate_hindsight]]）。特徴量化する場合は predictions ソース再検証必須。
- `jrdb_rca_index.json`（3/3, 15MB）は現行コードに該当なしの **謎レガシー**。要棚卸し。
