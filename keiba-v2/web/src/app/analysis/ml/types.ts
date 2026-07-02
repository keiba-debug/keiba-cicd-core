export interface MlMetrics {
  accuracy: number;
  auc: number;
  precision?: number;
  recall?: number;
  f1?: number;
  log_loss: number;
  best_iteration: number;
  train_size: number;
  test_size: number;
  brier_score?: number;
  ece?: number;
  auc_val?: number;
  val_size?: number;
}

export interface FeatureImportanceEntry {
  feature: string;
  label?: string;
  importance: number;
}

export interface HitAnalysisEntry {
  top_n: number;
  hit_rate: number;
  hits: number;
  total: number;
}

export interface Top3DistributionEntry {
  count: number;   // 0, 1, 2, 3
  races: number;
  pct: number;
}

export interface HitAnalysisV2 {
  top1_win_rate: number;
  top1_place_rate: number;
  top1_total: number;
  top1_wins: number;
  top1_places: number;
  top3_distribution: Top3DistributionEntry[];
  legacy: HitAnalysisEntry[];
}

export interface ArdThresholdEntry {
  threshold: number;
  total: number;
  wins: number;
  win_rate: number;
  places: number;
  place_rate: number;
}

export interface RoiBetSummary {
  total_bet: number;
  total_return: number;
  roi: number;
  bet_count: number;
  hit_rate?: number;
}

export interface ThresholdEntry {
  threshold: number;
  bet_count: number;
  win_hits: number;
  win_roi: number;
  place_hits: number;
  place_roi: number;
  place_hit_rate: number;
}

export interface RoiAnalysis {
  top1_win: RoiBetSummary;
  top1_place: RoiBetSummary;
  by_threshold: ThresholdEntry[];
}

export interface MlModelResult {
  features: string[];
  metrics: MlMetrics;
  feature_importance: FeatureImportanceEntry[];
  target?: string;
  feature_count?: number;
}

export interface ValueBetGapEntry {
  min_gap: number;
  bet_count: number;
  win_hits?: number;
  win_roi?: number;
  place_hits?: number;
  place_roi: number;
  place_hit_rate: number;
}

export interface HorsePredictionV2 {
  horse_number: number;
  horse_name: string;
  pred_proba_p: number;
  pred_proba_value?: number;   // legacy alias for pred_proba_p
  pred_top3: number;
  actual_position: number;
  actual_top3: number;
  odds_rank: number | null;
  odds: number | null;
  value_rank: number;
}

export interface RacePredictionV2 {
  race_id: string;
  date: string;
  venue: string;
  grade: string;
  entry_count: number;
  horses: HorsePredictionV2[];
}

export interface ValueBetPick {
  race_id: string;
  date: string;
  venue: string;
  grade: string;
  horse_number: number;
  horse_name: string;
  value_rank: number;
  odds_rank: number;
  gap: number;
  odds: number | null;
  pred_proba_p: number;
  pred_proba_value?: number;   // legacy alias for pred_proba_p
  predicted_margin?: number | null;
  win_ev?: number | null;
  actual_position: number;
  is_top3: number;
}

export interface GapMarginGridEntry {
  min_gap: number;
  max_margin: number | null;  // null = margin制限なし
  count: number;
  win_hits: number;
  win_roi: number;
  place_hits: number;
  place_roi: number;
}

export interface GapArdGridEntry {
  min_gap: number;
  min_ard: number | null;  // null = ARd制限なし
  count: number;
  win_hits: number;
  win_roi: number;
  place_hits: number;
  place_roi: number;
}

export interface BetEnginePresetResult {
  params: Record<string, number>;
  total_bet: number;
  total_return: number;
  total_roi: number;
  win_bet: number;
  win_return: number;
  win_roi: number;
  win_hits: number;
  place_bet: number;
  place_return: number;
  place_roi: number;
  place_hits: number;
  num_bets: number;
  bootstrap_ci_low?: number;
  bootstrap_ci_high?: number;
  bootstrap_std?: number;
}

export interface RegressionMetrics {
  mae: number;
  correlation: number;
  best_iteration: number;
}

export interface RegressionModelResult {
  target: string;
  features: string[];
  feature_count: number;
  metrics: RegressionMetrics;
  feature_importance: FeatureImportanceEntry[];
}

export interface IntersectionGridArm {
  count: number;
  wins: number;
  win_rate: number;
  win_roi: number;
  avg_odds: number;
  pnl: number;
}

export interface IntersectionGridEntry {
  min_gap: number;
  min_ev: number;
  max_margin: number;
  A_gap_margin: IntersectionGridArm;
  B_ev_margin: IntersectionGridArm;
  C_intersection: IntersectionGridArm;
}

