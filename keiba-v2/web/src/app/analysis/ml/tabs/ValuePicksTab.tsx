'use client';

import { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import type { ValueBetPick } from '../types';

export default function ValuePicksTab({ picks }: { picks: ValueBetPick[] }) {
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
