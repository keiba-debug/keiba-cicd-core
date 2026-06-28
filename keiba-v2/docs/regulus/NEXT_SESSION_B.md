# 次セッション起動プロンプト — Regulus B（レース文脈エンジン本丸）

> Session 177 の続き。これをそのまま次セッションの最初の発言に貼る。

---

Regulus B に着手したい。前回 Session 177 でモデル「Regulus」(3歳上芝オープン以上 専用・Stars系/馬単位)の Phase 0-1 と「レース文脈エンジン」の土台を作って区切った。今回は本丸の **B＝文脈で過去走を"掃除"して能力トレンドを de-confound する** をやる。

## まず読んでオリエンして
- メモリ `regulus-race-context-engine`（特に「★次セッション着手点(B)」の節）+ `feedback_specialist_for_its_own_sake` + `multi-model-naming`
- 設計正本 `keiba-v2/docs/regulus/sources/`（`00_integration_5books.md`=5冊統合の背骨 / `03_agari_x_furlong.md`=上がり3軸 / `05_course_prev_position_mineta.md`=front_ratio）
- レポート `keiba-v2/docs/ml-experiments/v9.x_turf_op_specialist_phase0.md §6`

## 既にある資産（再利用・再ビルド不要）
- front_ratio 計算基盤: `ml/nova/context_features.py`（build_horse_timeline / prev_le3=前走3角corners[-2]≤3 / add_context、リーク防止bisect）
- context付splits: `data3/ml/nova/turf_op/splits/*_ctx.pkl`、素splits `splits/{train,val,test}.pkl`
- ablation/可視化: `ml/nova/{train_turf_op,ablation_turf_op,feature_lab_report}.py`、`data3/ml/nova/turf_op/{feature_lab.html,iteration_log.json}`

## 今回のタスク（B）
1. **上がり3軸を前計算**（spec 03）: lap_times(1F刻み)末尾から `ability_speed`(上がり2F・着差補正)／`ability_stamina`(上がり1F・⚠遅い=良=符号反転注意)／`ability_power`(上がり4F・馬場/距離補正)。標準化定数はJRDB実データで再回帰。
2. **`prev_race_quality_fit`（符号付）**: 各馬の直近走を「文脈不利度」で採点＝不利文脈で凡走→隠れ能力(正)/有利文脈で好走→割引(負)。材料 = front_ratio(巻込) × 脚質 × ペース質ミスマッチ(上がり3軸 × pace_scenario)。※各過去走の文脈は2段履歴(過去走のそのまた前走)が要る。
3. **`idm_trend_clean`**: `jrdb_ls_idx_trend`/`jrdb_idm_trend` を不利文脈走割引で再計算。
4. **検証**: ablation で 素の `jrdb_ls_idx_trend`(=Regulus W の#1柱) を `idm_trend_clean` に**差し替え**て AUC が上がるか（"足す"でなく"置換"で評価）。結果を iteration_log + Feature Lab に記録。

## 成功基準
- `idm_trend_clean` が素トレンドを **AUC ≥ +0.005**（単発ノイズ超え）で上回る → 採用。同等以下 → 畳んで学びを記録（"掃除しても市場/既存特徴量を超えない"も価値ある結論）。

## 厳守する制約（前回の学び）
- **生足しは無駄**（A で実測）→ 必ず"掃除/置換"で評価する。
- **目的は予想品質（本命精度・印）・払戻エッジは期待しない**（OP市場シャープ・妙味≠勝率＝前走上がり1位は単回72円）。
- **リーク防止**: 全特徴量は対象レース日より前の走のみ。front_ratio/sandwich は確定枠順+前走で事前計算。
- **単発ランは ±0.005 がノイズ**。信じるのは方向と大きな差（不安なら複数seed平均）。
- **非定常性**: 枠バイアスは開催前半/後半・コース改修・経年で反転 → 近3年窓。生 front_ratio で枠は決まらない。
- **上がり1F は「遅い=スタミナ高=良い」**（素朴に小さいほど良いで入れると逆効果）。
