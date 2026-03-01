import { cn } from '@/lib/utils';
import type { MlExperimentResultV2, RoiAnalysis } from './types';

export const TABS = [
  { key: 'overview', label: '概要' },
  { key: 'value', label: 'Value分析' },
  { key: 'roi', label: '的中・回収' },
  { key: 'picks', label: 'VB検証' },
  { key: 'predictions', label: 'レース検証' },
  { key: 'importance', label: '特徴量重要度' },
] as const;

export type TabKey = (typeof TABS)[number]['key'];

export function MetricCard({
  label,
  value,
  highlight,
  color,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  color?: 'blue' | 'green' | 'emerald';
}) {
  const colors = {
    blue: 'border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-950/30',
    green: 'border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-950/30',
    emerald: 'border-emerald-300 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-950/30',
  };
  return (
    <div
      className={cn(
        'rounded-lg border p-3',
        highlight && color
          ? colors[color]
          : 'border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800'
      )}
    >
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className="mt-1 text-xl font-bold tabular-nums">{value}</div>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function normalizeResult(raw: any): MlExperimentResultV2 {
  if (raw.version === '2.0') return raw as MlExperimentResultV2;

  const d = raw;

  // --- Model key migration: old → new ---
  // place (was: accuracy→DELETE, value→place)
  // win (was: win_accuracy→DELETE, win_value→win)
  // aura (was: regression_value→aura)
  if (d.models) {
    if (!d.models.place && d.models.value) d.models.place = d.models.value;
    if (!d.models.win && d.models.win_value) d.models.win = d.models.win_value;
    if (!d.models.aura && d.models.regression_value) d.models.aura = d.models.regression_value;
  }

  // Normalize feature_importance labels for all models
  for (const modelKey of ['place', 'win', 'accuracy', 'value', 'win_accuracy', 'win_value'] as const) {
    const m = d.models?.[modelKey];
    if (!m) continue;
    if (m.feature_importance) {
      for (const fi of m.feature_importance) {
        if (!fi.label) fi.label = fi.feature;
      }
    }
    if (m.metrics) {
      m.metrics.precision = m.metrics.precision ?? 0;
      m.metrics.recall = m.metrics.recall ?? 0;
      m.metrics.f1 = m.metrics.f1 ?? 0;
    }
  }

  // Normalize regression model feature_importance labels
  const auraModel = d.models?.aura ?? d.models?.regression_value;
  if (auraModel?.feature_importance) {
    for (const fi of auraModel.feature_importance) {
      if (!fi.label) fi.label = fi.feature;
    }
  }

  let hitAnalysis = d.hit_analysis;
  if (hitAnalysis && !Array.isArray(hitAnalysis)) {
    // Migrate hit_analysis keys: value→place, value_v2→place_v2, regression_v2→aura_v2
    if (!hitAnalysis.place && hitAnalysis.value) hitAnalysis.place = hitAnalysis.value;
    if (!hitAnalysis.place_v2 && hitAnalysis.value_v2) hitAnalysis.place_v2 = hitAnalysis.value_v2;
    if (!hitAnalysis.aura_v2 && hitAnalysis.regression_v2) hitAnalysis.aura_v2 = hitAnalysis.regression_v2;
  }

  const roiRaw = d.roi_analysis;
  let roiNormalized;
  if (roiRaw?.place_model || roiRaw?.accuracy_model) {
    // Migrate roi_analysis keys
    if (!roiRaw.place_model && roiRaw.value_model) roiRaw.place_model = roiRaw.value_model;
    if (!roiRaw.win_model && roiRaw.win_value_model) roiRaw.win_model = roiRaw.win_value_model;
    if (!roiRaw.aura_model && roiRaw.regression_model) roiRaw.aura_model = roiRaw.regression_model;
    roiNormalized = roiRaw;
  } else {
    const makeRoi = (m: { top1_win_roi?: number; top1_place_roi?: number; top1_bets?: number }): RoiAnalysis => ({
      top1_win: { total_bet: (m.top1_bets ?? 0) * 100, total_return: Math.round((m.top1_win_roi ?? 0) * (m.top1_bets ?? 0)), roi: m.top1_win_roi ?? 0, bet_count: m.top1_bets ?? 0 },
      top1_place: { total_bet: (m.top1_bets ?? 0) * 100, total_return: Math.round((m.top1_place_roi ?? 0) * (m.top1_bets ?? 0)), roi: m.top1_place_roi ?? 0, bet_count: m.top1_bets ?? 0 },
      by_threshold: [],
    });
    roiNormalized = {
      place_model: makeRoi(roiRaw?.value ?? roiRaw?.place ?? {}),
      win_model: roiRaw?.win_value || roiRaw?.win ? makeRoi(roiRaw.win_value ?? roiRaw.win) : undefined,
      aura_model: roiRaw?.regression || roiRaw?.aura ? makeRoi(roiRaw.regression ?? roiRaw.aura) : undefined,
      // Keep legacy keys for backward compat
      accuracy_model: makeRoi(roiRaw?.accuracy ?? {}),
      value_model: makeRoi(roiRaw?.value ?? {}),
      ...(roiRaw?.win_accuracy ? { win_accuracy_model: makeRoi(roiRaw.win_accuracy) } : {}),
      ...(roiRaw?.win_value ? { win_value_model: makeRoi(roiRaw.win_value) } : {}),
      ...(roiRaw?.regression ? { regression_model: makeRoi(roiRaw.regression) } : {}),
      value_bets: d.value_bets ?? { by_rank_gap: [] },
    };
  }

  return {
    version: d.version ?? '3.0',
    model: d.model ?? 'LightGBM',
    experiment: d.experiment ?? '',
    created_at: d.created_at ?? '',
    description: d.description ?? `v${d.version} デュアルモデル（JRA-VAN特徴量ベース）`,
    split: d.split ?? { train: '', test: '' },
    models: d.models,
    hit_analysis: hitAnalysis,
    roi_analysis: roiNormalized,
    race_predictions: d.race_predictions ?? [],
    value_bet_picks: d.value_bet_picks,
    gap_margin_grid: d.gap_margin_grid,
    gap_ard_grid: d.gap_ard_grid,
    bet_engine_presets: d.bet_engine_presets,
    obstacle_model: d.obstacle_model,
  } as MlExperimentResultV2;
}

export const V2_FEATURES = new Set([
  'avg_finish_last3', 'best_finish_last5', 'last3f_avg_last3',
  'days_since_last_race', 'win_rate_all', 'top3_rate_all',
  'total_career_races', 'recent_form_trend',
  'venue_top3_rate', 'track_type_top3_rate', 'distance_fitness',
  'prev_race_entry_count', 'entry_count_change', 'rating_trend_last3',
  'trainer_top3_rate',
]);

/** 特徴量の日本語ラベルマップ */
export const FEATURE_LABELS: Record<string, string> = {
  // 基本
  age: '馬齢', sex: '性別', futan: '斤量', horse_weight: '馬体重',
  horse_weight_diff: '馬体重増減', wakuban: '枠番', distance: '距離',
  track_type: '馬場種別', track_condition: '馬場状態', entry_count: '出走頭数',
  month: '月', nichi: '開催日',
  // オッズ・人気
  odds: 'オッズ', popularity: '人気', odds_rank: 'オッズ順位',
  // 過去走成績
  avg_finish_last3: '直近3走平均着順', best_finish_last5: '直近5走最高着順',
  last3f_avg_last3: '直近3走上がり3F平均', days_since_last_race: '前走間隔(日)',
  win_rate_all: '通算勝率', top3_rate_all: '通算複勝率',
  total_career_races: '通算出走数', recent_form_trend: '近走成績トレンド',
  venue_top3_rate: '会場別複勝率', track_type_top3_rate: '馬場別複勝率',
  distance_fitness: '距離適性', prev_race_entry_count: '前走出走頭数',
  entry_count_change: '出走頭数増減', best_l3f_last5: '直近5走最速上がり3F',
  finish_std_last5: '着順標準偏差(5走)', comeback_strength_last5: '盛り返し強度(5走)',
  // 調教師・騎手
  trainer_win_rate: '調教師勝率', trainer_top3_rate: '調教師複勝率',
  trainer_venue_top3_rate: '調教師会場複勝率',
  jockey_win_rate: '騎手勝率', jockey_top3_rate: '騎手複勝率',
  jockey_venue_top3_rate: '騎手会場複勝率',
  // 脚質
  avg_first_corner_ratio: '平均1角位置', avg_last_corner_ratio: '平均最終角位置',
  position_gain_last5: 'ポジション変動(5走)', front_runner_rate: '逃げ率',
  pace_sensitivity: 'ペース感度', closing_strength: '末脚力',
  running_style_consistency: '脚質一貫性', last_race_corner1_ratio: '前走1角位置',
  // ローテーション
  futan_diff: '斤量差', futan_diff_ratio: '斤量差率', weight_change_ratio: '体重変化率',
  prev_race_popularity: '前走人気', jockey_change: '騎手乗替',
  popularity_trend: '人気トレンド',
  // 降格ローテ
  prev_grade_level: '前走グレード', grade_level_diff: 'グレード差',
  venue_rank_diff: '会場ランク差',
  is_koukaku_venue: '降格:会場', is_koukaku_female: '降格:牝馬限定',
  is_koukaku_season: '降格:季節', is_koukaku_age: '降格:馬齢',
  is_koukaku_distance: '降格:距離', is_koukaku_turf_to_dirt: '降格:芝→ダ',
  is_koukaku_handicap: '降格:ハンデ', koukaku_rote_count: '降格パターン数',
  // ペース・ラップ
  avg_race_rpci_last3: '直近3走RPCI平均', prev_race_rpci: '前走RPCI',
  consumption_flag: '消耗フラグ', last3f_vs_race_l3_last3: '相対末脚(3走)',
  steep_course_experience: '坂コース経験', steep_course_top3_rate: '坂コース複勝率',
  l3_unrewarded_rate_last5: '末脚空振り率(5走)',
  avg_lap33_last3: '直近3走33ラップ平均', prev_race_lap33: '前走33ラップ',
  best_trend_top3_rate: '得意傾向複勝率', worst_trend_top3_rate: '苦手傾向複勝率',
  trend_versatility: '傾向適応力',
  // 調教
  training_arrow_value: '調教矢印', oikiri_5f: '追切5F', oikiri_3f: '追切3F',
  oikiri_1f: '追切1F', oikiri_intensity_code: '脚色コード',
  oikiri_has_awase: '併せ馬', training_session_count: '調教本数',
  rest_weeks: '休養週数', oikiri_is_slope: '坂路調教',
  // KB・CK
  kb_rating: 'KBレーティング', kb_mark_point: 'KB印ポイント',
  kb_aggregate_mark_point: 'KB総合印', speed_idx_latest: 'スピード指数(最新)',
  speed_idx_best5: 'スピード指数(5走Best)', speed_idx_avg3: 'スピード指数(3走平均)',
  speed_idx_trend: 'スピード指数トレンド', speed_idx_std: 'スピード指数分散',
  ck_laprank_score: 'CK lapRankスコア', ck_laprank_class: 'CK lapRankクラス',
  ck_laprank_accel: 'CK 加速度', ck_time_rank: 'CKタイムランク',
  ck_final_laprank_score: 'CK最終lapRank', ck_final_time4f: 'CK最終4Fタイム',
  ck_final_lap1: 'CK最終ラスト1F',
  // NLPコメント (v5.3)
  comment_stable_condition: '厩舎コメント状態', comment_stable_confidence: '厩舎コメント確信度',
  comment_stable_mark: '厩舎コメント印', comment_stable_excuse_flag: '厩舎言い訳フラグ',
  comment_interview_condition: '取材コメント状態', comment_interview_excuse_score: '取材言い訳スコア',
  comment_memo_condition: 'メモ状態', comment_memo_trouble_score: 'メモ問題スコア',
  comment_has_stable: '厩舎コメント有無', comment_has_interview: '取材コメント有無',
  // v5.4: ベイズ平滑化
  win_rate_smoothed: '勝率(平滑化)', top3_rate_smoothed: '複勝率(平滑化)',
  venue_top3_rate_smoothed: '会場複勝率(平滑化)', track_type_top3_rate_smoothed: '馬場複勝率(平滑化)',
  distance_fitness_smoothed: '距離適性(平滑化)', career_stage: 'キャリア段階',
  // v5.6: 前走レースレベル・騎手接戦勝率
  prev_race_level_vs_class: '前走Lvvsクラス', avg_race_level_last3: '直近3走Lv平均',
  prev_race_level_rank: '前走Lv順位', jockey_close_win_rate: '騎手接戦勝率',
  // 血統 (v5.10): 集計統計量
  sire_top3_rate: '父産駒複勝率', bms_top3_rate: '母父産駒複勝率', dam_top3_rate: '母産駒複勝率',
  sire_fresh_advantage: '父:休み明け優位', sire_tight_penalty: '父:詰め使い耐性',
  bms_fresh_advantage: '母父:休み明け優位', bms_tight_penalty: '母父:詰め使い耐性',
  dam_fresh_advantage: '母:休み明け優位', dam_tight_penalty: '母:詰め使い耐性',
  sire_sprint_top3_rate: '父:瞬発複勝率', sire_sustained_top3_rate: '父:持続複勝率',
  sire_finish_type_pref: '父:瞬発vs持続', bms_sprint_top3_rate: '母父:瞬発複勝率',
  bms_sustained_top3_rate: '母父:持続複勝率', bms_finish_type_pref: '母父:瞬発vs持続',
  dam_sprint_top3_rate: '母:瞬発複勝率', dam_sustained_top3_rate: '母:持続複勝率',
  dam_finish_type_pref: '母:瞬発vs持続',
  sire_maturity_index: '父:成長曲線', bms_maturity_index: '母父:成長曲線',
  dam_maturity_index: '母:成長曲線',
};

/** 特徴量カテゴリ分類 */
export const FEATURE_CATEGORIES: Record<string, { label: string; color: string }> = {
  MARKET: { label: 'MARKET', color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  ROTATION: { label: 'ROTATION', color: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' },
  PACE: { label: 'PACE', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
  TRAINING: { label: 'TRAINING', color: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400' },
  CK: { label: 'CK', color: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400' },
  PEDIGREE: { label: 'PEDIGREE', color: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400' },
};

const MARKET_FEATURES = new Set([
  'odds', 'odds_rank', 'popularity', 'popularity_trend',
  'ck_laprank_score', 'ck_final_laprank_score', 'kb_mark_point',
  'ck_laprank_accel', 'ck_final_time4f', 'prev_grade_level',
  'ck_laprank_class', 'grade_level_diff', 'kb_aggregate_mark_point',
  'venue_rank_diff', 'ck_final_lap1', 'ck_time_rank',
  'comment_stable_mark',
  'win_rate_smoothed', 'top3_rate_smoothed',
  'venue_top3_rate_smoothed', 'track_type_top3_rate_smoothed',
  'distance_fitness_smoothed',
]);
const ROTATION_FEATURES = new Set([
  'futan_diff', 'futan_diff_ratio', 'weight_change_ratio',
  'prev_race_popularity', 'jockey_change', 'popularity_trend',
  'prev_grade_level', 'grade_level_diff', 'venue_rank_diff',
  'is_koukaku_venue', 'is_koukaku_female', 'is_koukaku_season',
  'is_koukaku_age', 'is_koukaku_distance', 'is_koukaku_turf_to_dirt',
  'is_koukaku_handicap', 'koukaku_rote_count',
]);
const PACE_FEATURES = new Set([
  'avg_race_rpci_last3', 'prev_race_rpci', 'consumption_flag',
  'last3f_vs_race_l3_last3', 'steep_course_experience', 'steep_course_top3_rate',
  'l3_unrewarded_rate_last5', 'avg_lap33_last3', 'prev_race_lap33',
  'best_trend_top3_rate', 'worst_trend_top3_rate', 'trend_versatility',
]);
const TRAINING_FEATURES = new Set([
  'training_arrow_value', 'oikiri_5f', 'oikiri_3f', 'oikiri_1f',
  'oikiri_intensity_code', 'oikiri_has_awase', 'training_session_count',
  'rest_weeks', 'oikiri_is_slope', 'kb_rating', 'kb_mark_point', 'kb_aggregate_mark_point',
]);
const CK_FEATURES = new Set([
  'ck_laprank_score', 'ck_laprank_class', 'ck_laprank_accel', 'ck_time_rank',
  'ck_final_laprank_score', 'ck_final_time4f', 'ck_final_lap1',
]);
const PEDIGREE_FEATURES_SET = new Set([
  'sire_top3_rate', 'bms_top3_rate', 'dam_top3_rate',
  'sire_fresh_advantage', 'sire_tight_penalty',
  'bms_fresh_advantage', 'bms_tight_penalty',
  'dam_fresh_advantage', 'dam_tight_penalty',
  'sire_sprint_top3_rate', 'sire_sustained_top3_rate', 'sire_finish_type_pref',
  'bms_sprint_top3_rate', 'bms_sustained_top3_rate', 'bms_finish_type_pref',
  'dam_sprint_top3_rate', 'dam_sustained_top3_rate', 'dam_finish_type_pref',
  'sire_maturity_index', 'bms_maturity_index', 'dam_maturity_index',
]);

export function getFeatureCategory(feature: string): string | null {
  if (MARKET_FEATURES.has(feature)) return 'MARKET';
  if (CK_FEATURES.has(feature)) return 'CK';
  if (PEDIGREE_FEATURES_SET.has(feature)) return 'PEDIGREE';
  if (ROTATION_FEATURES.has(feature)) return 'ROTATION';
  if (PACE_FEATURES.has(feature)) return 'PACE';
  if (TRAINING_FEATURES.has(feature)) return 'TRAINING';
  return null;
}
