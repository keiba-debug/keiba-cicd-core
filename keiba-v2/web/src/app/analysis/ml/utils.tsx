import { cn } from '@/lib/utils';
import type { MlExperimentResultV2, RoiAnalysis } from './types';

export const TABS = [
  { key: 'overview', label: '概要' },
  { key: 'value', label: 'Value分析' },
  { key: 'picks', label: 'VB一覧' },
  { key: 'roi', label: '回収率' },
  { key: 'importance', label: '特徴量重要度' },
  { key: 'predictions', label: 'レース予測' },
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
  color?: 'blue' | 'green';
}) {
  const colors = {
    blue: 'border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-950/30',
    green: 'border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-950/30',
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

  for (const modelKey of ['accuracy', 'value'] as const) {
    const m = d.models?.[modelKey];
    if (m?.feature_importance) {
      for (const fi of m.feature_importance) {
        if (!fi.label) fi.label = fi.feature;
      }
    }
    if (m?.metrics) {
      m.metrics.precision = m.metrics.precision ?? 0;
      m.metrics.recall = m.metrics.recall ?? 0;
      m.metrics.f1 = m.metrics.f1 ?? 0;
    }
  }

  let hitAnalysis = d.hit_analysis;
  if (hitAnalysis && !Array.isArray(hitAnalysis)) {
    hitAnalysis = hitAnalysis;
  }

  const roiRaw = d.roi_analysis;
  let roiNormalized;
  if (roiRaw?.accuracy_model) {
    roiNormalized = roiRaw;
  } else {
    const makeRoi = (m: { top1_win_roi?: number; top1_place_roi?: number; top1_bets?: number }): RoiAnalysis => ({
      top1_win: { total_bet: (m.top1_bets ?? 0) * 100, total_return: Math.round((m.top1_win_roi ?? 0) * (m.top1_bets ?? 0)), roi: m.top1_win_roi ?? 0, bet_count: m.top1_bets ?? 0 },
      top1_place: { total_bet: (m.top1_bets ?? 0) * 100, total_return: Math.round((m.top1_place_roi ?? 0) * (m.top1_bets ?? 0)), roi: m.top1_place_roi ?? 0, bet_count: m.top1_bets ?? 0 },
      by_threshold: [],
    });
    roiNormalized = {
      accuracy_model: makeRoi(roiRaw?.accuracy ?? {}),
      value_model: makeRoi(roiRaw?.value ?? {}),
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
