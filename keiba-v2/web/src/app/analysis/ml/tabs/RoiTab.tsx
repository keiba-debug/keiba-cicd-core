'use client';

import { cn } from '@/lib/utils';
import type { MlExperimentResultV2, RoiAnalysis } from '../types';

function RoiBlock({ label, roi, color }: { label: string; roi: RoiAnalysis; color: string }) {
  return (
    <div className={cn('rounded-lg border p-4', color)}>
      <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">{label}</h3>
      <div className="grid grid-cols-2 gap-4 mb-2">
        <div className="space-y-1 text-sm">
          <div className="font-medium">Top1 → 単勝</div>
          <div className="flex justify-between"><span className="text-gray-500">投資</span><span className="tabular-nums">¥{roi.top1_win.total_bet.toLocaleString()}</span></div>
          <div className="flex justify-between"><span className="text-gray-500">回収</span><span className="tabular-nums">¥{roi.top1_win.total_return.toLocaleString()}</span></div>
          <div className="flex justify-between font-medium"><span>ROI</span>
            <span className={cn('tabular-nums', roi.top1_win.roi >= 100 ? 'text-green-600' : 'text-red-500')}>{roi.top1_win.roi.toFixed(1)}%</span>
          </div>
        </div>
        <div className="space-y-1 text-sm">
          <div className="font-medium">Top1 → 複勝</div>
          <div className="flex justify-between"><span className="text-gray-500">投資</span><span className="tabular-nums">¥{roi.top1_place.total_bet.toLocaleString()}</span></div>
          <div className="flex justify-between"><span className="text-gray-500">回収</span><span className="tabular-nums">¥{roi.top1_place.total_return.toLocaleString()}</span></div>
          <div className="flex justify-between font-medium"><span>ROI</span>
            <span className={cn('tabular-nums', roi.top1_place.roi >= 100 ? 'text-green-600' : 'text-red-500')}>{roi.top1_place.roi.toFixed(1)}%</span>
          </div>
        </div>
      </div>
      {roi.by_threshold.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">閾値別の詳細</summary>
          <table className="mt-2 w-full text-xs">
            <thead>
              <tr className="border-b text-gray-400">
                <th className="py-1 text-left">閾値</th>
                <th className="py-1 text-right">件数</th>
                <th className="py-1 text-right">単勝ROI</th>
                <th className="py-1 text-right">複勝ROI</th>
              </tr>
            </thead>
            <tbody>
              {roi.by_threshold.map((t) => (
                <tr key={t.threshold} className="border-b border-gray-50 dark:border-gray-800">
                  <td className="py-1 tabular-nums">{(t.threshold * 100).toFixed(0)}%+</td>
                  <td className="py-1 text-right tabular-nums">{t.bet_count}</td>
                  <td className="py-1 text-right tabular-nums">
                    <span className={t.win_roi >= 100 ? 'text-green-600 font-medium' : ''}>{t.win_roi.toFixed(1)}%</span>
                  </td>
                  <td className="py-1 text-right tabular-nums">
                    <span className={t.place_roi >= 100 ? 'text-green-600 font-medium' : ''}>{t.place_roi.toFixed(1)}%</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  );
}

export default function RoiTab({ data }: { data: MlExperimentResultV2 }) {
  const hasWin = !!data.roi_analysis.win_accuracy_model;

  const models: { label: string; roi: RoiAnalysis; color: string }[] = [
    { label: 'Model A (Place精度)', roi: data.roi_analysis.accuracy_model, color: 'border-blue-200 dark:border-blue-800' },
    { label: 'Model V (Place Value)', roi: data.roi_analysis.value_model, color: 'border-blue-200 dark:border-blue-800' },
  ];
  if (data.roi_analysis.win_accuracy_model) {
    models.push({ label: 'Model W (Win精度)', roi: data.roi_analysis.win_accuracy_model, color: 'border-emerald-200 dark:border-emerald-800' });
  }
  if (data.roi_analysis.win_value_model) {
    models.push({ label: 'Model WV (Win Value)', roi: data.roi_analysis.win_value_model, color: 'border-emerald-200 dark:border-emerald-800' });
  }

  return (
    <div className="space-y-6">
      {/* Summary comparison table */}
      {hasWin && (
        <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">4モデル比較サマリー</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-gray-500 dark:border-gray-700">
                <th className="py-2 text-left">モデル</th>
                <th className="py-2 text-right">単勝ROI</th>
                <th className="py-2 text-right">複勝ROI</th>
                <th className="py-2 text-right">件数</th>
              </tr>
            </thead>
            <tbody>
              {models.map(({ label, roi }) => (
                <tr key={label} className="border-b border-gray-50 dark:border-gray-800">
                  <td className="py-2 font-medium">{label}</td>
                  <td className="py-2 text-right tabular-nums">
                    <span className={cn('font-medium', roi.top1_win.roi >= 100 ? 'text-green-600' : 'text-red-500')}>
                      {roi.top1_win.roi.toFixed(1)}%
                    </span>
                  </td>
                  <td className="py-2 text-right tabular-nums">
                    <span className={cn('font-medium', roi.top1_place.roi >= 100 ? 'text-green-600' : 'text-red-500')}>
                      {roi.top1_place.roi.toFixed(1)}%
                    </span>
                  </td>
                  <td className="py-2 text-right tabular-nums text-gray-500">{roi.top1_win.bet_count}R</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail blocks */}
      {models.map(({ label, roi, color }) => (
        <RoiBlock key={label} label={label} roi={roi} color={color} />
      ))}
    </div>
  );
}
