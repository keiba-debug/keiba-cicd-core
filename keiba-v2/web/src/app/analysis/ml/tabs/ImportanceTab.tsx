'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { V2_FEATURES } from '../utils';
import type { MlExperimentResultV2 } from '../types';

export default function ImportanceTab({ data }: { data: MlExperimentResultV2 }) {
  const [showModel, setShowModel] = useState<'accuracy' | 'value'>('value');
  const fi = showModel === 'accuracy'
    ? data.models.accuracy.feature_importance
    : data.models.value.feature_importance;
  const maxImportance = fi[0]?.importance ?? 1;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {(['accuracy', 'value'] as const).map((m) => (
          <button key={m} onClick={() => setShowModel(m)}
            className={cn('rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              showModel === m
                ? m === 'accuracy' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                  : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
            )}>
            {m === 'accuracy' ? 'Model A（精度）' : 'Model B（Value）'}
          </button>
        ))}
      </div>
      <p className="text-sm text-gray-500">LightGBMのgain（情報利得）ベースの特徴量重要度</p>
      <div className="space-y-2">
        {fi.map((f, i) => {
          const pct = (f.importance / maxImportance) * 100;
          return (
            <div key={f.feature} className="flex items-center gap-3">
              <div className="w-6 text-right text-xs text-gray-400">{i + 1}</div>
              <div className="w-44 text-sm font-medium truncate flex items-center gap-1">
                {f.label || f.feature}
                {V2_FEATURES.has(f.feature) && (
                  <span className="rounded bg-amber-100 px-1 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">v2</span>
                )}
              </div>
              <div className="flex-1">
                <div className="relative h-6 rounded bg-gray-100 dark:bg-gray-700/50">
                  <div className={cn('absolute inset-y-0 left-0 rounded',
                    showModel === 'value'
                      ? i === 0 ? 'bg-emerald-500' : i < 3 ? 'bg-emerald-400' : 'bg-emerald-300 dark:bg-emerald-600'
                      : i === 0 ? 'bg-blue-500' : i < 3 ? 'bg-blue-400' : 'bg-blue-300 dark:bg-blue-600'
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
  );
}
