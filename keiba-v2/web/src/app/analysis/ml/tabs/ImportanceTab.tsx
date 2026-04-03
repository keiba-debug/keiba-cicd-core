'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { FEATURE_LABELS, FEATURE_CATEGORIES, getFeatureCategory } from '../utils';
import type { MlExperimentResultV2 } from '../types';

type ModelKey = 'place' | 'win' | 'aura';

const MODEL_OPTIONS: { key: ModelKey; label: string; shortLabel: string; color: string; activeColor: string }[] = [
  { key: 'place', label: '好走(P)', shortLabel: 'P', color: 'blue', activeColor: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  { key: 'win', label: '勝利(W)', shortLabel: 'W', color: 'emerald', activeColor: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' },
  { key: 'aura', label: '能力(AR)', shortLabel: 'AR', color: 'amber', activeColor: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
];

export default function ImportanceTab({ data }: { data: MlExperimentResultV2 }) {
  const [showModel, setShowModel] = useState<ModelKey>('place');

  const modelData = data.models[showModel as keyof typeof data.models];
  const fi = modelData?.feature_importance ?? [];
  const maxImportance = fi[0]?.importance ?? 1;

  const barColors: Record<string, { top: string; high: string; base: string }> = {
    place: { top: 'bg-blue-500', high: 'bg-blue-400', base: 'bg-blue-300 dark:bg-blue-600' },
    win: { top: 'bg-emerald-500', high: 'bg-emerald-400', base: 'bg-emerald-300 dark:bg-emerald-600' },
    aura: { top: 'bg-amber-500', high: 'bg-amber-400', base: 'bg-amber-300 dark:bg-amber-600' },
    obstacle_p: { top: 'bg-purple-500', high: 'bg-purple-400', base: 'bg-purple-300 dark:bg-purple-600' },
    obstacle_w: { top: 'bg-purple-500', high: 'bg-purple-400', base: 'bg-purple-300 dark:bg-purple-600' },
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
        LightGBMのgain（情報利得）ベースの特徴量重要度 — Top 20 / {fi.length}特徴量
      </p>
      <FeatureList features={fi.slice(0, 20)} maxImportance={maxImportance} barColors={currentBar} startRank={0} />
      {fi.length > 20 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">残り {fi.length - 20} 特徴量を表示</summary>
          <div className="mt-2">
            <FeatureList features={fi.slice(20)} maxImportance={maxImportance} barColors={currentBar} startRank={20} />
          </div>
        </details>
      )}
    </div>
  );
}

function FeatureList({ features, maxImportance, barColors, startRank }: {
  features: { feature: string; importance: number }[];
  maxImportance: number;
  barColors: { top: string; high: string; base: string };
  startRank: number;
}) {
  return (
    <div className="space-y-1.5">
      {features.map((f, idx) => {
        const i = startRank + idx;
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
                    i === 0 ? barColors.top : i < 3 ? barColors.high : barColors.base
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
  );
}
