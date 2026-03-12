'use client';

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import type { SimulationResult } from './types';

interface Props {
  results: SimulationResult[];
  initialBankroll: number;
  modeColors: Record<string, string>;
}

export default function BankrollChart({ results, initialBankroll, modeColors }: Props) {
  const chartData = useMemo(() => {
    if (!results.length) return [];

    // Collect all unique dates across all presets (date-based merge)
    const allDatesSet = new Set<string>();
    for (const r of results) {
      if (!r.history) continue;
      for (const h of r.history) {
        if (h.date) allDatesSet.add(h.date);
      }
    }
    const allDates = [...allDatesSet].sort();
    if (!allDates.length) return [];

    // Build date→bankroll maps for each result
    const dateMaps = results.map(r => {
      const m = new Map<string, number>();
      if (!r.history) return m;
      for (const h of r.history) {
        if (h.date) m.set(h.date, h.bankroll);
      }
      return m;
    });

    // For each date, carry forward the last known bankroll
    const lastKnown = results.map(() => initialBankroll);

    return allDates.map((date) => {
      const point: Record<string, string | number> = {
        date,
        label: `${date.slice(4, 6)}/${date.slice(6, 8)}`,
      };

      for (let ri = 0; ri < results.length; ri++) {
        const val = dateMaps[ri].get(date);
        if (val !== undefined) {
          lastKnown[ri] = val;
        }
        point[results[ri].mode] = lastKnown[ri];
      }

      return point;
    });
  }, [results, initialBankroll]);

  if (!chartData.length) {
    return <div className="flex h-64 items-center justify-center text-muted-foreground">No data</div>;
  }

  // Find max bankroll for Y axis
  const maxBankroll = Math.max(
    initialBankroll * 1.5,
    ...results.map(r => Math.max(...r.history.map(h => h.bankroll))),
  );

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11 }}
          interval={Math.max(0, Math.floor(chartData.length / 15))}
        />
        <YAxis
          tick={{ fontSize: 11 }}
          tickFormatter={(v: number) => v >= 1000 ? `${Math.round(v / 1000)}K` : String(v)}
          domain={[0, maxBankroll]}
        />
        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
        <Tooltip
          formatter={(value: any, name: any) => {
            const v = Number(value);
            const strategy = results.find(r => r.mode === name);
            return [isNaN(v) ? '' : v.toLocaleString(), strategy?.label ?? String(name)];
          }}
          labelFormatter={(label: any) => `Date: ${label}`}
          contentStyle={{ fontSize: 12 }}
        />
        <Legend
          formatter={(value: string) => {
            const strategy = results.find(r => r.mode === value);
            return strategy?.label ?? value;
          }}
          wrapperStyle={{ fontSize: 12 }}
        />
        <ReferenceLine
          y={initialBankroll}
          stroke="#94a3b8"
          strokeDasharray="5 5"
          label={{ value: 'Initial', position: 'right', fontSize: 11, fill: '#94a3b8' }}
        />
        {results.map(r => (
          <Line
            key={r.mode}
            type="monotone"
            dataKey={r.mode}
            stroke={modeColors[r.mode] ?? '#888'}
            strokeWidth={r.mode === 'intersection' ? 2.5 : 1.5}
            dot={false}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
