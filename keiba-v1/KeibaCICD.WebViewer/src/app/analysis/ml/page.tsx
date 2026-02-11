'use client';

import { useState, useEffect, useMemo } from 'react';
import { cn } from '@/lib/utils';

// ── 型定義 ──

interface MlMetrics {
  accuracy: number;
  auc: number;
  precision: number;
  recall: number;
  f1: number;
  log_loss: number;
  best_iteration: number;
  train_size: number;
  test_size: number;
}

interface FeatureImportanceEntry {
  feature: string;
  label: string;
  importance: number;
}

interface HitAnalysisEntry {
  top_n: number;
  hit_rate: number;
  hits: number;
  total: number;
}

interface RoiBetSummary {
  total_bet: number;
  total_return: number;
  roi: number;
  bet_count: number;
  hit_rate?: number;
}

interface ThresholdEntry {
  threshold: number;
  bet_count: number;
  win_hits: number;
  win_roi: number;
  place_hits: number;
  place_roi: number;
  place_hit_rate: number;
}

interface RoiAnalysis {
  top1_win: RoiBetSummary;
  top1_place: RoiBetSummary;
  by_threshold: ThresholdEntry[];
}

interface MlModelResult {
  features: string[];
  metrics: MlMetrics;
  feature_importance: FeatureImportanceEntry[];
}

interface ValueBetGapEntry {
  min_gap: number;
  bet_count: number;
  win_hits: number;
  win_roi: number;
  place_hits: number;
  place_roi: number;
  place_hit_rate: number;
}

