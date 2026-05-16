'use client';

/**
 * polaris セグメント分析ダッシュボード
 *
 * data3/analysis/polaris_segments/{run_id}/segments.json を表示する。
 * Run 選択 + サマリ + 軸別アコーディオン (テーブル)。
 * Session 122 Phase 2 で追加。
 */

import { useState, useMemo } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ArrowLeft, ChevronDown, ChevronRight, TrendingUp, TrendingDown, Minus, Activity, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

// ===========================================================================
// Types
// ===========================================================================
interface RunMeta {
  run_id: string;
  generated_at?: string;
  model?: string;
  total_races?: number;
  total_entries?: number;
  split_date?: string;
}

interface SegmentStats {
  n_entries: number;
  n_races_segment: number;
  n_races_bet: number;
  top1_bets: number;
  win_roi: {
    n: number;
    cost: number;
    payout: number;
    pnl: number;
    roi: number;
    hit_rate: number;
    hits: number;
    mean_hit_odds: number;
    ci_low?: number;
    ci_high?: number;
  };
  brier: number | null;
  ece: number | null;
  marker: string;
}

interface PeriodCompareEntry {
  a: { n_bets: number; roi: number; hit_rate: number };
  b: { n_bets: number; roi: number; hit_rate: number };
  delta_roi: number;
}

interface MonthlyEntry {
  month: string;
  n_bets: number;
  roi: number;
  pnl: number;
  cum_pnl: number;
  hits: number;
}

interface SegmentsResponse {
  model: string;
  total_entries: number;
  total_races: number;
  split_date: string;
  axes: Record<string, Record<string, SegmentStats>>;
  monthly: {
    monthly: MonthlyEntry[];
    sharpe: number;
    max_dd_amount: number;
    max_dd_pct: number;
    losing_streaks: {
      max_streak: number;
      avg_streak: number;
      streak_10plus: number;
      max_streak_loss: number;
    };
  } | null;
}

interface RunDetail {
  run_id: string;
  meta: RunMeta;
  segments: SegmentsResponse;
  period_compare: Record<string, Record<string, PeriodCompareEntry>> | null;
}

// ===========================================================================
// Axis metadata (display labels)
// ===========================================================================
const AXIS_LABELS: Record<string, string> = {
  odds_band: 'オッズ帯',
  runners: '頭数帯',
  grade: 'グレード',
  track_type: '馬場 (芝/ダ)',
  distance: '距離帯',
  month: '月別',
  venue: '会場 (場コード)',
  jockey: '騎手 Top30',
  trainer: '調教師 Top30',
};

const AXIS_ORDER = [
  'odds_band', 'runners', 'grade', 'track_type', 'distance',
  'month', 'venue', 'jockey', 'trainer',
];

// ===========================================================================
// Helpers
// ===========================================================================
const fetcher = (url: string) => fetch(url).then((r) => r.json());

function roiStyle(roi: number): string {
  if (roi >= 130) return 'text-emerald-700 dark:text-emerald-400 font-bold';
  if (roi >= 110) return 'text-emerald-600 dark:text-emerald-500 font-semibold';
  if (roi >= 90) return 'text-slate-700 dark:text-slate-300';
  if (roi >= 70) return 'text-rose-500 dark:text-rose-400';
  return 'text-rose-700 dark:text-rose-300 font-semibold';
}

function deltaIcon(d: number | undefined | null) {
  if (d === undefined || d === null) return <Minus className="inline w-3 h-3 text-slate-400" />;
  if (d >= 5) return <TrendingUp className="inline w-3 h-3 text-emerald-500" />;
  if (d <= -5) return <TrendingDown className="inline w-3 h-3 text-rose-500" />;
  return <Minus className="inline w-3 h-3 text-slate-400" />;
}

