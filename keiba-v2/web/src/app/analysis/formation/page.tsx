'use client';

import { useState, useMemo } from 'react';
import useSWR from 'swr';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------
// Types
// ---------------------------------------------------------------
interface MonthlyData {
  month: string;
  races: number;
  inv: number;
  ret: number;
  hits: number;
  roi: number;
  pnl: number;
}

interface HitDetail {
  race_id: string;
  ticket: number[];
  payout: number;
}

interface Strategy {
  key: string;
  label: string;
  tier: string;
  fired_races: number;
  total_hits: number;
  total_invested: number;
  total_return: number;
  roi: number;
  avg_payout: number;
  monthly_inv: number;
  hit_rate: number;
  roi_ex_top1: number;
  roi_first_half: number;
  roi_second_half: number;
  top1_payout: number;
  top1_dependency: number;
  monthly: MonthlyData[];
  hit_details: HitDetail[];
}

interface FormationData {
  created_at: string;
  period_start: string;
  period_end: string;
  total_races: number;
  races_with_payouts: number;
  strategies: Strategy[];
}

// ---------------------------------------------------------------
// Fetcher
// ---------------------------------------------------------------
const fetcher = (url: string) => fetch(url).then(r => r.json());

// ---------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------
function MetricCard({ label, value, sub, color }: {
  label: string;
  value: string;
  sub?: string;
  color?: 'blue' | 'green' | 'red' | 'amber' | 'gray' | 'purple';
}) {
  const colors = {
    blue: 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30',
    green: 'border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/30',
    red: 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30',
    amber: 'border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30',
    gray: 'border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900/30',
    purple: 'border-purple-200 bg-purple-50 dark:border-purple-800 dark:bg-purple-950/30',
  };
  return (
    <div className={cn('rounded-lg border px-4 py-3', colors[color ?? 'gray'])}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-bold tabular-nums">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

const TIER_COLORS: Record<string, string> = {
  top: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  recommended: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  base: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
  aggressive: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
};

const TIER_LABELS: Record<string, string> = {
  top: 'S',
  recommended: 'A',
  base: 'Base',
  aggressive: 'B',
};

function StrategyTable({ strategies, onSelect, selected }: {
  strategies: Strategy[];
  onSelect: (key: string) => void;
  selected: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">Tier</th>
            <th className="px-3 py-2 font-medium">Strategy</th>
            <th className="px-3 py-2 font-medium text-right">Fire</th>
            <th className="px-3 py-2 font-medium text-right">Hits</th>
            <th className="px-3 py-2 font-medium text-right">ROI</th>
            <th className="px-3 py-2 font-medium text-right">Top1除外</th>
            <th className="px-3 py-2 font-medium text-right">前半</th>
            <th className="px-3 py-2 font-medium text-right">後半</th>
            <th className="px-3 py-2 font-medium text-right">Invested</th>
            <th className="px-3 py-2 font-medium text-right">Return</th>
            <th className="px-3 py-2 font-medium text-right">AvgPay</th>
            <th className="px-3 py-2 font-medium text-right">月投資</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map(s => (
            <tr
              key={s.key}
              onClick={() => onSelect(s.key)}
              className={cn(
                'border-b transition-colors cursor-pointer',
                selected === s.key
                  ? 'bg-blue-50 dark:bg-blue-950/30'
                  : 'hover:bg-muted/30',
                s.roi >= 200 && 'bg-emerald-50/50 dark:bg-emerald-950/20',
              )}
            >
              <td className="px-3 py-2">
                <span className={cn('inline-block px-2 py-0.5 rounded text-xs font-semibold', TIER_COLORS[s.tier])}>
                  {TIER_LABELS[s.tier] ?? s.tier}
                </span>
              </td>
              <td className="px-3 py-2 font-medium">{s.label}</td>
              <td className="px-3 py-2 text-right tabular-nums">{s.fired_races}</td>
              <td className="px-3 py-2 text-right tabular-nums">{s.total_hits}</td>
              <td className={cn('px-3 py-2 text-right tabular-nums font-bold',
                s.roi >= 200 ? 'text-emerald-600' : s.roi >= 100 ? 'text-blue-600' : 'text-red-500')}>
                {s.roi.toFixed(1)}%
              </td>
              <td className={cn('px-3 py-2 text-right tabular-nums',
                s.roi_ex_top1 >= 100 ? 'text-emerald-600' : 'text-red-500')}>
                {s.roi_ex_top1.toFixed(1)}%
              </td>
              <td className={cn('px-3 py-2 text-right tabular-nums',
                s.roi_first_half >= 100 ? 'text-emerald-600' : 'text-red-500')}>
                {s.roi_first_half.toFixed(0)}%
              </td>
              <td className={cn('px-3 py-2 text-right tabular-nums',
                s.roi_second_half >= 100 ? 'text-emerald-600' : 'text-red-500')}>
                {s.roi_second_half.toFixed(0)}%
              </td>
              <td className="px-3 py-2 text-right tabular-nums">
                {s.total_invested.toLocaleString()}
              </td>
              <td className="px-3 py-2 text-right tabular-nums font-semibold">
                {s.total_return.toLocaleString()}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">
                {s.avg_payout.toLocaleString()}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                {s.monthly_inv.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MonthlyChart({ monthly }: { monthly: MonthlyData[] }) {
  const maxPnl = Math.max(...monthly.map(m => Math.abs(m.pnl)), 1);

  // cumulative P&L
  let cum = 0;
  const cumData = monthly.map(m => {
    cum += m.pnl;
    return { ...m, cum };
  });
  const maxCum = Math.max(...cumData.map(d => Math.abs(d.cum)), 1);

  return (
    <div className="space-y-3">
      {/* Cumulative line (simple bar representation) */}
      <div className="flex items-end gap-1 h-32">
        {cumData.map(d => {
          const height = Math.abs(d.cum) / maxCum * 100;
          return (
            <div key={d.month} className="flex-1 flex flex-col items-center justify-end h-full">
              <div
                className={cn(
                  'w-full rounded-t transition-all min-h-[2px]',
                  d.cum >= 0 ? 'bg-emerald-500' : 'bg-red-400',
                )}
                style={{ height: `${Math.max(height, 2)}%` }}
                title={`${d.month}: ${d.cum >= 0 ? '+' : ''}${d.cum.toLocaleString()}`}
              />
            </div>
          );
        })}
      </div>

      {/* Monthly table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-muted-foreground">
              <th className="px-2 py-1 text-left font-medium">Month</th>
              <th className="px-2 py-1 text-right font-medium">R</th>
              <th className="px-2 py-1 text-right font-medium">Hit</th>
              <th className="px-2 py-1 text-right font-medium">Inv</th>
              <th className="px-2 py-1 text-right font-medium">Ret</th>
              <th className="px-2 py-1 text-right font-medium">ROI</th>
              <th className="px-2 py-1 text-right font-medium">PnL</th>
              <th className="px-2 py-1 text-right font-medium">Cum</th>
            </tr>
          </thead>
          <tbody>
            {cumData.map(d => (
              <tr key={d.month} className="border-b hover:bg-muted/30">
                <td className="px-2 py-1 font-medium">{d.month}</td>
                <td className="px-2 py-1 text-right tabular-nums">{d.races}</td>
                <td className="px-2 py-1 text-right tabular-nums">{d.hits}</td>
                <td className="px-2 py-1 text-right tabular-nums">{d.inv.toLocaleString()}</td>
                <td className="px-2 py-1 text-right tabular-nums">{d.ret.toLocaleString()}</td>
                <td className={cn('px-2 py-1 text-right tabular-nums font-semibold',
                  d.roi >= 100 ? 'text-emerald-600' : 'text-red-500')}>
                  {d.roi.toFixed(0)}%
                </td>
                <td className={cn('px-2 py-1 text-right tabular-nums',
                  d.pnl >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                  {d.pnl >= 0 ? '+' : ''}{d.pnl.toLocaleString()}
                </td>
                <td className={cn('px-2 py-1 text-right tabular-nums font-semibold',
                  d.cum >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                  {d.cum >= 0 ? '+' : ''}{d.cum.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const VENUE_NAMES: Record<string, string> = {
  '01': '札幌', '02': '函館', '03': '福島', '04': '新潟', '05': '東京',
  '06': '中山', '07': '中京', '08': '京都', '09': '阪神', '10': '小倉',
};

function parseRaceId(id: string) {
  const y = id.slice(0, 4);
  const m = id.slice(4, 6);
  const d = id.slice(6, 8);
  const venueCode = id.slice(8, 10);
  const raceNum = parseInt(id.slice(14, 16), 10);
  const venueName = VENUE_NAMES[venueCode] ?? venueCode;
  const date = `${y}-${m}-${d}`;
  const href = `/races-v2/${date}/${venueName}/${id}`;
  return { date, venueName, raceNum, href };
}

function HitDetailsTable({ hits }: { hits: HitDetail[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">#</th>
            <th className="px-3 py-2 font-medium">Date</th>
            <th className="px-3 py-2 font-medium">Venue</th>
            <th className="px-3 py-2 font-medium text-right">R</th>
            <th className="px-3 py-2 font-medium">Ticket</th>
            <th className="px-3 py-2 font-medium text-right">Payout</th>
          </tr>
        </thead>
        <tbody>
          {hits.map((h, i) => {
            const r = parseRaceId(h.race_id);
            return (
              <tr key={`${h.race_id}-${i}`} className="border-b hover:bg-muted/30">
                <td className="px-3 py-2 text-muted-foreground">{i + 1}</td>
                <td className="px-3 py-2">
                  <a
                    href={r.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline dark:text-blue-400"
                  >
                    {r.date}
                  </a>
                </td>
                <td className="px-3 py-2 font-medium">{r.venueName}</td>
                <td className="px-3 py-2 text-right tabular-nums">{r.raceNum}</td>
                <td className="px-3 py-2 font-mono tabular-nums">
                  {h.ticket[0]}-{h.ticket[1]}-{h.ticket[2]}
                </td>
                <td className={cn('px-3 py-2 text-right tabular-nums font-bold',
                  h.payout >= 500000 ? 'text-emerald-600' : h.payout >= 100000 ? 'text-blue-600' : '')}>
                  {h.payout.toLocaleString()}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------
export default function FormationPage() {
  const { data, isLoading, error } = useSWR<FormationData>('/api/formation-backtest', fetcher);
  const [selectedKey, setSelectedKey] = useState<string>('VB_45F3_FO4_CG10');

  const selectedStrategy = useMemo(() => {
    if (!data) return null;
    return data.strategies.find(s => s.key === selectedKey) ?? data.strategies[0];
  }, [data, selectedKey]);

  const bestStrategy = useMemo(() => {
    if (!data) return null;
    return [...data.strategies].sort((a, b) => b.roi - a.roi)[0];
  }, [data]);

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
          python -m ml.export_formation_backtest
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">
          三連単フォーメーション検証
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          VB頭フォーメーション (★→▲▲▲▲→▲▲▲▲△△△) / {data.period_start} ~ {data.period_end}
          {' '}/ {data.total_races.toLocaleString()} races
          <span className="ml-2 text-xs">Updated: {data.created_at.split('T')[0]}</span>
        </p>
      </div>

      {/* Best Strategy Summary */}
      {bestStrategy && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard
            label="Best Strategy"
            value={bestStrategy.label}
            sub={`Tier ${TIER_LABELS[bestStrategy.tier]}`}
            color="purple"
          />
          <MetricCard
            label="ROI"
            value={`${bestStrategy.roi.toFixed(1)}%`}
            sub={`${bestStrategy.fired_races}R / ${bestStrategy.total_hits} hits`}
            color="green"
          />
          <MetricCard
            label="P&L"
            value={`+${(bestStrategy.total_return - bestStrategy.total_invested).toLocaleString()}`}
            sub={`${bestStrategy.total_invested.toLocaleString()} inv`}
            color="green"
          />
          <MetricCard
            label="Top1除外ROI"
            value={`${bestStrategy.roi_ex_top1.toFixed(1)}%`}
            sub={`Top1依存: ${bestStrategy.top1_dependency.toFixed(0)}%`}
            color={bestStrategy.roi_ex_top1 >= 100 ? 'green' : 'amber'}
          />
          <MetricCard
            label="前半 / 後半"
            value={`${bestStrategy.roi_first_half.toFixed(0)}% / ${bestStrategy.roi_second_half.toFixed(0)}%`}
            sub="period split"
            color={bestStrategy.roi_first_half >= 100 && bestStrategy.roi_second_half >= 100 ? 'green' : 'amber'}
          />
          <MetricCard
            label="月投資"
            value={`${bestStrategy.monthly_inv.toLocaleString()}`}
            sub={`avg ${bestStrategy.avg_payout.toLocaleString()}/hit`}
            color="gray"
          />
        </div>
      )}

      {/* Strategy Logic */}
      <div className="mb-6 rounded-xl border bg-background p-4">
        <h2 className="mb-2 text-sm font-semibold text-muted-foreground">Formation Logic</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg bg-muted/30 p-3 text-sm">
            <div className="font-semibold mb-1">Pattern: VB Head</div>
            <div className="font-mono text-xs space-y-0.5 text-muted-foreground">
              <div>★(1st): WinEV &ge; 1.5, Odds &ge; 10 (VB horse)</div>
              <div>▲(2nd): P% top 4 (excl ★)</div>
              <div>△(3rd): next 3 horses</div>
              <div>= ★ → ▲▲▲▲ → ▲▲▲▲△△△ (max 28 tickets)</div>
            </div>
          </div>
          <div className="rounded-lg bg-muted/30 p-3 text-sm">
            <div className="font-semibold mb-1">Filters</div>
            <div className="font-mono text-xs space-y-0.5 text-muted-foreground">
              <div>P% Top3 Share &lt; 0.45 (upset prediction)</div>
              <div>Fav Odds &ge; 3.0 (no clear favorite)</div>
              <div>VB candidates &ge; 3 (quality gate)</div>
              <div className="text-emerald-600">+ FavOdds &lt; 4.0 / ConfGap &lt; 0.10</div>
            </div>
          </div>
        </div>
      </div>

      {/* Strategy Comparison */}
      <div className="mb-6 rounded-xl border bg-background p-4">
        <h2 className="mb-3 text-lg font-semibold">Strategy Comparison</h2>
        <StrategyTable
          strategies={data.strategies}
          onSelect={setSelectedKey}
          selected={selectedKey}
        />
      </div>

      {/* Selected Strategy Detail */}
      {selectedStrategy && (
        <>
          {/* Monthly Breakdown */}
          <div className="mb-6 rounded-xl border bg-background p-4">
            <h2 className="mb-3 text-lg font-semibold">
              Monthly: {selectedStrategy.label}
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                ROI {selectedStrategy.roi.toFixed(1)}%
              </span>
            </h2>
            <MonthlyChart monthly={selectedStrategy.monthly} />
          </div>

          {/* Hit Details */}
          <div className="rounded-xl border bg-background p-4">
            <h2 className="mb-3 text-lg font-semibold">
              Hit Details: {selectedStrategy.label}
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                {selectedStrategy.total_hits} hits / avg {selectedStrategy.avg_payout.toLocaleString()}
              </span>
            </h2>
            <HitDetailsTable hits={selectedStrategy.hit_details} />
          </div>
        </>
      )}
    </div>
  );
}
