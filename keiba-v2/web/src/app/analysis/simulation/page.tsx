'use client';

import { useState, useMemo } from 'react';
import { useSimulationResult, useSimulationVersions } from '@/hooks/useSimulationResult';
import { cn } from '@/lib/utils';
import type { SimulationResult } from './types';
import BankrollChart from './BankrollChart';

const PRESET_LABELS: Record<string, string> = {
  standard: 'Standard',
  aggressive: 'Aggressive',
  ev_strategy: 'EV Strategy',
  simple: 'Simple',
};

const MODE_COLORS: Record<string, string> = {
  intersection: '#ef4444',
  relaxed: '#f59e0b',
  ev_focus: '#3b82f6',
  simple: '#10b981',
  simple_ev2: '#8b5cf6',
  simple_wide: '#f97316',
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

function ResultsTable({ results, initialBankroll, showBudget }: { results: SimulationResult[]; initialBankroll: number; showBudget?: boolean }) {
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
                {showBudget && (
                  <td className="px-3 py-2 font-semibold tabular-nums">{r.budget_label}</td>
                )}
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
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);
  const { data, isLoading, error } = useSimulationResult(selectedVersion);
  const { versions } = useSimulationVersions();
  const defaultPreset = data?.presets?.[0] ?? 'ev_strategy';
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [selectedBudget, setSelectedBudget] = useState('2%');
  const activePreset = selectedPreset ?? defaultPreset;

  const filteredResults = useMemo(() => {
    if (!data) return [];
    return data.results.filter(
      r => r.preset === activePreset && r.budget_label === selectedBudget,
    );
  }, [data, activePreset, selectedBudget]);

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

  /** 購入頻度・購入なし日数の統計 */
  const frequencyStats = useMemo(() => {
    if (!bestResult?.history) return null;
    const dates = bestResult.history
      .map(h => h.date)
      .filter((d): d is string => d !== null)
      .sort();
    if (dates.length < 2) return null;

    // 日付間のギャップ（日数）
    const gaps: number[] = [];
    for (let i = 1; i < dates.length; i++) {
      const d1 = new Date(dates[i - 1].replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3'));
      const d2 = new Date(dates[i].replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3'));
      const diffDays = Math.round((d2.getTime() - d1.getTime()) / 86400000);
      gaps.push(diffDays);
    }

    const maxGap = Math.max(...gaps);
    const avgGap = gaps.reduce((s, g) => s + g, 0) / gaps.length;

    // 月別ベット数
    const monthlyBets: Record<string, number> = {};
    for (const d of dates) {
      const ym = `${d.slice(0, 4)}-${d.slice(4, 6)}`;
      monthlyBets[ym] = (monthlyBets[ym] ?? 0) + 1;
    }
    const months = Object.keys(monthlyBets).sort();
    const monthlyAvg = dates.length / months.length;

    // 全期間の開催日数を推定（土日＝週2日）
    const firstDate = new Date(dates[0].replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3'));
    const lastDate = new Date(dates[dates.length - 1].replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3'));
    const totalCalendarDays = Math.round((lastDate.getTime() - firstDate.getTime()) / 86400000) + 1;
    const estimatedRacingDays = Math.round(totalCalendarDays * 2 / 7); // 週2開催想定

    // 月別で購入0日の月を計算
    const allMonths: string[] = [];
    const cur = new Date(firstDate);
    while (cur <= lastDate) {
      const ym = `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, '0')}`;
      if (!allMonths.includes(ym)) allMonths.push(ym);
      cur.setMonth(cur.getMonth() + 1);
    }
    const zeroBetMonths = allMonths.filter(m => !monthlyBets[m]);

    return {
      betDays: dates.length,
      estimatedRacingDays,
      noBetDays: Math.max(0, estimatedRacingDays - dates.length),
      avgGap: Math.round(avgGap * 10) / 10,
      maxGap,
      monthlyAvg: Math.round(monthlyAvg * 10) / 10,
      monthlyBets,
      months,
      allMonths,
      zeroBetMonths,
    };
  }, [bestResult]);

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
            初期資金 {data.initial_bankroll.toLocaleString()}円 / 複利シミュレーション / {periodInfo ? `${periodInfo.start} ~ ${periodInfo.end}（${periodInfo.days}開催日）` : '---'}
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
            <option value="">最新</option>
            {versions.map(v => (
              <option key={v} value={v}>v{v}</option>
            ))}
          </select>
        )}
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <div>
          <label className="text-xs font-medium text-muted-foreground">Preset</label>
          <div className="mt-1 flex gap-1">
            {data.presets.map(p => (
              <button
                key={p}
                onClick={() => setSelectedPreset(p === defaultPreset ? null : p)}
                className={cn(
                  'px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors',
                  activePreset === p
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

      {/* Betting Frequency */}
      {bestResult && frequencyStats && (
        <div className="mb-6 rounded-xl border bg-background p-4">
          <h2 className="mb-3 text-lg font-semibold">
            Betting Frequency ({bestResult.label.split(' ')[0]})
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5 mb-4">
            <MetricCard
              label="購入日数"
              value={`${frequencyStats.betDays}日`}
              sub={`推定開催 ~${frequencyStats.estimatedRacingDays}日中`}
              color="blue"
            />
            <MetricCard
              label="購入なし開催日"
              value={`~${frequencyStats.noBetDays}日`}
              sub={`${frequencyStats.estimatedRacingDays > 0 ? Math.round((1 - frequencyStats.betDays / frequencyStats.estimatedRacingDays) * 100) : 0}% スキップ`}
              color="amber"
            />
            <MetricCard
              label="月平均"
              value={`${frequencyStats.monthlyAvg}回`}
              sub={`${frequencyStats.months.length}ヶ月間`}
              color="gray"
            />
            <MetricCard
              label="平均間隔"
              value={`${frequencyStats.avgGap}日`}
              sub={`購入日間の平均`}
              color="gray"
            />
            <MetricCard
              label="最大間隔"
              value={`${frequencyStats.maxGap}日`}
              sub="連続購入なし最長"
              color={frequencyStats.maxGap >= 30 ? 'red' : 'amber'}
            />
          </div>
          {/* Monthly breakdown */}
          <div className="overflow-x-auto">
            <div className="flex gap-1 min-w-fit">
              {frequencyStats.allMonths.map(m => {
                const count = frequencyStats.monthlyBets[m] ?? 0;
                const isZero = count === 0;
                return (
                  <div
                    key={m}
                    className={cn(
                      'flex flex-col items-center rounded px-2 py-1.5 text-xs min-w-[52px]',
                      isZero
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
              r => r.preset === activePreset && r.mode === bestResult.mode,
            )}
            initialBankroll={data.initial_bankroll}
            showBudget
          />
        </div>
      )}
    </div>
  );
}
