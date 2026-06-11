'use client';

import { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ReferenceLine, ResponsiveContainer,
} from 'recharts';

export interface TrajectorySeries {
  key: string;
  label: string;
  color: string;
  base: number;   // 初期資金 (eff_w0)。 指数正規化の基準
  history: { date: string | null; bankroll: number }[];
}

interface Props {
  series: TrajectorySeries[];
}

/**
 * キャラ別の資金軌道を「初期資金=100 の指数」で重ね描き。
 * ringfenced (隔離枠 9000円) と通常 (30万) のスケール差を正規化で吸収する。
 */
export default function CharacterChart({ series }: Props) {
  const chartData = useMemo(() => {
    const allDatesSet = new Set<string>();
    for (const s of series) {
      for (const h of s.history) {
        if (h.date) allDatesSet.add(h.date);
      }
    }
    const allDates = [...allDatesSet].sort();
    if (!allDates.length) return [];

    const dateMaps = series.map(s => {
      const m = new Map<string, number>();
      for (const h of s.history) {
        if (h.date) m.set(h.date, h.bankroll);
      }
      return m;
    });
    const lastKnown = series.map(s => s.base);

    return allDates.map((date) => {
      const point: Record<string, string | number> = {
        date,
        label: `${date.slice(2, 4)}/${date.slice(4, 6)}`,
      };
      for (let si = 0; si < series.length; si++) {
        const val = dateMaps[si].get(date);
        if (val !== undefined) lastKnown[si] = val;
        const base = series[si].base || 1;
        point[series[si].key] = Math.round(lastKnown[si] / base * 1000) / 10;
      }
      return point;
    });
  }, [series]);

  if (!chartData.length) {
    return <div className="flex h-64 items-center justify-center text-muted-foreground">No data</div>;
  }

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
          tickFormatter={(v: number) => `${v}`}
          domain={['auto', 'auto']}
        />
        <Tooltip
          formatter={(value, name) => {
            const s = series.find((x) => x.key === name);
            return [`${value}`, s?.label ?? String(name)];
          }}
          labelFormatter={(label) => `${label}`}
          contentStyle={{ fontSize: 12 }}
        />
        <Legend
          formatter={(value: string) => series.find(s => s.key === value)?.label ?? value}
          wrapperStyle={{ fontSize: 12 }}
        />
        <ReferenceLine
          y={100}
          stroke="#94a3b8"
          strokeDasharray="5 5"
          label={{ value: '初期=100', position: 'right', fontSize: 11, fill: '#94a3b8' }}
        />
        {series.map(s => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            stroke={s.color}
            strokeWidth={1.8}
            dot={false}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
