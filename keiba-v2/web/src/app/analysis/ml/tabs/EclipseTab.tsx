'use client';

import { cn } from '@/lib/utils';
import { Sun } from 'lucide-react';
import { FEATURE_LABELS, FEATURE_CATEGORIES, getFeatureCategory } from '../utils';
import type { EclipseModelMeta } from '../types';

function Stat({ label, value, hint, strong }: { label: string; value: string; hint?: string; strong?: boolean }) {
  return (
    <div className={cn('rounded p-2 text-center', strong ? 'bg-orange-50 dark:bg-orange-950/30' : 'bg-gray-50 dark:bg-gray-800/50')}>
      <div className="text-xs text-gray-500">{label}</div>
      <div className={cn('font-bold tabular-nums', strong ? 'text-lg text-orange-600 dark:text-orange-400' : 'text-base')}>{value}</div>
      {hint && <div className="text-[10px] text-gray-400">{hint}</div>}
    </div>
  );
}

export default function EclipseTab({ meta }: { meta?: EclipseModelMeta | null }) {
  if (!meta || !meta.metrics) {
    return <div className="py-12 text-center text-gray-400">Eclipseモデルが読み込まれていません</div>;
  }

  const m = meta.metrics;
  const fi = meta.feature_importance ?? [];
  const maxImportance = fi[0]?.importance ?? 1;
  const thr = meta.threshold_analysis ?? [];
  const posRate = meta.test_positive_rate ?? meta.train_positive_rate;

  return (
    <div className="space-y-6">
      {/* レース単位モデル 説明バナー */}
      <div className="flex items-start gap-3 rounded-lg border border-orange-200 bg-orange-50 p-3 dark:border-orange-800 dark:bg-orange-950/20">
        <Sun className="mt-0.5 h-5 w-5 shrink-0 text-orange-500" />
        <div className="text-xs text-orange-800 dark:text-orange-300">
          <span className="font-semibold">レース単位モデル（Nebula系）。</span>{' '}
          {meta.description ?? '差し/追込馬が3着内に2頭以上入る「差し決着優勢」レースを事前判定する。'}
          {' '}馬単位の勝率ではなく<strong>レースの決着傾向</strong>を出力（正例率 {posRate != null ? `${(posRate * 100).toFixed(1)}%` : '—'} の不均衡分類）。
        </div>
      </div>

      {/* メトリクス */}
      <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-6">
          <Stat label="AUC" value={m.auc.toFixed(4)} strong />
          <Stat label="PR-AUC" value={meta.pr_auc != null ? meta.pr_auc.toFixed(4) : '—'} hint={posRate != null ? `base ${(posRate * 100).toFixed(0)}%` : undefined} strong />
          <Stat label="ECE(cal)" value={m.ece_calibrated.toFixed(4)} />
          <Stat label="Brier(cal)" value={m.brier_calibrated.toFixed(4)} />
          <Stat label="Val AUC" value={m.auc_val.toFixed(4)} />
          <Stat label="best_iter" value={String(m.best_iteration)} />
        </div>
        <div className="mt-2 flex justify-between text-[11px] text-gray-400">
          <span>{meta.feature_count} features</span>
          <span>train {m.train_size.toLocaleString()} / val {m.val_size.toLocaleString()} / test {m.test_size.toLocaleString()} レース</span>
        </div>
      </div>

      {/* Train/Test 期間 */}
      <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
        <div className="grid grid-cols-3 gap-2 text-xs text-gray-500">
          <div>Train: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.train_period}</span></div>
          <div>Val: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.val_period}</span></div>
          <div>Test: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.test_period}</span></div>
        </div>
      </div>

      {/* 閾値別 precision/recall — 運用の核 */}
      {thr.length > 0 && (
        <div>
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">閾値別 精度/再現率</h3>
            <span className="text-[11px] text-gray-400">「差し決着」と判定する確率しきい値の運用トレードオフ</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs text-gray-500 dark:border-gray-700">
                  <th className="px-2 py-1.5 text-left">閾値</th>
                  <th className="px-2 py-1.5 text-right">適合率</th>
                  <th className="px-2 py-1.5 text-right">再現率</th>
                  <th className="px-2 py-1.5 text-right">F1</th>
                  <th className="px-2 py-1.5 text-right">判定数</th>
                  <th className="px-2 py-1.5 text-right">的中数</th>
                  <th className="px-2 py-1.5 text-left">適合率バー</th>
                </tr>
              </thead>
              <tbody>
                {thr.map((t, i) => {
                  const lift = posRate ? t.precision / posRate : null;
                  return (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                      <td className="px-2 py-1.5 font-medium tabular-nums">{t.threshold.toFixed(2)}</td>
                      <td className="px-2 py-1.5 text-right font-semibold tabular-nums text-orange-600 dark:text-orange-400">
                        {(t.precision * 100).toFixed(1)}%
                        {lift ? <span className="ml-1 text-[10px] font-normal text-gray-400">×{lift.toFixed(1)}</span> : ''}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{(t.recall * 100).toFixed(1)}%</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{(t.f1 * 100).toFixed(1)}%</td>
                      <td className="px-2 py-1.5 text-right tabular-nums text-gray-500">{t.n_predicted}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums text-gray-500">{t.n_correct}</td>
                      <td className="px-2 py-1.5">
                        <div className="relative h-3 w-24 rounded bg-gray-100 dark:bg-gray-700/50">
                          <div className="absolute inset-y-0 left-0 rounded bg-orange-400"
                            style={{ width: `${Math.min(t.precision * 100 * 2, 100)}%` }} />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-1.5 text-[11px] text-gray-400">
            ×N = ベース正例率に対するリフト（適合率 ÷ {posRate != null ? `${(posRate * 100).toFixed(0)}%` : 'ベース'}）。閾値を上げるほど適合率↑・再現率↓。
          </p>
        </div>
      )}

      {/* 特徴量重要度 */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">特徴量重要度 (gain, 上位20)</h3>
        <div className="space-y-1.5">
          {fi.slice(0, 20).map((f, i) => {
            const pct = (f.importance / maxImportance) * 100;
            const jaLabel = FEATURE_LABELS[f.feature];
            const category = getFeatureCategory(f.feature);
            const catInfo = category ? FEATURE_CATEGORIES[category] : null;
            return (
              <div key={f.feature} className="flex items-center gap-2">
                <div className="w-6 text-right text-xs text-gray-400 tabular-nums">{i + 1}</div>
                <div className="w-56 truncate text-sm flex items-center gap-1" title={jaLabel ? `${jaLabel} (${f.feature})` : f.feature}>
                  <span className="font-medium">{jaLabel || f.feature}</span>
                  {catInfo && (
                    <span className={cn('rounded px-1 py-0.5 text-[9px] font-medium', catInfo.color)}>{catInfo.label}</span>
                  )}
                </div>
                <div className="flex-1">
                  <div className="relative h-5 rounded bg-gray-100 dark:bg-gray-700/50">
                    <div className={cn('absolute inset-y-0 left-0 rounded',
                      i === 0 ? 'bg-orange-500' : i < 3 ? 'bg-orange-400' : 'bg-orange-300 dark:bg-orange-600'
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
