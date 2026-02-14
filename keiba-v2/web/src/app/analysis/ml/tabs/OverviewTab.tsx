'use client';

import { MetricCard } from '../utils';
import type { MlExperimentResultV2 } from '../types';

export default function OverviewTab({ data }: { data: MlExperimentResultV2 }) {
  const ma = data.models.accuracy.metrics;
  const mv = data.models.value.metrics;

  const hitAccuracy = Array.isArray(data.hit_analysis) ? data.hit_analysis : data.hit_analysis.accuracy;
  const hitValue = Array.isArray(data.hit_analysis) ? [] : data.hit_analysis.value;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-blue-200 p-4 dark:border-blue-800">
          <h3 className="mb-3 text-sm font-semibold text-blue-700 dark:text-blue-400">
            Model A（精度モデル）
          </h3>
          <div className="grid grid-cols-3 gap-2">
            <MetricCard label="AUC" value={ma.auc.toFixed(4)} highlight color="blue" />
            <MetricCard label="Accuracy" value={(ma.accuracy * 100).toFixed(1) + '%'} />
            <MetricCard label="Log Loss" value={ma.log_loss.toFixed(4)} />
          </div>
          <div className="mt-2 text-xs text-gray-500">
            特徴量 {data.models.accuracy.features.length}個（市場情報含む）
          </div>
        </div>

        <div className="rounded-lg border border-emerald-200 p-4 dark:border-emerald-800">
          <h3 className="mb-3 text-sm font-semibold text-emerald-700 dark:text-emerald-400">
            Model B（Valueモデル）
          </h3>
          <div className="grid grid-cols-3 gap-2">
            <MetricCard label="AUC" value={mv.auc.toFixed(4)} highlight color="green" />
            <MetricCard label="Accuracy" value={(mv.accuracy * 100).toFixed(1) + '%'} />
            <MetricCard label="Log Loss" value={mv.log_loss.toFixed(4)} />
          </div>
          <div className="mt-2 text-xs text-gray-500">
            特徴量 {data.models.value.features.length}個（市場系除外）
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">モデル情報</h3>
        <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <div><span className="text-gray-500">バージョン: </span><span className="font-medium">v{data.version}</span></div>
          <div><span className="text-gray-500">学習/テスト: </span><span className="font-medium">{data.split.train} / {data.split.test}</span></div>
          <div><span className="text-gray-500">学習件数: </span><span className="font-medium">{ma.train_size.toLocaleString()}</span></div>
          <div><span className="text-gray-500">テスト件数: </span><span className="font-medium">{ma.test_size.toLocaleString()}</span></div>
        </div>
      </div>

      {hitAccuracy.length > 0 && (
        <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
            Top-N予測の的中率
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="mb-2 text-xs font-medium text-blue-600 dark:text-blue-400">Model A（精度）</h4>
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
                <h4 className="mb-2 text-xs font-medium text-emerald-600 dark:text-emerald-400">Model B（Value）</h4>
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