// ===========================================================================
// Sub-components
// ===========================================================================
function SummaryCard({ detail }: { detail: RunDetail }) {
  const { segments } = detail;
  const monthly = segments.monthly;
  const streaks = monthly?.losing_streaks;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="w-5 h-5" />
          {detail.run_id} <span className="text-sm font-normal text-slate-500">({segments.model.toUpperCase()})</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <Stat label="対象 races" value={`${segments.total_races.toLocaleString()}`} />
          <Stat label="対象 entries" value={`${segments.total_entries.toLocaleString()}`} />
          <Stat label="期間分割" value={segments.split_date || '—'} />
          {monthly && (
            <>
              <Stat
                label="Sharpe (月次)"
                value={monthly.sharpe.toFixed(2)}
                hint={monthly.sharpe > 1.5 ? '優秀' : monthly.sharpe > 0.5 ? '健全' : '不安定'}
              />
              <Stat
                label="MaxDD"
                value={`¥${monthly.max_dd_amount.toLocaleString()}`}
                hint={`${monthly.max_dd_pct.toFixed(1)}%`}
              />
              {streaks && (
                <>
                  <Stat label="最長連敗" value={`${streaks.max_streak}連敗`} hint={`-¥${streaks.max_streak_loss.toLocaleString()}`} />
                  <Stat label="平均連敗" value={`${streaks.avg_streak}`} />
                  <Stat label="10連敗以上" value={`${streaks.streak_10plus}回`} />
                </>
              )}
            </>
          )}
        </div>
        {detail.meta?.generated_at && (
          <p className="text-xs text-slate-500 mt-3">
            生成: {detail.meta.generated_at}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="font-mono font-semibold">{value}</div>
      {hint && <div className="text-xs text-slate-400">{hint}</div>}
    </div>
  );
}

function AxisCard({
  axisKey,
  segments,
  periodCompare,
}: {
  axisKey: string;
  segments: Record<string, SegmentStats>;
  periodCompare?: Record<string, PeriodCompareEntry>;
}) {
  const [expanded, setExpanded] = useState(true);
  const labels = Object.keys(segments);

  if (labels.length === 0) {
    return null;
  }

  const totalBets = labels.reduce((s, l) => s + (segments[l].win_roi?.n || 0), 0);
  const hasPeriod = !!periodCompare && Object.keys(periodCompare).length > 0;

  return (
    <Card>
      <CardHeader
        className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 py-3"
        onClick={() => setExpanded((e) => !e)}
      >
        <CardTitle className="flex items-center justify-between text-base">
          <span className="flex items-center gap-2">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            {AXIS_LABELS[axisKey] || axisKey}
            <span className="text-xs font-normal text-slate-500">
              ({labels.length} segments / {totalBets.toLocaleString()} bets)
            </span>
          </span>
        </CardTitle>
      </CardHeader>
      {expanded && (
        <CardContent className="pt-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-xs text-slate-500">
                  <th className="text-left py-1 px-2">セグメント</th>
                  <th className="text-right py-1 px-2">races</th>
                  <th className="text-right py-1 px-2">bets</th>
                  <th className="text-right py-1 px-2">勝率</th>
                  <th className="text-right py-1 px-2">単勝ROI</th>
                  {hasPeriod && <th className="text-right py-1 px-2">ΔROI (B-A)</th>}
                  <th className="text-right py-1 px-2">P&L</th>
                  <th className="text-right py-1 px-2">Brier</th>
                  <th className="text-right py-1 px-2">ECE</th>
                  <th className="text-left py-1 px-2">警告</th>
                </tr>
              </thead>
              <tbody>
                {labels.map((label) => {
                  const s = segments[label];
                  const roi = s.win_roi;
                  const pc = periodCompare?.[label];
                  return (
                    <tr key={label} className="border-b border-slate-100 dark:border-slate-800">
                      <td className="py-1 px-2 font-mono">{label}</td>
                      <td className="text-right py-1 px-2 tabular-nums">{s.n_races_bet.toLocaleString()}</td>
                      <td className="text-right py-1 px-2 tabular-nums">{roi.n.toLocaleString()}</td>
                      <td className="text-right py-1 px-2 tabular-nums">{roi.hit_rate.toFixed(1)}%</td>
                      <td className={`text-right py-1 px-2 tabular-nums ${roiStyle(roi.roi)}`}>
                        {roi.roi >= 0 ? '+' : ''}{roi.roi.toFixed(1)}%
                      </td>
                      {hasPeriod && (
                        <td className="text-right py-1 px-2 tabular-nums text-xs">
                          {deltaIcon(pc?.delta_roi)}{' '}
                          {pc ? (pc.delta_roi >= 0 ? '+' : '') + pc.delta_roi.toFixed(1) : '—'}
                        </td>
                      )}
                      <td className={`text-right py-1 px-2 tabular-nums ${roi.pnl < 0 ? 'text-rose-500' : 'text-emerald-600'}`}>
                        {roi.pnl >= 0 ? '+' : ''}{Math.round(roi.pnl).toLocaleString()}
                      </td>
                      <td className="text-right py-1 px-2 tabular-nums text-xs text-slate-500">
                        {s.brier !== null ? s.brier.toFixed(4) : '—'}
                      </td>
                      <td className="text-right py-1 px-2 tabular-nums text-xs text-slate-500">
                        {s.ece !== null ? s.ece.toFixed(4) : '—'}
                      </td>
                      <td className="py-1 px-2 text-xs text-amber-600">
                        {s.marker && (
                          <span className="inline-flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" />
                            {s.marker.trim().replace(/[\[\]]/g, '')}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

function MonthlyTrendCard({ monthly }: { monthly: MonthlyEntry[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">月別 ROI 推移 (累積P&L 含む)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-slate-500">
                <th className="text-left py-1 px-2">月</th>
                <th className="text-right py-1 px-2">bets</th>
                <th className="text-right py-1 px-2">勝率</th>
                <th className="text-right py-1 px-2">ROI</th>
                <th className="text-right py-1 px-2">P&L</th>
                <th className="text-right py-1 px-2">累積 P&L</th>
              </tr>
            </thead>
            <tbody>
              {monthly.map((m) => {
                const hitRate = m.n_bets ? (m.hits / m.n_bets) * 100 : 0;
                return (
                  <tr key={m.month} className="border-b border-slate-100 dark:border-slate-800">
                    <td className="py-1 px-2 font-mono">{m.month}</td>
                    <td className="text-right py-1 px-2 tabular-nums">{m.n_bets.toLocaleString()}</td>
                    <td className="text-right py-1 px-2 tabular-nums">{hitRate.toFixed(1)}%</td>
                    <td className={`text-right py-1 px-2 tabular-nums ${roiStyle(m.roi)}`}>
                      {m.roi >= 0 ? '+' : ''}{m.roi.toFixed(1)}%
                    </td>
                    <td className={`text-right py-1 px-2 tabular-nums ${m.pnl < 0 ? 'text-rose-500' : 'text-emerald-600'}`}>
                      {m.pnl >= 0 ? '+' : ''}{Math.round(m.pnl).toLocaleString()}
                    </td>
                    <td className={`text-right py-1 px-2 tabular-nums font-semibold ${m.cum_pnl < 0 ? 'text-rose-600' : 'text-emerald-700'}`}>
                      {m.cum_pnl >= 0 ? '+' : ''}{Math.round(m.cum_pnl).toLocaleString()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

// ===========================================================================
// Main page
// ===========================================================================
export default function PolarisSegmentsPage() {
  const { data: runsData } = useSWR<{ runs: RunMeta[] }>(
    '/api/analysis/polaris-segments',
    fetcher,
  );

  const runs = runsData?.runs ?? [];
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // default to newest run
  const activeRunId = selectedRunId ?? runs[0]?.run_id ?? null;

  const { data: detail, error } = useSWR<RunDetail>(
    activeRunId ? `/api/analysis/polaris-segments?run_id=${activeRunId}` : null,
    fetcher,
  );

  const sortedAxes = useMemo(() => {
    if (!detail) return [];
    const keys = Object.keys(detail.segments.axes);
    return keys.sort((a, b) => {
      const ai = AXIS_ORDER.indexOf(a);
      const bi = AXIS_ORDER.indexOf(b);
      if (ai === -1 && bi === -1) return a.localeCompare(b);
      if (ai === -1) return 1;
      if (bi === -1) return -1;
      return ai - bi;
    });
  }, [detail]);

  return (
    <div className="container mx-auto p-4 space-y-4 max-w-7xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Link
            href="/models"
            className="flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
          >
            <ArrowLeft className="w-4 h-4" />
            モデル一覧
          </Link>
          <h1 className="text-xl font-bold">polaris セグメント分析</h1>
        </div>

        {runs.length > 0 && (
          <select
            value={activeRunId ?? ''}
            onChange={(e) => setSelectedRunId(e.target.value)}
            className="border rounded px-3 py-1 text-sm bg-white dark:bg-slate-800 dark:border-slate-700"
          >
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id} ({r.model?.toUpperCase() || '?'}, {r.total_races?.toLocaleString() || '?'}R)
              </option>
            ))}
          </select>
        )}
      </div>

      {!runs.length && (
        <Card>
          <CardContent className="py-12 text-center text-slate-500">
            <p>polaris_segments の実行結果がまだありません。</p>
            <p className="text-xs mt-2 font-mono">
              python -m ml.analyze.polaris_segments --run-id [name]
            </p>
          </CardContent>
        </Card>
      )}

      {error && (
        <Card>
          <CardContent className="py-6 text-rose-600">
            読み込みエラー: {String(error)}
          </CardContent>
        </Card>
      )}

      {detail && (
        <>
          <SummaryCard detail={detail} />

          {detail.segments.monthly?.monthly && detail.segments.monthly.monthly.length > 0 && (
            <MonthlyTrendCard monthly={detail.segments.monthly.monthly} />
          )}

          <div className="space-y-3">
            {sortedAxes.map((axisKey) => (
              <AxisCard
                key={axisKey}
                axisKey={axisKey}
                segments={detail.segments.axes[axisKey]}
                periodCompare={detail.period_compare?.[axisKey]}
              />
            ))}
          </div>

          <p className="text-xs text-slate-500 text-center pt-4 pb-8">
            ソース: <code>data3/analysis/polaris_segments/{detail.run_id}/</code>
            　 再生成: <code>python -m ml.analyze.polaris_segments --run-id {detail.run_id}</code>
          </p>
        </>
      )}
    </div>
  );
}
