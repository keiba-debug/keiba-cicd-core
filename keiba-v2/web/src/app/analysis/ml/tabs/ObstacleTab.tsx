'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { FEATURE_LABELS, FEATURE_CATEGORIES, getFeatureCategory } from '../utils';
import type { ObstacleModelMeta } from '../types';

export default function ObstacleTab({ obstacleModel }: { obstacleModel?: ObstacleModelMeta | null }) {
  const [showModel, setShowModel] = useState<'p' | 'w'>('p');

  if (!obstacleModel) {
    return (
      <div className="py-12 text-center text-gray-400">
        障害モデルが読み込まれていません
      </div>
    );
  }

  const meta = obstacleModel;
  const mp = meta.metrics_p;
  const mw = meta.metrics_w;

  const fi = showModel === 'p'
    ? (meta.feature_importance_p ?? [])
    : (meta.feature_importance_w ?? []);
  const maxImportance = fi[0]?.importance ?? 1;
  const barColor = showModel === 'p'
    ? { top: 'bg-purple-500', high: 'bg-purple-400', base: 'bg-purple-300 dark:bg-purple-600' }
    : { top: 'bg-emerald-500', high: 'bg-emerald-400', base: 'bg-emerald-300 dark:bg-emerald-600' };

  return (
    <div className="space-y-6">
      {/* Model metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border border-purple-200 p-4 dark:border-purple-800">
          <h3 className="mb-3 text-sm font-semibold text-purple-600 dark:text-purple-400">障害 好走(P)</h3>
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div className="rounded bg-purple-50 p-2 text-center dark:bg-purple-950/30">
              <div className="text-xs text-gray-500">AUC</div>
              <div className="text-lg font-bold text-purple-600 dark:text-purple-400">{mp.auc.toFixed(4)}</div>
            </div>
            <div className="rounded bg-gray-50 p-2 text-center dark:bg-gray-800/50">
              <div className="text-xs text-gray-500">Brier</div>
              <div className="font-medium">{mp.brier_calibrated.toFixed(4)}</div>
            </div>
            <div className="rounded bg-gray-50 p-2 text-center dark:bg-gray-800/50">
              <div className="text-xs text-gray-500">ECE</div>
              <div className="font-medium">{mp.ece_calibrated.toFixed(4)}</div>
            </div>
          </div>
          {meta.hit_analysis_p && (
            <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
              <div className="text-center">
                <div className="text-gray-500">Top1勝率</div>
                <div className="font-bold text-purple-600">{((meta.hit_analysis_p.top1_win_rate ?? 0) * 100).toFixed(1)}%</div>
              </div>
              <div className="text-center">
                <div className="text-gray-500">Top1好走率</div>
                <div className="font-bold text-purple-600">{((meta.hit_analysis_p.top1_place_rate ?? 0) * 100).toFixed(1)}%</div>
              </div>
              <div className="text-center">
                <div className="text-gray-500">Iter</div>
                <div className="font-medium">{mp.best_iteration}</div>
              </div>
            </div>
          )}
        </div>

        <div className="rounded-lg border border-emerald-200 p-4 dark:border-emerald-800">
          <h3 className="mb-3 text-sm font-semibold text-emerald-600 dark:text-emerald-400">障害 勝利(W)</h3>
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div className="rounded bg-emerald-50 p-2 text-center dark:bg-emerald-950/30">
              <div className="text-xs text-gray-500">AUC</div>
              <div className="text-lg font-bold text-emerald-600 dark:text-emerald-400">{mw.auc.toFixed(4)}</div>
            </div>
            <div className="rounded bg-gray-50 p-2 text-center dark:bg-gray-800/50">
              <div className="text-xs text-gray-500">Brier</div>
              <div className="font-medium">{mw.brier_calibrated.toFixed(4)}</div>
            </div>
            <div className="rounded bg-gray-50 p-2 text-center dark:bg-gray-800/50">
              <div className="text-xs text-gray-500">ECE</div>
              <div className="font-medium">{mw.ece_calibrated.toFixed(4)}</div>
            </div>
          </div>
          {meta.hit_analysis_w && (
            <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
              <div className="text-center">
                <div className="text-gray-500">Top1勝率</div>
                <div className="font-bold text-emerald-600">{((meta.hit_analysis_w.top1_win_rate ?? 0) * 100).toFixed(1)}%</div>
              </div>
              <div className="text-center">
                <div className="text-gray-500">Top1好走率</div>
                <div className="font-bold text-emerald-600">{((meta.hit_analysis_w.top1_place_rate ?? 0) * 100).toFixed(1)}%</div>
              </div>
              <div className="text-center">
                <div className="text-gray-500">Iter</div>
                <div className="font-medium">{mw.best_iteration}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Train/Val/Test period */}
      <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
        <div className="grid grid-cols-3 gap-2 text-xs text-gray-500">
          <div>Train: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.train_period} ({meta.train_races}R)</span></div>
          <div>Val: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.val_period} ({meta.val_races}R)</span></div>
          <div>Test: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.test_period} ({meta.test_races}R)</span></div>
        </div>
      </div>

      {/* Feature importance */}
      <div>
        <div className="mb-3 flex items-center gap-3">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">特徴量重要度</h3>
          <div className="flex gap-1">
            <button onClick={() => setShowModel('p')}
              className={cn('rounded-md px-3 py-1 text-xs font-medium',
                showModel === 'p' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' : 'bg-gray-100 text-gray-500 dark:bg-gray-800'
              )}>障害(P)</button>
            <button onClick={() => setShowModel('w')}
              className={cn('rounded-md px-3 py-1 text-xs font-medium',
                showModel === 'w' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-gray-100 text-gray-500 dark:bg-gray-800'
              )}>障害(W)</button>
          </div>
        </div>
        <div className="space-y-1.5">
          {fi.slice(0, 20).map((f, i) => {
            const pct = (f.importance / maxImportance) * 100;
            const jaLabel = FEATURE_LABELS[f.feature];
            const category = getFeatureCategory(f.feature);
            const catInfo = category ? FEATURE_CATEGORIES[category] : null;
            return (
              <div key={f.feature} className="flex items-center gap-2">
                <div className="w-6 text-right text-xs text-gray-400 tabular-nums">{i + 1}</div>
                <div className="w-52 text-sm truncate flex items-center gap-1" title={jaLabel ? `${jaLabel} (${f.feature})` : f.feature}>
                  <span className="font-medium">{jaLabel || f.feature}</span>
                  {catInfo && (
                    <span className={cn('rounded px-1 py-0.5 text-[9px] font-medium', catInfo.color)}>{catInfo.label}</span>
                  )}
                </div>
                <div className="flex-1">
                  <div className="relative h-5 rounded bg-gray-100 dark:bg-gray-700/50">
                    <div className={cn('absolute inset-y-0 left-0 rounded',
                      i === 0 ? barColor.top : i < 3 ? barColor.high : barColor.base
                    )} style={{ width: `${Math.max(pct, 1)}%` }} />
                    <span className="absolute inset-y-0 right-2 flex items-center text-xs tabular-nums text-gray-600 dark:text-gray-300">
                      {f.importance.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
