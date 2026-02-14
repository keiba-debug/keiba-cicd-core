'use client';

import { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import type { RacePredictionV2 } from '../types';

export default function PredictionsTab({ predictions }: { predictions: RacePredictionV2[] }) {
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
