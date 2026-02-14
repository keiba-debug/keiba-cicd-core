'use client';

import { cn } from '@/lib/utils';
import type { MlExperimentResultV2 } from '../types';

export default function ValueTab({ data }: { data: MlExperimentResultV2 }) {
  const vb = data.roi_analysis.value_bets.by_rank_gap;
  const maxRoi = Math.max(...vb.map((v) => v.place_roi), 100);
  const hasWinData = vb.length > 0 && vb[0].win_roi != null;

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4 dark:border-emerald-800 dark:bg-emerald-950/20">
        <h3 className="mb-2 text-sm font-semibold text-emerald-800 dark:text-emerald-300">Value Bet戦略</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Model B（市場情報なし）がレース内上位3位に予測 × 実際の人気が低い馬を購入。
          モデルと市場の「乖離」が大きいほど、市場が見落としている可能性。
        </p>
      </div>

      <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">ランクギャップ別の回収率</h3>
        <p className="mb-3 text-xs text-gray-500">gap = 人気順 - Model Bランク。gapが大きい = 市場より高い評価</p>

        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-gray-500 dark:border-gray-700">
              <th className="py-2 text-left">条件</th>
              <th className="py-2 text-right">購入数</th>
              {hasWinData && <th className="py-2 text-right">単勝的中</th>}
              {hasWinData && <th className="py-2 text-right">単勝ROI</th>}
              <th className="py-2 text-right">複勝的中率</th>
              <th className="py-2 text-right">複勝ROI</th>
            </tr>
          </thead>
          <tbody>
            {vb.map((v) => (
              <tr key={v.min_gap} className="border-b border-gray-50 dark:border-gray-800">
                <td className="py-2 font-medium">gap {'≥'} {v.min_gap}</td>
                <td className="py-2 text-right tabular-nums">{v.bet_count.toLocaleString()}</td>
                {hasWinData && <td className="py-2 text-right tabular-nums">{v.win_hits}</td>}
                {hasWinData && (
                  <td className="py-2 text-right tabular-nums">
                    <span className={cn('font-medium', (v.win_roi ?? 0) >= 100 ? 'text-green-600 dark:text-green-400' : '')}>
                      {v.win_roi?.toFixed(1)}%
                    </span>
                  </td>
                )}
                <td className="py-2 text-right tabular-nums">{(v.place_hit_rate * 100).toFixed(1)}%</td>
                <td className="py-2 text-right tabular-nums">
                  <span className={cn('font-bold', v.place_roi >= 100 ? 'text-green-600 dark:text-green-400' : 'text-red-500')}>
                    {v.place_roi.toFixed(1)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-4">
          <h4 className="mb-2 text-xs font-medium text-gray-500">複勝回収率（赤線: 損益分岐100%）</h4>
          <div className="space-y-1">
            {vb.map((v) => {
              const pct = (v.place_roi / maxRoi) * 100;
              const breakeven = (100 / maxRoi) * 100;
              return (
                <div key={v.min_gap} className="flex items-center gap-2">
                  <span className="w-16 text-right text-xs tabular-nums text-gray-500">gap{'≥'}{v.min_gap}</span>
                  <div className="relative flex-1 h-6 rounded bg-gray-100 dark:bg-gray-700/50">
                    <div
                      className={cn('absolute inset-y-0 left-0 rounded',
                        v.place_roi >= 100 ? 'bg-emerald-400 dark:bg-emerald-600' : 'bg-amber-300 dark:bg-amber-600'
                      )}
                      style={{ width: `${Math.max(pct, 1)}%` }}
                    />
                    <div className="absolute inset-y-0 w-0.5 bg-red-500" style={{ left: `${breakeven}%` }} />
                    <span className="absolute inset-y-0 right-2 flex items-center text-xs tabular-nums font-medium text-gray-700 dark:text-gray-200">
                      {v.place_roi.toFixed(1)}%
                    </span>
                  </div>
                  <span className="w-14 text-right text-xs tabular-nums text-gray-400">{v.bet_count}件</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <h3 className="mb-2 text-sm font-semibold">Model A Top1 単勝ROI</h3>
          <div className="text-3xl font-bold tabular-nums">
            <span className={data.roi_analysis.accuracy_model.top1_win.roi >= 100 ? 'text-green-600' : 'text-red-500'}>
              {data.roi_analysis.accuracy_model.top1_win.roi.toFixed(1)}%
            </span>
          </div>
          <div className="text-xs text-gray-500">{data.roi_analysis.accuracy_model.top1_win.bet_count}R</div>
        </div>
        <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <h3 className="mb-2 text-sm font-semibold">Model B Top1 単勝ROI</h3>
          <div className="text-3xl font-bold tabular-nums">
            <span className={data.roi_analysis.value_model.top1_win.roi >= 100 ? 'text-green-600' : 'text-red-500'}>
              {data.roi_analysis.value_model.top1_win.roi.toFixed(1)}%
            </span>
          </div>
          <div className="text-xs text-gray-500">{data.roi_analysis.value_model.top1_win.bet_count}R</div>
        </div>
      </div>
    </div>
  );
}
