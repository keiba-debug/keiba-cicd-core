'use client';

import { useState, useMemo } from 'react';
import { useSimulationResult, useSimulationVersions } from '@/hooks/useSimulationResult';
import { cn } from '@/lib/utils';
import type { SimulationResult } from './types';
import BankrollChart from './BankrollChart';

const MODE_COLORS: Record<string, string> = {
  adaptive: '#3b82f6',
  intersection: '#ef4444',
  intersection_place: '#f97316',
  relaxed: '#f59e0b',
  simple: '#10b981',
  simple_ev2: '#8b5cf6',
  simple_wide: '#6366f1',
};

function MetricCard({ label, value, sub, color }: {
  label: string;
  value: string;
  sub?: string;
  color?: 'blue' | 'green' | 'red' | 'amber' | 'gray';
}) {
  const colors = {
    blue: 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30',
    green: 'border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/30',
    red: 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30',
    amber: 'border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30',
    gray: 'border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900/30',
  };
  return (
    <div className={cn('rounded-lg border px-4 py-3', colors[color ?? 'gray'])}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-bold tabular-nums">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function BetBreakdown({ result }: { result: SimulationResult }) {
  const items = [
    { label: '単勝', count: result.win_bets ?? 0, rate: result.win_hit_rate ?? 0, color: 'text-blue-600' },
    { label: '複勝', count: result.place_bets ?? 0, rate: result.place_hit_rate ?? 0, color: 'text-emerald-600' },
    { label: 'ワイド', count: result.wide_bets ?? 0, rate: result.wide_hit_rate ?? 0, color: 'text-purple-600' },
    { label: '馬連', count: result.umaren_bets ?? 0, rate: result.umaren_hit_rate ?? 0, color: 'text-orange-600' },
  ].filter(i => i.count > 0);

  if (items.length === 0) return null;

  return (
    <div className="flex gap-3 text-xs">
      {items.map(i => (
        <span key={i.label} className={cn('tabular-nums', i.color)}>
          {i.label} {i.count}({i.rate}%)
        </span>
      ))}
    </div>
  );
}

function ResultsTable({ results, initialBankroll, showBudget }: {
  results: SimulationResult[];
  initialBankroll: number;
  showBudget?: boolean;
}) {
  const sorted = [...results].sort((a, b) => b.final_bankroll - a.final_bankroll);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">Strategy</th>
            {showBudget && <th className="px-3 py-2 font-medium">Budget</th>}
            <th className="px-3 py-2 font-medium text-right">Final</th>
            <th className="px-3 py-2 font-medium text-right">ROI</th>
            <th className="px-3 py-2 font-medium text-right">Flat ROI</th>
            <th className="px-3 py-2 font-medium text-right">Max DD</th>
            <th className="px-3 py-2 font-medium text-right">Calmar</th>
            <th className="px-3 py-2 font-medium text-right">Sharpe</th>
            <th className="px-3 py-2 font-medium text-right">W/L</th>
            <th className="px-3 py-2 font-medium text-right">Bets</th>
            <th className="px-3 py-2 font-medium">Breakdown</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => {
            const isProfit = r.final_bankroll > initialBankroll;
            return (
              <tr
                key={`${r.mode}-${r.budget_label}-${i}`}
                className={cn(
                  'border-b transition-colors hover:bg-muted/30',
                  isProfit && 'bg-emerald-50/50 dark:bg-emerald-950/20',
                )}
              >
                <td className="px-3 py-2 font-medium">
                  <span className="inline-block w-3 h-3 rounded-full mr-2"
                    style={{ backgroundColor: MODE_COLORS[r.mode] ?? '#888' }} />
                  {r.label}
                </td>
                {showBudget && (
                  <td className="px-3 py-2 font-semibold tabular-nums">{r.budget_label}</td>
                )}
                <td className={cn('px-3 py-2 text-right tabular-nums font-semibold',
                  isProfit ? 'text-emerald-600' : 'text-red-500')}>
                  {r.final_bankroll.toLocaleString()}
                </td>
                <td className={cn('px-3 py-2 text-right tabular-nums',
                  r.roi_pct >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                  {r.roi_pct >= 0 ? '+' : ''}{r.roi_pct}%
                </td>
                <td className={cn('px-3 py-2 text-right tabular-nums',
                  r.flat_roi >= 100 ? 'text-emerald-600' : 'text-red-500')}>
                  {r.flat_roi}%
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-red-500">
                  {r.max_dd}%
                </td>
                <td className={cn('px-3 py-2 text-right tabular-nums font-semibold',
                  (r.calmar ?? 0) >= 3 ? 'text-emerald-600' : (r.calmar ?? 0) >= 1 ? 'text-amber-600' : 'text-red-500')}>
                  {(r.calmar ?? 0).toFixed(2)}
                </td>
                <td className={cn('px-3 py-2 text-right tabular-nums',
                  r.sharpe >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                  {r.sharpe.toFixed(3)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className="text-emerald-600">{r.win_days}</span>
                  <span className="text-muted-foreground">/</span>
                  <span className="text-red-500">{r.lose_days}</span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.total_bets}
                </td>
                <td className="px-3 py-2">
                  <BetBreakdown result={r} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function SimulationPage() {
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);
  const { data, isLoading, error } = useSimulationResult(selectedVersion);
  const { versions } = useSimulationVersions();
  const [selectedBudget, setSelectedBudget] = useState('3%');

  // All results for the selected budget (one per preset)
  const filteredResults = useMemo(() => {
    if (!data) return [];
    return data.results.filter(r => r.budget_label === selectedBudget);
  }, [data, selectedBudget]);

  const bestResult = useMemo(() => {
    if (!filteredResults.length) return null;
    return [...filteredResults].sort((a, b) => b.final_bankroll - a.final_bankroll)[0];
  }, [filteredResults]);

  const periodInfo = useMemo(() => {
    if (!data?.results[0]?.history) return null;
    const dates = data.results[0].history
      .map(h => h.date)
      .filter((d): d is string => d !== null)
      .sort();
    if (!dates.length) return null;
    return { start: dates[0], end: dates[dates.length - 1], days: dates.length };
  }, [data]);

  const frequencyStats = useMemo(() => {
    if (!bestResult?.history) return null;
    const dates = bestResult.history
      .map(h => h.date)
      .filter((d): d is string => d !== null)
      .sort();
    if (dates.length < 2) return null;

    const gaps: number[] = [];
    for (let i = 1; i < dates.length; i++) {
      const d1 = new Date(dates[i - 1].replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3'));
      const d2 = new Date(dates[i].replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3'));
      gaps.push(Math.round((d2.getTime() - d1.getTime()) / 86400000));
    }

    const maxGap = Math.max(...gaps);
    const avgGap = gaps.reduce((s, g) => s + g, 0) / gaps.length;

    const monthlyBets: Record<string, number> = {};
    for (const d of dates) {
      const ym = `${d.slice(0, 4)}-${d.slice(4, 6)}`;
      monthlyBets[ym] = (monthlyBets[ym] ?? 0) + 1;
    }
    const months = Object.keys(monthlyBets).sort();

    const firstDate = new Date(dates[0].replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3'));
    const lastDate = new Date(dates[dates.length - 1].replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3'));
    const totalCalendarDays = Math.round((lastDate.getTime() - firstDate.getTime()) / 86400000) + 1;
    const estimatedRacingDays = Math.round(totalCalendarDays * 2 / 7);

    const allMonths: string[] = [];
    const cur = new Date(firstDate);
    while (cur <= lastDate) {
      const ym = `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, '0')}`;
      if (!allMonths.includes(ym)) allMonths.push(ym);
      cur.setMonth(cur.getMonth() + 1);
    }

    return {
      betDays: dates.length,
      estimatedRacingDays,
      noBetDays: Math.max(0, estimatedRacingDays - dates.length),
      avgGap: Math.round(avgGap * 10) / 10,
      maxGap,
      monthlyAvg: Math.round(dates.length / months.length * 10) / 10,
      monthlyBets,
      months,
      allMonths,
    };
  }, [bestResult]);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2">
        <div className="text-red-500">{error?.message ?? 'No data'}</div>
        <p className="text-sm text-gray-500">
          python -m ml.simulate_bankroll
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            Bankroll Simulation
            {data.model_version && (
              <span className="ml-2 text-base font-normal text-muted-foreground">
                v{data.model_version}
              </span>
            )}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {data.initial_bankroll.toLocaleString()}円 / 複利 / {periodInfo ? `${periodInfo.start}~${periodInfo.end} (${periodInfo.days}日)` : '---'}
            {data.created_at && (
              <span className="ml-2">/ {data.created_at.replace('T', ' ')}</span>
            )}
          </p>
        </div>
        {versions.length > 0 && (
          <select
            value={selectedVersion ?? ''}
            onChange={(e) => setSelectedVersion(e.target.value || null)}
            className="rounded-lg border border-gray-200 bg-background px-3 py-1.5 text-sm dark:border-gray-700"
          >
            <option value="">Latest</option>
            {versions.map(v => (
              <option key={v} value={v}>v{v}</option>
            ))}
          </select>
        )}
      </div>

      {/* Budget Selector */}
      <div className="mb-6">
        <label className="text-xs font-medium text-muted-foreground">Daily Budget</label>
        <div className="mt-1 flex gap-1">
          {data.budget_configs.map(b => (
            <button
              key={b.label}
              onClick={() => setSelectedBudget(b.label)}
              className={cn(
                'px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors',
                selectedBudget === b.label
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-background text-muted-foreground border-gray-200 dark:border-gray-700 hover:bg-muted/50',
              )}
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      {bestResult && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard
            label="Best Strategy"
            value={bestResult.label.split(' ')[0]}
            sub={bestResult.label}
            color="blue"
          />
          <MetricCard
            label="Final Bankroll"
            value={`${bestResult.final_bankroll.toLocaleString()}`}
            sub={`${bestResult.roi_pct >= 0 ? '+' : ''}${bestResult.roi_pct}%`}
            color={bestResult.final_bankroll > data.initial_bankroll ? 'green' : 'red'}
          />
          <MetricCard
            label="Flat ROI"
            value={`${bestResult.flat_roi}%`}
            sub={`${bestResult.total_bets} bets / ${bestResult.bet_days} days`}
            color={bestResult.flat_roi >= 100 ? 'green' : 'amber'}
          />
          <MetricCard
            label="Max Drawdown"
            value={`${bestResult.max_dd}%`}
            sub={`Loss streak: ${bestResult.max_loss_streak}d`}
            color="red"
          />
          <MetricCard
            label="Sharpe / Calmar"
            value={`${bestResult.sharpe.toFixed(2)} / ${(bestResult.calmar ?? 0).toFixed(2)}`}
            sub={`Win streak: ${bestResult.max_win_streak}d`}
            color={(bestResult.calmar ?? 0) >= 1 ? 'green' : 'amber'}
          />
          <MetricCard
            label="Win Rate"
            value={`${bestResult.bet_days > 0 ? Math.round(bestResult.win_days / bestResult.bet_days * 100) : 0}%`}
            sub={`${bestResult.win_days}W / ${bestResult.lose_days}L`}
            color={bestResult.win_days > bestResult.lose_days ? 'green' : 'amber'}
          />
        </div>
      )}

      {/* Chart */}
      <div className="mb-6 rounded-xl border bg-background p-4">
        <h2 className="mb-3 text-lg font-semibold">Bankroll Trajectory ({selectedBudget})</h2>
        <BankrollChart
          results={filteredResults}
          initialBankroll={data.initial_bankroll}
          modeColors={MODE_COLORS}
        />
      </div>

      {/* Strategy Comparison Table */}
      <div className="mb-6 rounded-xl border bg-background p-4">
        <h2 className="mb-3 text-lg font-semibold">Strategy Comparison ({selectedBudget})</h2>
        <ResultsTable results={filteredResults} initialBankroll={data.initial_bankroll} />
      </div>

      {/* Budget Comparison for Best Strategy */}
      {bestResult && (
        <div className="mb-6 rounded-xl border bg-background p-4">
          <h2 className="mb-3 text-lg font-semibold">
            Budget Comparison: {bestResult.label}
          </h2>
          <ResultsTable
            results={data.results.filter(r => r.mode === bestResult.mode)}
            initialBankroll={data.initial_bankroll}
            showBudget
          />
        </div>
      )}

      {/* Betting Frequency */}
      {bestResult && frequencyStats && (
        <div className="rounded-xl border bg-background p-4">
          <h2 className="mb-3 text-lg font-semibold">
            Betting Frequency: {bestResult.label}
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5 mb-4">
            <MetricCard
              label="Purchase Days"
              value={`${frequencyStats.betDays}`}
              sub={`~${frequencyStats.estimatedRacingDays} racing days`}
              color="blue"
            />
            <MetricCard
              label="Skip Rate"
              value={`${frequencyStats.estimatedRacingDays > 0 ? Math.round((1 - frequencyStats.betDays / frequencyStats.estimatedRacingDays) * 100) : 0}%`}
              sub={`~${frequencyStats.noBetDays} days skipped`}
              color="amber"
            />
            <MetricCard label="Monthly Avg" value={`${frequencyStats.monthlyAvg}`} sub={`${frequencyStats.months.length} months`} color="gray" />
            <MetricCard label="Avg Gap" value={`${frequencyStats.avgGap}d`} color="gray" />
            <MetricCard label="Max Gap" value={`${frequencyStats.maxGap}d`} color={frequencyStats.maxGap >= 30 ? 'red' : 'amber'} />
          </div>
          <div className="overflow-x-auto">
            <div className="flex gap-1 min-w-fit">
              {frequencyStats.allMonths.map(m => {
                const count = frequencyStats.monthlyBets[m] ?? 0;
                return (
                  <div
                    key={m}
                    className={cn(
                      'flex flex-col items-center rounded px-2 py-1.5 text-xs min-w-[52px]',
                      count === 0
                        ? 'bg-red-50 dark:bg-red-950/30 text-red-500'
                        : count >= 5
                          ? 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600'
                          : 'bg-gray-50 dark:bg-gray-800/30 text-muted-foreground',
                    )}
                  >
                    <span className="font-medium">{m.slice(5)}</span>
                    <span className="text-lg font-bold tabular-nums">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
