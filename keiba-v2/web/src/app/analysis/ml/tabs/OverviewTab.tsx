'use client';

import { cn } from '@/lib/utils';
import { MetricCard } from '../utils';
import type { MlExperimentResultV2, MlModelResult } from '../types';

function ModelCard({
  title,
  model,
  color,
  targetLabel,
}: {
  title: string;
  model: MlModelResult;
  color: 'blue' | 'emerald';
  targetLabel: string;
}) {
  const m = model.metrics;
  const borderColor = color === 'blue' ? 'border-blue-200 dark:border-blue-800' : 'border-emerald-200 dark:border-emerald-800';
  const titleColor = color === 'blue' ? 'text-blue-700 dark:text-blue-400' : 'text-emerald-700 dark:text-emerald-400';

  return (
    <div className={cn('rounded-lg border p-4', borderColor)}>
      <h3 className={cn('mb-3 text-sm font-semibold', titleColor)}>
        {title}
        <span className="ml-2 text-xs font-normal text-gray-400">{targetLabel}</span>
      </h3>
      <div className="grid grid-cols-3 gap-2">
        <MetricCard label="AUC" value={m.auc.toFixed(4)} highlight color={color === 'blue' ? 'blue' : 'emerald'} />
        <MetricCard label="Brier" value={m.brier_score != null ? m.brier_score.toFixed(4) : '-'} />
        <MetricCard label="ECE" value={m.ece != null ? m.ece.toFixed(4) : '-'} />
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-gray-500">
        <div>Iter: <span className="font-medium text-gray-700 dark:text-gray-300">{m.best_iteration}</span></div>
        <div>Accuracy: <span className="font-medium text-gray-700 dark:text-gray-300">{(m.accuracy * 100).toFixed(1)}%</span></div>
        <div>Features: <span className="font-medium text-gray-700 dark:text-gray-300">{model.features.length}</span></div>
      </div>
    </div>
  );
}

export default function OverviewTab({ data }: { data: MlExperimentResultV2 }) {
  const hitAccuracy = Array.isArray(data.hit_analysis) ? data.hit_analysis : data.hit_analysis.accuracy;
  const hitValue = Array.isArray(data.hit_analysis) ? [] : data.hit_analysis.value;
  const hasWin = !!data.models.win_accuracy;

  return (
    <div className="space-y-6">
      {/* Place Models */}
      <div>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">Place Models (3着内)</h2>
        <div className="grid grid-cols-2 gap-4">
          <ModelCard title="Model A" model={data.models.accuracy} color="blue" targetLabel="精度 / 全特徴量" />
          <ModelCard title="Model V" model={data.models.value} color="blue" targetLabel="Value / 市場系除外" />
        </div>
      </div>

      {/* Win Models */}
      {hasWin && (
        <div>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">Win Models (1着)</h2>
          <div className="grid grid-cols-2 gap-4">
            <ModelCard title="Model W" model={data.models.win_accuracy!} color="emerald" targetLabel="精度 / 全特徴量" />
            <ModelCard title="Model WV" model={data.models.win_value!} color="emerald" targetLabel="Value / 市場系除外" />
          </div>
        </div>
      )}

      {/* Model Info */}
      <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">モデル情報</h3>
        <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <div><span className="text-gray-500">バージョン: </span><span className="font-medium">v{data.version}</span></div>
          <div>
            <span className="text-gray-500">データ分割: </span>
            <span className="font-medium">
              {data.split.val
                ? `${data.split.train} / ${data.split.val} / ${data.split.test}`
                : `${data.split.train} / ${data.split.test}`
              }
            </span>
          </div>
          <div><span className="text-gray-500">学習件数: </span><span className="font-medium">{data.models.accuracy.metrics.train_size.toLocaleString()}</span></div>
          <div><span className="text-gray-500">テスト件数: </span><span className="font-medium">{data.models.accuracy.metrics.test_size.toLocaleString()}</span></div>
        </div>
        {data.split.val && (
          <div className="mt-1 text-xs text-gray-400">3-way split: Train / Val(early stopping) / Test(純粋評価)</div>
        )}
      </div>

      {/* Hit Analysis */}
      {hitAccuracy.length > 0 && (
        <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
            Top-N予測の的中率
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="mb-2 text-xs font-medium text-blue-600 dark:text-blue-400">Model A (Place精度)</h4>
              <div className="grid grid-cols-3 gap-3">
                {hitAccuracy.map((h) => (
                  <div key={h.top_n} className="rounded-lg bg-gray-50 p-3 text-center dark:bg-gray-800/50">
                    <div className="text-xs text-gray-500">Top {h.top_n}</div>
                    <div className="mt-1 text-xl font-bold text-blue-600 dark:text-blue-400">
                      {(h.hit_rate * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-400">{h.hits}/{h.total}R</div>
                  </div>
                ))}
              </div>
            </div>
            {hitValue.length > 0 && (
              <div>
                <h4 className="mb-2 text-xs font-medium text-blue-600 dark:text-blue-400">Model V (Place Value)</h4>
                <div className="grid grid-cols-3 gap-3">
                  {hitValue.map((h) => (
                    <div key={h.top_n} className="rounded-lg bg-gray-50 p-3 text-center dark:bg-gray-800/50">
                      <div className="text-xs text-gray-500">Top {h.top_n}</div>
                      <div className="mt-1 text-xl font-bold text-emerald-600 dark:text-emerald-400">
                        {(h.hit_rate * 100).toFixed(1)}%
                      </div>
                      <div className="text-xs text-gray-400">{h.hits}/{h.total}R</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
