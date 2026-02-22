'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { FEATURE_LABELS, FEATURE_CATEGORIES, getFeatureCategory } from '../utils';
import type { MlExperimentResultV2 } from '../types';

type ModelKey = 'accuracy' | 'value' | 'win_accuracy' | 'win_value';

const MODEL_OPTIONS: { key: ModelKey; label: string; shortLabel: string; color: string; activeColor: string }[] = [
  { key: 'accuracy', label: '好走 市場', shortLabel: 'A', color: 'blue', activeColor: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  { key: 'value', label: '好走 独自', shortLabel: 'V', color: 'emerald', activeColor: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' },
  { key: 'win_accuracy', label: '勝利 市場', shortLabel: 'W', color: 'green', activeColor: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  { key: 'win_value', label: '勝利 独自', shortLabel: 'WV', color: 'teal', activeColor: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400' },
];

export default function ImportanceTab({ data }: { data: MlExperimentResultV2 }) {
  const [showModel, setShowModel] = useState<ModelKey>('value');

  const modelData = data.models[showModel as keyof typeof data.models];
  const fi = modelData?.feature_importance ?? [];
  const maxImportance = fi[0]?.importance ?? 1;

  const barColors = {
    accuracy: { top: 'bg-blue-500', high: 'bg-blue-400', base: 'bg-blue-300 dark:bg-blue-600' },
    value: { top: 'bg-emerald-500', high: 'bg-emerald-400', base: 'bg-emerald-300 dark:bg-emerald-600' },
    win_accuracy: { top: 'bg-green-500', high: 'bg-green-400', base: 'bg-green-300 dark:bg-green-600' },
    win_value: { top: 'bg-teal-500', high: 'bg-teal-400', base: 'bg-teal-300 dark:bg-teal-600' },
  };
  const currentBar = barColors[showModel];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {MODEL_OPTIONS.map((opt) => {
          const modelExists = !!data.models[opt.key as keyof typeof data.models];
          return (
            <button key={opt.key} onClick={() => modelExists && setShowModel(opt.key)}
              disabled={!modelExists}
              className={cn('rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                !modelExists && 'opacity-30 cursor-not-allowed',
                showModel === opt.key
                  ? opt.activeColor
                  : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
              )}>
              {opt.label}
            </button>
          );
        })}
      </div>
      <p className="text-sm text-gray-500">
        LightGBMのgain（情報利得）ベースの特徴量重要度 — {fi.length}特徴量
      </p>
      <div className="space-y-1.5">
        {fi.map((f, i) => {
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
                  <span className={cn('rounded px-1 py-0.5 text-[9px] font-medium', catInfo.color)}>
                    {catInfo.label}
                  </span>
                )}
              </div>
              <div className="flex-1">
                <div className="relative h-5 rounded bg-gray-100 dark:bg-gray-700/50">
                  <div className={cn('absolute inset-y-0 left-0 rounded',
                    i === 0 ? currentBar.top : i < 3 ? currentBar.high : currentBar.base
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
