'use client';

import { useState, useMemo } from 'react';
import { useSimulationResult } from '@/hooks/useSimulationResult';
import { cn } from '@/lib/utils';
import type { SimulationResult } from './types';
import BankrollChart from './BankrollChart';

const PRESET_LABELS: Record<string, string> = {
  standard: 'Standard',
  aggressive: 'Aggressive',
};

const MODE_COLORS: Record<string, string> = {
  exact: '#6b7280',
  win_only: '#10b981',
  passthrough: '#3b82f6',
  equal_win: '#22d3ee',
  s90_n50: '#f59e0b',
  s80_n50: '#f97316',
  equal_50: '#8b5cf6',
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

function ResultsTable({ results, initialBankroll }: { results: SimulationResult[]; initialBankroll: number }) {
  const sorted = [...results].sort((a, b) => b.final_bankroll - a.final_bankroll);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">Strategy</th>
            <th className="px-3 py-2 font-medium text-right">Final</th>
            <th className="px-3 py-2 font-medium text-right">ROI</th>
            <th className="px-3 py-2 font-medium text-right">Flat ROI</th>
            <th className="px-3 py-2 font-medium text-right">Max DD</th>
            <th className="px-3 py-2 font-medium text-right">Calmar</th>
            <th className="px-3 py-2 font-medium text-right">Sharpe</th>
            <th className="px-3 py-2 font-medium text-right">W/L</th>
            <th className="px-3 py-2 font-medium text-right">Max Loss</th>
            <th className="px-3 py-2 font-medium text-right">Max Win</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => {
            const isProfit = r.final_bankroll > initialBankroll;
            return (
              <tr
                key={`${r.mode}-${i}`}
                className={cn(
                  'border-b transition-colors hover:bg-muted/30',
                  isProfit && 'bg-emerald-50/50 dark:bg-emerald-950/20',
                )}
              >
                <td className="px-3 py-2 font-medium">
                  <span className="inline-block w-3 h-3 rounded-full mr-2" style={{ backgroundColor: MODE_COLORS[r.mode] ?? '#888' }} />
                  {r.label}
                </td>
                <td className={cn('px-3 py-2 text-right tabular-nums font-semibold', isProfit ? 'text-emerald-600' : 'text-red-500')}>
                  {r.final_bankroll.toLocaleString()}
                </td>
                <td className={cn('px-3 py-2 text-right tabular-nums', r.roi_pct >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                  {r.roi_pct >= 0 ? '+' : ''}{r.roi_pct}%
                </td>
                <td className={cn('px-3 py-2 text-right tabular-nums', r.flat_roi >= 100 ? 'text-emerald-600' : 'text-red-500')}>
                  {r.flat_roi}%
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-red-500">
                  {r.max_dd}%
                </td>
                <td className={cn('px-3 py-2 text-right tabular-nums font-semibold', (r.calmar ?? 0) >= 3 ? 'text-emerald-600' : (r.calmar ?? 0) >= 1 ? 'text-amber-600' : 'text-red-500')}>
                  {(r.calmar ?? 0).toFixed(2)}
                </td>
                <td className={cn('px-3 py-2 text-right tabular-nums', r.sharpe >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                  {r.sharpe.toFixed(3)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className="text-emerald-600">{r.win_days}</span>
                  <span className="text-muted-foreground">/</span>
                  <span className="text-red-500">{r.lose_days}</span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-red-500">
                  {r.max_loss_streak}d
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-emerald-600">
                  {r.max_win_streak}d
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
  const { data, isLoading, error } = useSimulationResult();
  const [selectedPreset, setSelectedPreset] = useState('aggressive');
  const [selectedBudget, setSelectedBudget] = useState('5%');

  const filteredResults = useMemo(() => {
    if (!data) return [];
    return data.results.filter(
      r => r.preset === selectedPreset && r.budget_label === selectedBudget,
    );
  }, [data, selectedPreset, selectedBudget]);

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

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-gray-500">読み込み中...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2">
        <div className="text-red-500">{error?.message ?? 'データがありません'}</div>
        <p className="text-sm text-gray-500">
          simulate_bankroll.py を実行してください
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Bankroll Simulation</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          初期資金 {data.initial_bankroll.toLocaleString()}円 / 複利シミュレーション / {periodInfo ? `${periodInfo.start} ~ ${periodInfo.end}（${periodInfo.days}開催日）` : '---'}
        </p>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <div>
          <label className="text-xs font-medium text-muted-foreground">Preset</label>
          <div className="mt-1 flex gap-1">
            {data.presets.map(p => (
              <button
                key={p}
                onClick={() => setSelectedPreset(p)}
                className={cn(
                  'px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors',
                  selectedPreset === p
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-background text-muted-foreground border-gray-200 dark:border-gray-700 hover:bg-muted/50',
                )}
              >
                {PRESET_LABELS[p] ?? p}
              </button>
            ))}
          </div>
        </div>
        <div>
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
      </div>

      {/* Summary Cards */}
      {bestResult && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
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
            sub={`${bestResult.total_bets} bets`}
            color={bestResult.flat_roi >= 100 ? 'green' : 'amber'}
          />
          <MetricCard
            label="Max Drawdown"
            value={`${bestResult.max_dd}%`}
            sub={`Calmar: ${(bestResult.calmar ?? 0).toFixed(2)}`}
            color="red"
          />
          <MetricCard
            label="Sharpe / Calmar"
            value={`${bestResult.sharpe.toFixed(3)}`}
            sub={`Calmar ${(bestResult.calmar ?? 0).toFixed(2)} / Loss ${bestResult.max_loss_streak}d`}
            color={(bestResult.calmar ?? 0) >= 3 ? 'green' : 'amber'}
          />
          <MetricCard
            label="Win Rate (days)"
            value={`${bestResult.bet_days > 0 ? Math.round(bestResult.win_days / bestResult.bet_days * 100) : 0}%`}
            sub={`${bestResult.win_days}W / ${bestResult.lose_days}L`}
            color={bestResult.win_days > bestResult.lose_days ? 'green' : 'amber'}
          />
        </div>
      )}

      {/* Chart */}
      <div className="mb-6 rounded-xl border bg-background p-4">
        <h2 className="mb-3 text-lg font-semibold">Bankroll Trajectory</h2>
        <BankrollChart
          results={filteredResults}
          initialBankroll={data.initial_bankroll}
          modeColors={MODE_COLORS}
        />
      </div>

      {/* Results Table */}
      <div className="rounded-xl border bg-background p-4">
        <h2 className="mb-3 text-lg font-semibold">Strategy Comparison</h2>
        <ResultsTable results={filteredResults} initialBankroll={data.initial_bankroll} />
      </div>

      {/* Cross-comparison: all budgets for best strategy */}
      {bestResult && (
        <div className="mt-6 rounded-xl border bg-background p-4">
          <h2 className="mb-3 text-lg font-semibold">
            Budget Comparison ({bestResult.label})
          </h2>
          <ResultsTable
            results={data.results.filter(
              r => r.preset === selectedPreset && r.mode === bestResult.mode,
            )}
            initialBankroll={data.initial_bankroll}
          />
        </div>
      )}
    </div>
  );
}