interface HorsePredictionV2 {
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

interface RacePredictionV2 {
  race_id: string;
  date: string;
  venue: string;
  grade: string;
  entry_count: number;
  horses: HorsePredictionV2[];
}

interface ValueBetPick {
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

interface MlExperimentResultV2 {
  version: '2.0';
  model: string;
  experiment: string;
  created_at: string;
  description: string;
  split: { train: string; test: string };
  models: {
    accuracy: MlModelResult;
    value: MlModelResult;
  };
  hit_analysis: HitAnalysisEntry[];
  roi_analysis: {
    accuracy_model: RoiAnalysis;
    value_model: RoiAnalysis;
    value_bets: { by_rank_gap: ValueBetGapEntry[] };
  };
  race_predictions: RacePredictionV2[];
  value_bet_picks?: ValueBetPick[];
}

// ── 定数 ──

const TABS = [
  { key: 'overview', label: '概要' },
  { key: 'value', label: 'Value分析' },
  { key: 'picks', label: 'VB一覧' },
  { key: 'roi', label: '回収率' },
  { key: 'importance', label: '特徴量重要度' },
  { key: 'predictions', label: 'レース予測' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

// ── メトリクスカード ──

function MetricCard({
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

// ── 概要タブ ──

function OverviewTab({ data }: { data: MlExperimentResultV2 }) {
  const ma = data.models.accuracy.metrics;
  const mv = data.models.value.metrics;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-blue-200 p-4 dark:border-blue-800">
          <h3 className="mb-3 text-sm font-semibold text-blue-700 dark:text-blue-400">
            Model A（精度モデル）
          </h3>
          <div className="grid grid-cols-3 gap-2">
            <MetricCard label="AUC" value={ma.auc.toFixed(4)} highlight color="blue" />
            <MetricCard label="Accuracy" value={(ma.accuracy * 100).toFixed(1) + '%'} />
            <MetricCard label="Precision" value={(ma.precision * 100).toFixed(1) + '%'} />
          </div>
          <div className="mt-2 text-xs text-gray-500">
            特徴量 {data.models.accuracy.features.length}個（市場情報含む）
          </div>
        </div>

        <div className="rounded-lg border border-emerald-200 p-4 dark:border-emerald-800">
          <h3 className="mb-3 text-sm font-semibold text-emerald-700 dark:text-emerald-400">
            Model B（Valueモデル）
          </h3>
          <div className="grid grid-cols-3 gap-2">
            <MetricCard label="AUC" value={mv.auc.toFixed(4)} highlight color="green" />
            <MetricCard label="Accuracy" value={(mv.accuracy * 100).toFixed(1) + '%'} />
            <MetricCard label="Precision" value={(mv.precision * 100).toFixed(1) + '%'} />
          </div>
          <div className="mt-2 text-xs text-gray-500">
            特徴量 {data.models.value.features.length}個（人気/印/AI除外）
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">モデル情報</h3>
        <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <div><span className="text-gray-500">学習: </span><span className="font-medium">{data.split.train}</span></div>
          <div><span className="text-gray-500">テスト: </span><span className="font-medium">{data.split.test}</span></div>
          <div><span className="text-gray-500">学習件数: </span><span className="font-medium">{ma.train_size.toLocaleString()}</span></div>
          <div><span className="text-gray-500">テスト件数: </span><span className="font-medium">{ma.test_size.toLocaleString()}</span></div>
        </div>
      </div>

      {data.hit_analysis.length > 0 && (
        <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
            Top-N予測の的中率（Model A）
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {data.hit_analysis.map((h) => (
              <div key={h.top_n} className="rounded-lg bg-gray-50 p-3 text-center dark:bg-gray-800/50">
                <div className="text-xs text-gray-500">Top {h.top_n}</div>
                <div className="mt-1 text-xl font-bold text-blue-600 dark:text-blue-400">
                  {(h.hit_rate * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-gray-400">{h.hits}/{h.total}R</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Value分析タブ ──

function ValueTab({ data }: { data: MlExperimentResultV2 }) {
  const vb = data.roi_analysis.value_bets.by_rank_gap;
  const maxRoi = Math.max(...vb.map((v) => v.place_roi), 100);

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4 dark:border-emerald-800 dark:bg-emerald-950/20">
        <h3 className="mb-2 text-sm font-semibold text-emerald-800 dark:text-emerald-300">Value Bet戦略</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Model B（市場情報なし）がレース内上位3位に予測 × 実際の人気が低い馬を購入。
          モデルと市場の「乖離」が大きいほど、市場が見落としている可能性。
        </p>
      </div>

      <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">ランクギャップ別の回収率</h3>
        <p className="mb-3 text-xs text-gray-500">gap = 人気順 - Model Bランク。gapが大きい = 市場より高い評価</p>

        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-gray-500 dark:border-gray-700">
              <th className="py-2 text-left">条件</th>
              <th className="py-2 text-right">購入数</th>
              <th className="py-2 text-right">単勝的中</th>
              <th className="py-2 text-right">単勝ROI</th>
              <th className="py-2 text-right">複勝的中率</th>
              <th className="py-2 text-right">複勝ROI</th>
            </tr>
          </thead>
          <tbody>
            {vb.map((v) => (
              <tr key={v.min_gap} className="border-b border-gray-50 dark:border-gray-800">
                <td className="py-2 font-medium">gap {'≥'} {v.min_gap}</td>
                <td className="py-2 text-right tabular-nums">{v.bet_count.toLocaleString()}</td>
                <td className="py-2 text-right tabular-nums">{v.win_hits}</td>
                <td className="py-2 text-right tabular-nums">
                  <span className={cn('font-medium', v.win_roi >= 100 ? 'text-green-600 dark:text-green-400' : '')}>
                    {v.win_roi.toFixed(1)}%
                  </span>
                </td>
                <td className="py-2 text-right tabular-nums">{(v.place_hit_rate * 100).toFixed(1)}%</td>
                <td className="py-2 text-right tabular-nums">
                  <span className={cn('font-bold', v.place_roi >= 100 ? 'text-green-600 dark:text-green-400' : 'text-red-500')}>
                    {v.place_roi.toFixed(1)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-4">
          <h4 className="mb-2 text-xs font-medium text-gray-500">複勝回収率（赤線: 損益分岐100%）</h4>
          <div className="space-y-1">
            {vb.map((v) => {
              const pct = (v.place_roi / maxRoi) * 100;
              const breakeven = (100 / maxRoi) * 100;
              return (
                <div key={v.min_gap} className="flex items-center gap-2">
                  <span className="w-16 text-right text-xs tabular-nums text-gray-500">gap{'≥'}{v.min_gap}</span>
                  <div className="relative flex-1 h-6 rounded bg-gray-100 dark:bg-gray-700/50">
                    <div
                      className={cn('absolute inset-y-0 left-0 rounded',
                        v.place_roi >= 100 ? 'bg-emerald-400 dark:bg-emerald-600' : 'bg-amber-300 dark:bg-amber-600'
                      )}
                      style={{ width: `${Math.max(pct, 1)}%` }}
                    />
                    <div className="absolute inset-y-0 w-0.5 bg-red-500" style={{ left: `${breakeven}%` }} />
                    <span className="absolute inset-y-0 right-2 flex items-center text-xs tabular-nums font-medium text-gray-700 dark:text-gray-200">
                      {v.place_roi.toFixed(1)}%
                    </span>
                  </div>
                  <span className="w-14 text-right text-xs tabular-nums text-gray-400">{v.bet_count}件</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <h3 className="mb-2 text-sm font-semibold">Model A Top1 単勝ROI</h3>
          <div className="text-3xl font-bold tabular-nums">
            <span className={data.roi_analysis.accuracy_model.top1_win.roi >= 100 ? 'text-green-600' : 'text-red-500'}>
              {data.roi_analysis.accuracy_model.top1_win.roi.toFixed(1)}%
            </span>
          </div>
          <div className="text-xs text-gray-500">{data.roi_analysis.accuracy_model.top1_win.bet_count}R</div>
        </div>
        <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <h3 className="mb-2 text-sm font-semibold">Model B Top1 単勝ROI</h3>
          <div className="text-3xl font-bold tabular-nums">
            <span className={data.roi_analysis.value_model.top1_win.roi >= 100 ? 'text-green-600' : 'text-red-500'}>
              {data.roi_analysis.value_model.top1_win.roi.toFixed(1)}%
            </span>
          </div>
          <div className="text-xs text-gray-500">{data.roi_analysis.value_model.top1_win.bet_count}R</div>
        </div>
      </div>
    </div>
  );
}

// ── Value Bet一覧タブ ──

function ValuePicksTab({ picks }: { picks: ValueBetPick[] }) {
  const [minGap, setMinGap] = useState(3);
  const [sortKey, setSortKey] = useState<'gap' | 'date' | 'odds'>('gap');
  const [showHitsOnly, setShowHitsOnly] = useState(false);

  const filtered = useMemo(() => {
    let list = picks.filter((p) => p.gap >= minGap);
    if (showHitsOnly) list = list.filter((p) => p.is_top3 === 1);
    list = [...list].sort((a, b) => {
      if (sortKey === 'gap') return b.gap - a.gap || a.date.localeCompare(b.date);
      if (sortKey === 'date') return b.date.localeCompare(a.date) || b.gap - a.gap;
      return (b.odds ?? 0) - (a.odds ?? 0);
    });
    return list;
  }, [picks, minGap, sortKey, showHitsOnly]);

  const stats = useMemo(() => {
    const total = filtered.length;
    const hits = filtered.filter((p) => p.is_top3 === 1).length;
    return { total, hits, rate: total > 0 ? (hits / total) * 100 : 0 };
  }, [filtered]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">最小Gap:</span>
          {[2, 3, 4, 5].map((g) => (
            <button key={g} onClick={() => setMinGap(g)}
              className={cn('rounded-md px-2.5 py-1 text-sm font-medium transition-colors',
                minGap === g
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                  : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
              )}>
              {'\u2265'}{g}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">並び順:</span>
          {([['gap', 'Gap大'], ['date', '日付'], ['odds', 'オッズ']] as const).map(([k, l]) => (
            <button key={k} onClick={() => setSortKey(k)}
              className={cn('rounded-md px-2.5 py-1 text-sm transition-colors',
                sortKey === k
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                  : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
              )}>
              {l}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-sm text-gray-500 cursor-pointer">
          <input type="checkbox" checked={showHitsOnly} onChange={(e) => setShowHitsOnly(e.target.checked)}
            className="rounded border-gray-300" />
          的中のみ
        </label>
      </div>

      <div className="flex items-center gap-4 rounded-lg border border-gray-200 p-3 dark:border-gray-700 text-sm">
        <div>
          <span className="text-gray-500">該当馬: </span>
          <span className="font-bold">{stats.total}頭</span>
        </div>
        <div>
          <span className="text-gray-500">3着以内: </span>
          <span className="font-bold text-green-600 dark:text-green-400">{stats.hits}頭</span>
          <span className="ml-1 text-gray-400">({stats.rate.toFixed(1)}%)</span>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="py-8 text-center text-gray-400">該当なし</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-gray-500 dark:border-gray-700">
                <th className="py-2 text-left">日付</th>
                <th className="py-2 text-left">場所</th>
                <th className="py-2 text-center">R</th>
                <th className="py-2 text-left">馬名</th>
                <th className="py-2 text-center">VR</th>
                <th className="py-2 text-center">人気</th>
                <th className="py-2 text-center">Gap</th>
                <th className="py-2 text-right">オッズ</th>
                <th className="py-2 text-center">着順</th>
                <th className="py-2 text-center">結果</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p, i) => (
                <tr key={`${p.race_id}-${p.horse_number}-${i}`}
                  className={cn('border-b border-gray-50 dark:border-gray-800',
                    p.is_top3 === 1 && 'bg-green-50/50 dark:bg-green-950/20'
                  )}>
                  <td className="py-1.5 tabular-nums text-gray-600 dark:text-gray-400">{p.date.replace(/\//g, '-')}</td>
                  <td className="py-1.5">{p.venue}</td>
                  <td className="py-1.5 text-center tabular-nums text-gray-500">{parseInt(p.race_id.slice(-2), 10)}</td>
                  <td className="py-1.5 font-medium">{p.horse_name}</td>
                  <td className="py-1.5 text-center tabular-nums text-emerald-600 dark:text-emerald-400">{p.value_rank}</td>
                  <td className="py-1.5 text-center tabular-nums text-gray-500">{p.odds_rank}</td>
                  <td className="py-1.5 text-center">
                    <span className={cn('rounded px-1.5 py-0.5 text-xs font-bold tabular-nums',
                      p.gap >= 5 ? 'bg-emerald-200 text-emerald-800 dark:bg-emerald-800 dark:text-emerald-200'
                        : p.gap >= 4 ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300'
                        : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                    )}>
                      +{p.gap}
                    </span>
                  </td>
                  <td className="py-1.5 text-right tabular-nums text-amber-600 dark:text-amber-400">
                    {p.odds != null ? p.odds.toFixed(1) : '-'}
                  </td>
                  <td className="py-1.5 text-center tabular-nums font-medium">
                    <span className={p.actual_position <= 3 ? 'text-red-600 dark:text-red-400' : ''}>
                      {p.actual_position}
                    </span>
                  </td>
                  <td className="py-1.5 text-center">
                    {p.is_top3 === 1
                      ? <span className="rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">的中</span>
                      : <span className="text-xs text-gray-400">-</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── 回収率タブ ──

function RoiTab({ roiA, roiV }: { roiA: RoiAnalysis; roiV: RoiAnalysis }) {
  return (
    <div className="space-y-6">
      {[
        { label: 'Model A（精度）', roi: roiA },
        { label: 'Model B（Value）', roi: roiV },
      ].map(({ label, roi }) => (
        <div key={label} className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">{label}</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="space-y-1 text-sm">
              <div className="font-medium">Top1 → 単勝</div>
              <div className="flex justify-between"><span className="text-gray-500">投資</span><span className="tabular-nums">¥{roi.top1_win.total_bet.toLocaleString()}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">回収</span><span className="tabular-nums">¥{roi.top1_win.total_return.toLocaleString()}</span></div>
              <div className="flex justify-between font-medium"><span>ROI</span>
                <span className={cn('tabular-nums', roi.top1_win.roi >= 100 ? 'text-green-600' : 'text-red-500')}>{roi.top1_win.roi.toFixed(1)}%</span>
              </div>
            </div>
            <div className="space-y-1 text-sm">
              <div className="font-medium">Top1 → 複勝</div>
              <div className="flex justify-between"><span className="text-gray-500">投資</span><span className="tabular-nums">¥{roi.top1_place.total_bet.toLocaleString()}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">的中率</span>
                <span className="tabular-nums">{roi.top1_place.hit_rate != null ? (roi.top1_place.hit_rate * 100).toFixed(1) + '%' : '-'}</span>
              </div>
              <div className="flex justify-between font-medium"><span>ROI</span>
                <span className={cn('tabular-nums', roi.top1_place.roi >= 100 ? 'text-green-600' : 'text-red-500')}>{roi.top1_place.roi.toFixed(1)}%</span>
              </div>
            </div>
          </div>
          {roi.by_threshold.length > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">閾値別の詳細</summary>
              <table className="mt-2 w-full text-xs">
                <thead>
                  <tr className="border-b text-gray-400">
                    <th className="py-1 text-left">閾値</th>
                    <th className="py-1 text-right">件数</th>
                    <th className="py-1 text-right">単勝ROI</th>
                    <th className="py-1 text-right">複勝ROI</th>
                  </tr>
                </thead>
                <tbody>
                  {roi.by_threshold.map((t) => (
                    <tr key={t.threshold} className="border-b border-gray-50 dark:border-gray-800">
                      <td className="py-1 tabular-nums">{(t.threshold * 100).toFixed(0)}%+</td>
                      <td className="py-1 text-right tabular-nums">{t.bet_count}</td>
                      <td className="py-1 text-right tabular-nums">
                        <span className={t.win_roi >= 100 ? 'text-green-600 font-medium' : ''}>{t.win_roi.toFixed(1)}%</span>
                      </td>
                      <td className="py-1 text-right tabular-nums">
                        <span className={t.place_roi >= 100 ? 'text-green-600 font-medium' : ''}>{t.place_roi.toFixed(1)}%</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}

// ── 特徴量重要度タブ ──

const V2_FEATURES = new Set([
  'avg_finish_last3', 'best_finish_last5', 'last3f_avg_last3',
  'days_since_last_race', 'win_rate_all', 'top3_rate_all',
  'total_career_races', 'recent_form_trend',
  'venue_top3_rate', 'track_type_top3_rate', 'distance_fitness',
  'prev_race_entry_count', 'entry_count_change', 'rating_trend_last3',
  'trainer_top3_rate',
]);

function ImportanceTab({ data }: { data: MlExperimentResultV2 }) {
  const [showModel, setShowModel] = useState<'accuracy' | 'value'>('value');
  const fi = showModel === 'accuracy'
    ? data.models.accuracy.feature_importance
    : data.models.value.feature_importance;
  const maxImportance = fi[0]?.importance ?? 1;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {(['accuracy', 'value'] as const).map((m) => (
          <button key={m} onClick={() => setShowModel(m)}
            className={cn('rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              showModel === m
                ? m === 'accuracy' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                  : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
            )}>
            {m === 'accuracy' ? 'Model A（精度）' : 'Model B（Value）'}
          </button>
        ))}
      </div>
      <p className="text-sm text-gray-500">LightGBMのgain（情報利得）ベースの特徴量重要度</p>
      <div className="space-y-2">
        {fi.map((f, i) => {
          const pct = (f.importance / maxImportance) * 100;
          return (
            <div key={f.feature} className="flex items-center gap-3">
              <div className="w-6 text-right text-xs text-gray-400">{i + 1}</div>
              <div className="w-44 text-sm font-medium truncate flex items-center gap-1">
                {f.label}
                {V2_FEATURES.has(f.feature) && (
                  <span className="rounded bg-amber-100 px-1 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">v2</span>
                )}
              </div>
              <div className="flex-1">
                <div className="relative h-6 rounded bg-gray-100 dark:bg-gray-700/50">
                  <div className={cn('absolute inset-y-0 left-0 rounded',
                    showModel === 'value'
                      ? i === 0 ? 'bg-emerald-500' : i < 3 ? 'bg-emerald-400' : 'bg-emerald-300 dark:bg-emerald-600'
                      : i === 0 ? 'bg-blue-500' : i < 3 ? 'bg-blue-400' : 'bg-blue-300 dark:bg-blue-600'
                  )} style={{ width: `${Math.max(pct, 1)}%` }} />
                  <span className="absolute inset-y-0 right-2 flex items-center text-xs tabular-nums text-gray-600 dark:text-gray-300">
                    {f.importance.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── レース予測タブ ──

function PredictionsTab({ predictions }: { predictions: RacePredictionV2[] }) {
  const [page, setPage] = useState(0);
  const [expandedRace, setExpandedRace] = useState<string | null>(null);
  const pageSize = 20;
  const paged = predictions.slice(page * pageSize, (page + 1) * pageSize);
  const totalPages = Math.ceil(predictions.length / pageSize);

  const stats = useMemo(() => {
    let totalHits = 0, totalPredicted = 0;
    for (const race of predictions) {
      for (const h of race.horses) {
        if (h.pred_top3 === 1) { totalPredicted++; if (h.actual_top3 === 1) totalHits++; }
      }
    }
    return { totalHits, totalPredicted };
  }, [predictions]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-500">
          {predictions.length}R中、予測的中: {stats.totalHits}/{stats.totalPredicted}頭
          ({stats.totalPredicted > 0 ? ((stats.totalHits / stats.totalPredicted) * 100).toFixed(1) : 0}%)
        </span>
        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
              className="rounded border px-2 py-1 text-xs disabled:opacity-30">前</button>
            <span className="text-xs text-gray-500">{page + 1}/{totalPages}</span>
            <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
              className="rounded border px-2 py-1 text-xs disabled:opacity-30">次</button>
          </div>
        )}
      </div>

      <div className="space-y-2">
        {paged.map((race) => {
          const isExpanded = expandedRace === race.race_id;
          const top1 = race.horses[0];
          const top1Hit = top1?.actual_top3 === 1;
          const valuePick = race.horses.find(
            (h) => h.value_rank <= 3 && h.odds_rank != null && h.odds_rank >= h.value_rank + 3
          );

          return (
            <div key={race.race_id} className="rounded-lg border border-gray-200 dark:border-gray-700">
              <button onClick={() => setExpandedRace(isExpanded ? null : race.race_id)}
                className="flex w-full items-center gap-3 p-3 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-800/50">
                <span className="w-20 text-gray-500">{race.date.replace(/\//g, '-')}</span>
                <span className="w-12 font-medium">{race.venue}</span>
                <span className="w-10 text-gray-400">{race.entry_count}頭</span>
                <span className="flex-1">
                  <span className="text-xs text-gray-400">Top1: </span>
                  <span className="font-medium">{top1?.horse_name ?? '-'}</span>
                  <span className="ml-1 text-xs text-gray-500">({(top1?.pred_proba_accuracy * 100).toFixed(0)}%)</span>
                  {top1?.odds != null && (
                    <span className="ml-1 text-xs text-amber-600 dark:text-amber-400">{top1.odds.toFixed(1)}倍</span>
                  )}
                </span>
                {valuePick && (
                  <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">VALUE</span>
                )}
                <span>
                  {top1Hit
                    ? <span className="rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">的中</span>
                    : <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500 dark:bg-gray-700 dark:text-gray-400">不的中</span>}
                </span>
                <span className="text-gray-400">{isExpanded ? '▲' : '▼'}</span>
              </button>

              {isExpanded && (
                <div className="border-t border-gray-100 px-3 pb-3 dark:border-gray-700">
                  <table className="mt-2 w-full text-xs">
                    <thead>
                      <tr className="text-gray-400">
                        <th className="w-8 text-right">馬番</th>
                        <th className="px-2 text-left">馬名</th>
                        <th className="w-14 text-right">精度%</th>
                        <th className="w-14 text-right">Value%</th>
                        <th className="w-8 text-center">VR</th>
                        <th className="w-10 text-center">着順</th>
                        <th className="w-10 text-center">人気</th>
                        <th className="w-12 text-right">オッズ</th>
                        <th className="w-14 text-center">判定</th>
                      </tr>
                    </thead>
                    <tbody>
                      {race.horses.map((h) => {
                        const hit = h.pred_top3 === 1 && h.actual_top3 === 1;
                        const miss = h.pred_top3 === 1 && h.actual_top3 === 0;
                        const isValue = h.value_rank <= 3 && h.odds_rank != null && h.odds_rank >= h.value_rank + 3;
                        return (
                          <tr key={h.horse_number} className={cn(
                            'border-t border-gray-50 dark:border-gray-800',
                            hit && 'bg-green-50/50 dark:bg-green-950/20',
                            miss && 'bg-red-50/30 dark:bg-red-950/10',
                            isValue && !hit && !miss && 'bg-emerald-50/30 dark:bg-emerald-950/10'
                          )}>
                            <td className="py-1 text-right tabular-nums">{h.horse_number}</td>
                            <td className="px-2 font-medium">
                              {h.horse_name}
                              {isValue && <span className="ml-1 rounded bg-emerald-100 px-1 py-0.5 text-[9px] font-bold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">V</span>}
                            </td>
                            <td className="text-right tabular-nums">{(h.pred_proba_accuracy * 100).toFixed(1)}</td>
                            <td className="text-right tabular-nums text-emerald-600 dark:text-emerald-400">{(h.pred_proba_value * 100).toFixed(1)}</td>
                            <td className="text-center tabular-nums text-gray-500">{h.value_rank}</td>
                            <td className="text-center tabular-nums font-medium">
                              <span className={h.actual_position <= 3 ? 'text-red-600 dark:text-red-400' : ''}>{h.actual_position}</span>
                            </td>
                            <td className="text-center tabular-nums text-gray-500">{h.odds_rank ?? '-'}</td>
                            <td className="text-right tabular-nums text-amber-600 dark:text-amber-400">{h.odds != null ? h.odds.toFixed(1) : '-'}</td>
                            <td className="text-center">
                              {hit && <span className="text-green-600">的中</span>}
                              {miss && <span className="text-red-400">外れ</span>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── メインページ ──

export default function MlAnalysisPage() {
  const [data, setData] = useState<MlExperimentResultV2 | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('overview');

  useEffect(() => {
    fetch('/api/ml/result')
      .then((res) => { if (!res.ok) throw new Error('ML結果が見つかりません'); return res.json(); })
      .then((d) => {
        if (d.version !== '2.0') throw new Error('v2結果が必要です。python ml/scripts/ml_experiment_v2.py を実行してください');
        setData(d as MlExperimentResultV2);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex h-64 items-center justify-center"><div className="text-gray-500">読み込み中...</div></div>;
  if (error || !data) return (
    <div className="flex h-64 flex-col items-center justify-center gap-2">
      <div className="text-red-500">{error ?? 'データがありません'}</div>
      <p className="text-sm text-gray-500">python ml/scripts/ml_experiment_v2.py を実行してください</p>
    </div>
  );

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">ML分析</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          {data.description} — {data.model} ({data.experiment})
        </p>
      </div>

      {/* 用語説明 */}
      <div className="mb-5 grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-xs text-gray-600 dark:border-gray-700 dark:bg-gray-800/50 dark:text-gray-400">
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">Model A（精度）</span> — 全32特徴量（オッズ含む）で3着内を予測。的中率重視</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">Model B（Value）</span> — 市場系5特徴量を除外した27特徴量。市場に依存しない能力評価</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">VR（Value Rank）</span> — Model Bによるレース内の順位（1=最も能力が高い）</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">Gap</span> — 人気順位 - VR。大きいほど市場が過小評価している馬</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">Value Bet</span> — VR≤3 かつ Gap≥3 の馬。モデルは上位評価だが人気薄</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">AUC</span> — モデルの判別力（0.5=ランダム、1.0=完全予測）</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">ROI</span> — 回収率。100%超えで利益が出る戦略</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">複勝ROI</span> — 3着以内的中時の払戻（オッズ÷3.5で概算）</div>
      </div>

      <div className="mb-4 flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
        {TABS.map((tab) => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={cn('flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              activeTab === tab.key
                ? 'bg-white text-gray-900 shadow dark:bg-gray-700 dark:text-gray-100'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
            )}>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && <OverviewTab data={data} />}
      {activeTab === 'value' && <ValueTab data={data} />}
      {activeTab === 'picks' && (
        data.value_bet_picks && data.value_bet_picks.length > 0
          ? <ValuePicksTab picks={data.value_bet_picks} />
          : <div className="py-8 text-center text-gray-400">value_bet_picksがありません。ml_experiment_v2.pyを再実行してください。</div>
      )}
      {activeTab === 'roi' && <RoiTab roiA={data.roi_analysis.accuracy_model} roiV={data.roi_analysis.value_model} />}
      {activeTab === 'importance' && <ImportanceTab data={data} />}
      {activeTab === 'predictions' && <PredictionsTab predictions={data.race_predictions} />}
    </div>
  );
}