export interface MlExperimentResultV2 {
  version: string;
  version_alias?: string;
  model?: string;
  experiment: string;
  created_at: string;
  description?: string;
  split: { train: string; val?: string; test: string };
  models: {
    place: MlModelResult;
    win?: MlModelResult;
    aura?: RegressionModelResult;
    // Legacy keys (pre-v5.45 JSON compatibility)
    accuracy?: MlModelResult;
    value?: MlModelResult;
    win_accuracy?: MlModelResult;
    win_value?: MlModelResult;
    regression_value?: RegressionModelResult;
  };
  hit_analysis: HitAnalysisEntry[] | {
    place: HitAnalysisEntry[];
    place_v2?: HitAnalysisV2;
    win_v2?: HitAnalysisV2;
    aura_v2?: HitAnalysisV2;
    ard_analysis?: ArdThresholdEntry[];
    // Legacy keys
    accuracy?: HitAnalysisEntry[];
    value?: HitAnalysisEntry[];
    accuracy_v2?: HitAnalysisV2;
    value_v2?: HitAnalysisV2;
    regression_v2?: HitAnalysisV2;
  };
  roi_analysis: {
    place_model: RoiAnalysis;
    win_model?: RoiAnalysis;
    aura_model?: RoiAnalysis;
    value_bets: {
      by_rank_gap: ValueBetGapEntry[];
      win_by_rank_gap?: ValueBetGapEntry[];
    };
    // Legacy keys
    accuracy_model?: RoiAnalysis;
    value_model?: RoiAnalysis;
    win_accuracy_model?: RoiAnalysis;
    win_value_model?: RoiAnalysis;
    regression_model?: RoiAnalysis;
  };
  race_predictions: RacePredictionV2[];
  value_bet_picks?: ValueBetPick[];
  gap_margin_grid?: GapMarginGridEntry[];
  gap_ard_grid?: GapArdGridEntry[];
  bet_engine_presets?: Record<string, BetEnginePresetResult>;
  intersection_grid?: IntersectionGridEntry[];
  obstacle_model?: ObstacleModelMeta;
}

export interface ObstacleModelMetrics {
  auc: number;
  accuracy: number;
  log_loss: number;
  brier_score: number;
  ece: number;
  ece_calibrated: number;
  brier_calibrated: number;
  log_loss_calibrated: number;
  auc_val: number;
  best_iteration: number;
  train_size: number;
  val_size: number;
  test_size: number;
}

/** Regulus (3歳上 芝OP+ 専用) の top1 単勝 ROI サマリ */
export interface RegulusRoiSummary {
  n: number;
  hits: number;
  hit_rate: number;
  place_hits: number;
  place_rate: number;
  cost: number;
  payout: number;
  pnl: number;
  roi: number;
  mean_hit_odds: number;
}

/** Regulus 券種/ゲート別バリューベット分析 (最適化で meta に追記される任意フィールド) */
export interface RegulusValueRow {
  label: string;         // 例 "gap>=3", "EV>=1.1", "G1/G2"
  n: number;
  win_hits?: number;
  win_roi?: number;
  win_rate?: number;
  place_hits?: number;
  place_roi?: number;
  place_rate?: number;
  mean_odds?: number;
  note?: string;
}

/** Regulus 条件別(グレード帯/月)成績分析 (任意フィールド) */
export interface RegulusSegmentRow {
  segment: string;
  n: number;
  auc?: number;
  top1_win_rate?: number;
  top1_place_rate?: number;
  top1_win_roi?: number;
}

export interface RegulusModelMeta {
  model_type: string;
  version: string;
  description?: string;
  has_win_model: boolean;
  created_at: string;
  train_period: string;
  val_period: string;
  test_period: string;
  sire_cutoff?: string;
  min_age?: number;
  eligibility?: { track_type: string; grade_in: string[]; min_age: number };
  feature_groups?: string[];
  train_races: number;
  train_entries: number;
  val_races: number;
  val_entries: number;
  test_races: number;
  test_entries: number;
  features_p?: string[];
  features_w?: string[];
  feature_count_p?: number;
  feature_count_w?: number;
  metrics_p: ObstacleModelMetrics;
  metrics_w?: ObstacleModelMetrics;
  feature_importance_p: FeatureImportanceEntry[];
  feature_importance_w?: FeatureImportanceEntry[];
  roi_analysis_p: RegulusRoiSummary;
  roi_analysis_w?: RegulusRoiSummary;
  // 最適化フェーズで追記される任意の分析フィールド
  value_analysis_p?: RegulusValueRow[];
  value_analysis_w?: RegulusValueRow[];
  segment_analysis_p?: RegulusSegmentRow[];
  segment_analysis_w?: RegulusSegmentRow[];
  optimization_note?: string;
}

/** Eclipse (差し追込レース = レース単位) 閾値別 precision/recall */
export interface EclipseThresholdEntry {
  threshold: number;
  precision: number;
  recall: number;
  f1: number;
  n_predicted: number;
  n_correct: number;
}

export interface EclipseModelMeta {
  version: string;
  model_type: string;
  description?: string;
  created_at: string;
  train_period: string;
  val_period: string;
  test_period: string;
  features: string[];
  feature_count: number;
  params?: Record<string, number | string>;
  metrics: ObstacleModelMetrics;
  pr_auc?: number;
  threshold_analysis?: EclipseThresholdEntry[];
  train_races: number;
  train_positive_rate?: number;
  val_races: number;
  test_races: number;
  test_positive_rate?: number;
  feature_importance: FeatureImportanceEntry[];
}

export interface ObstacleModelMeta {
  version: string;
  model_type: string;
  has_win_model: boolean;
  created_at: string;
  train_period: string;
  val_period: string;
  test_period: string;
  features: string[];
  feature_count: number;
  metrics_p: ObstacleModelMetrics;
  metrics_w: ObstacleModelMetrics;
  train_races: number;
  train_entries: number;
  val_races: number;
  val_entries: number;
  test_races: number;
  test_entries: number;
  feature_importance_p: FeatureImportanceEntry[];
  feature_importance_w: FeatureImportanceEntry[];
  hit_analysis_p: HitAnalysisV2;
  hit_analysis_w: HitAnalysisV2;
  roi_analysis_p: {
    top1_win_roi: number;
    top1_place_roi: number;
    top1_bets: number;
    place_odds_db_count: number;
  };
  roi_analysis_w: {
    top1_win_roi: number;
    top1_place_roi: number;
    top1_bets: number;
    place_odds_db_count: number;
  };
}
