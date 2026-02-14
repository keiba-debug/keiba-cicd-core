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
  pred_proba_accuracy: number;
  pred_proba_value: number;
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
  pred_proba_accuracy: number;
  pred_proba_value: number;
  actual_position: number;
  is_top3: number;
}

export interface MlExperimentResultV2 {
  version: string;
  model?: string;
  experiment: string;
  created_at: string;
  description?: string;
  split: { train: string; test: string };
  models: {
    accuracy: MlModelResult;
    value: MlModelResult;
  };
  hit_analysis: HitAnalysisEntry[] | { accuracy: HitAnalysisEntry[]; value: HitAnalysisEntry[] };
  roi_analysis: {
    accuracy_model: RoiAnalysis;
    value_model: RoiAnalysis;
    value_bets: { by_rank_gap: ValueBetGapEntry[] };
  };
  race_predictions: RacePredictionV2[];
  value_bet_picks?: ValueBetPick[];
}
