'use client';

import { useMemo, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import type { HorseRaceResult } from '@/lib/data/integrated-horse-reader';

// ── 年齢計算 ──

function calcAgeMonths(birthDate: string, raceDate: string): number {
  // birthDate: YYYYMMDD, raceDate: YYYY/MM/DD or YYYY-MM-DD
  // 日単位の精度で同月内の複数レースを区別
  const by = parseInt(birthDate.slice(0, 4), 10);
  const bm = parseInt(birthDate.slice(4, 6), 10);
  const bd = parseInt(birthDate.slice(6, 8), 10);
  const clean = raceDate.replace(/[/-]/g, '');
  const ry = parseInt(clean.slice(0, 4), 10);
  const rm = parseInt(clean.slice(4, 6), 10);
  const rd = parseInt(clean.slice(6, 8), 10);
  return (ry - by) * 12 + (rm - bm) + (rd - bd) / 31;
}

function formatAge(months: number): string {
  const whole = Math.floor(months);
  const years = Math.floor(whole / 12);
  const m = whole % 12;
  return `${years}歳${m}月`;
}

// ── チャートデータ型 ──

interface ChartPoint {
  ageMonths: number;
  ageLabel: string;
  idm: number | null;
  preIdm: number | null;
  date: string;
  track: string;
  raceName: string;
  finishPosition: string;
  isMax: boolean;
}

// ── ツールチップ ──

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartPoint }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-white dark:bg-gray-800 border rounded-lg shadow-lg px-3 py-2 text-xs">
      <div className="font-semibold mb-1">{d.ageLabel} ({d.date})</div>
      <div className="text-muted-foreground mb-1">{d.track} {d.raceName}</div>
      <div className="flex gap-3">
        {d.idm != null && (
          <span>IDM: <span className="font-bold text-blue-600 dark:text-blue-400">{d.idm}</span></span>
        )}
        {d.preIdm != null && (
          <span className="text-muted-foreground">予想: {d.preIdm}</span>
        )}
        <span>着: <span className="font-medium">{d.finishPosition}</span></span>
      </div>
      {d.isMax && <div className="text-red-500 font-medium mt-0.5">★ 最高IDM</div>}
    </div>
  );
}

// ── カスタムドット（最高IDMをハイライト） ──

function MaxDot(props: { cx?: number; cy?: number; payload?: ChartPoint }) {
  const { cx, cy, payload } = props;
  if (!payload?.isMax || cx == null || cy == null) return null;
  return (
    <svg x={cx - 8} y={cy - 8} width={16} height={16}>
      <polygon
        points="8,0 10,6 16,6 11,10 13,16 8,12 3,16 5,10 0,6 6,6"
        fill="#ef4444"
        stroke="#fff"
        strokeWidth={0.5}
      />
    </svg>
  );
}

// ── レンジ設定 ──

type AgeRange = '2-3' | '2-6' | '2-10';

const RANGE_CONFIG: Record<AgeRange, { minYear: number; maxYear: number; label: string }> = {
  '2-3':  { minYear: 2,  maxYear: 4,  label: '2~3歳' },
  '2-6':  { minYear: 2,  maxYear: 7,  label: '2~6歳' },
  '2-10': { minYear: 2,  maxYear: 10, label: '2~10歳' },
};

// ── メインコンポーネント ──

interface IDMTimelineChartProps {
  pastRaces: HorseRaceResult[];
  birthDate?: string;
  horseName?: string;
}

export function IDMTimelineChart({ pastRaces, birthDate, horseName }: IDMTimelineChartProps) {
  const [range, setRange] = useState<AgeRange>('2-6');

  const chartData = useMemo(() => {
    if (!birthDate || birthDate.length < 8) return [];

    const points: ChartPoint[] = [];
    let maxIdm = 0;

    // 古い順に並べる
    const sorted = pastRaces.slice().reverse();
    for (const r of sorted) {
      const idm = r.jrdb_idm && r.jrdb_idm !== 0 ? r.jrdb_idm : null;
      const preIdm = r.jrdb_pre_idm && r.jrdb_pre_idm !== 0 ? r.jrdb_pre_idm : null;
      if (idm == null && preIdm == null) continue;

      const ageMonths = calcAgeMonths(birthDate, r.date);
      if (idm != null && idm > maxIdm) maxIdm = idm;

      points.push({
        ageMonths,
        ageLabel: formatAge(ageMonths),
        idm,
        preIdm,
        date: r.date,
        track: r.track,
        raceName: r.raceName || `${r.raceNumber}R`,
        finishPosition: r.finishPosition,
        isMax: false,
      });
    }

    // 最高IDMマーク
    if (maxIdm > 0) {
      for (const p of points) {
        if (p.idm === maxIdm) {
          p.isMax = true;
          break; // 最新の最高値のみ（reverseで古い順なので最初のhit）
        }
      }
    }

    return points;
  }, [pastRaces, birthDate]);

  if (chartData.length < 2) return null;

  // X軸: レンジに応じた固定スケール
  const { minYear, maxYear } = RANGE_CONFIG[range];
  const MIN_AGE = minYear * 12;
  const MAX_AGE = maxYear * 12;

  // X軸ティック: 年境界
  const ticks: number[] = [];
  for (let y = minYear; y < maxYear; y++) {
    ticks.push(y * 12);
  }

  // 最高IDM
  const maxIdm = Math.max(...chartData.filter(d => d.idm != null).map(d => d.idm!), 0);

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">📈 IDM推移</h2>
          <div className="flex items-center rounded-md border text-xs">
            {(Object.entries(RANGE_CONFIG) as [AgeRange, typeof RANGE_CONFIG[AgeRange]][]).map(([key, cfg]) => (
              <button
                key={key}
                onClick={() => setRange(key)}
                className={`px-2 py-1 transition-colors ${
                  range === key
                    ? 'bg-blue-500 text-white'
                    : 'hover:bg-muted'
                } ${key === '2-3' ? 'rounded-l-md' : ''} ${key === '2-10' ? 'rounded-r-md' : ''}`}
              >
                {cfg.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-blue-500 inline-block" /> IDM
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-gray-400 inline-block border-dashed" style={{ borderTop: '1px dashed' }} /> 予想IDM
          </span>
          {maxIdm > 0 && (
            <span className="flex items-center gap-1">
              <span className="text-red-500">★</span> 最高 {maxIdm}
            </span>
          )}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={360}>
        <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 5, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis
            dataKey="ageMonths"
            type="number"
            domain={[MIN_AGE, MAX_AGE]}
            ticks={ticks}
            tickFormatter={(v: number) => `${Math.floor(v / 12)}歳`}
            tick={{ fontSize: 11 }}
          />
          <YAxis
            domain={[30, 80]}
            ticks={[30, 40, 50, 60, 70, 80]}
            tick={{ fontSize: 11 }}
            width={30}
          />
          <ReferenceLine y={50} stroke="#94a3b8" strokeDasharray="4 4" opacity={0.6} />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="preIdm"
            stroke="#9ca3af"
            strokeDasharray="4 4"
            strokeWidth={1}
            dot={{ r: 2, fill: '#9ca3af' }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="idm"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3, fill: '#3b82f6', stroke: '#fff', strokeWidth: 1 }}
            activeDot={{ r: 5 }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="idm"
            stroke="none"
            dot={<MaxDot />}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
