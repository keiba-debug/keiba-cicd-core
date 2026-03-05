'use client';

import { cn } from '@/lib/utils';
import type { MlExperimentResultV2, ValueBetGapEntry, GapMarginGridEntry, GapArdGridEntry, IntersectionGridEntry } from '../types';

function GapTable({ title, vb, color }: { title: string; vb: ValueBetGapEntry[]; color: 'blue' | 'emerald' }) {
  if (!vb || vb.length === 0) return null;
  const hasWinData = vb[0].win_roi != null;
  return (
    <div>
      <h4 className={cn('mb-2 text-xs font-semibold',
        color === 'blue' ? 'text-blue-600 dark:text-blue-400' : 'text-emerald-600 dark:text-emerald-400'
      )}>{title}</h4>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-gray-500 dark:border-gray-700">
            <th className="py-2 text-left">条件</th>
            <th className="py-2 text-right">件数</th>
            {hasWinData && <th className="py-2 text-right">単勝的中</th>}
            {hasWinData && <th className="py-2 text-right">単勝ROI</th>}
            <th className="py-2 text-right">複勝的中率</th>
            <th className="py-2 text-right">複勝ROI</th>
          </tr>
        </thead>
        <tbody>
          {vb.map((v) => (
            <tr key={v.min_gap} className="border-b border-gray-50 dark:border-gray-800">
              <td className="py-2 font-medium">gap {'\u2265'} {v.min_gap}</td>
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
    </div>
  );
}

function RoiBarChart({ placeVb, winVb }: { placeVb: ValueBetGapEntry[]; winVb?: ValueBetGapEntry[] }) {
  const allRois = [
    ...placeVb.map((v) => v.place_roi),
    ...(winVb ?? []).map((v) => v.place_roi),
  ];
  const maxRoi = Math.max(...allRois, 100);

  return (
    <div className="mt-4">
      <h4 className="mb-2 text-xs font-medium text-gray-500">ROI比較（赤線: 損益分岐100%）</h4>
      <div className="space-y-1.5">
        {placeVb.map((v, i) => {
          const placePct = (v.place_roi / maxRoi) * 100;
          const winEntry = winVb?.[i];
          const winPct = winEntry ? (winEntry.place_roi / maxRoi) * 100 : 0;
          const breakeven = (100 / maxRoi) * 100;
          return (
            <div key={v.min_gap}>
              <div className="flex items-center gap-2">
                <span className="w-16 text-right text-xs tabular-nums text-gray-500">gap{'\u2265'}{v.min_gap}</span>
                <div className="relative flex-1 h-5 rounded bg-gray-100 dark:bg-gray-700/50">
                  <div
                    className={cn('absolute inset-y-0 left-0 rounded',
                      v.place_roi >= 100 ? 'bg-blue-400 dark:bg-blue-600' : 'bg-blue-200 dark:bg-blue-800'
                    )}
                    style={{ width: `${Math.max(placePct, 1)}%` }}
                  />
                  <div className="absolute inset-y-0 w-0.5 bg-red-500" style={{ left: `${breakeven}%` }} />
                  <span className="absolute inset-y-0 right-2 flex items-center text-xs tabular-nums font-medium text-gray-700 dark:text-gray-200">
                    {v.place_roi.toFixed(1)}%
                  </span>
                </div>
                <span className="w-10 text-[10px] text-blue-600 dark:text-blue-400">Place</span>
              </div>
              {winEntry && (
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="w-16" />
                  <div className="relative flex-1 h-5 rounded bg-gray-100 dark:bg-gray-700/50">
                    <div
                      className={cn('absolute inset-y-0 left-0 rounded',
                        winEntry.place_roi >= 100 ? 'bg-emerald-400 dark:bg-emerald-600' : 'bg-emerald-200 dark:bg-emerald-800'
                      )}
                      style={{ width: `${Math.max(winPct, 1)}%` }}
                    />
                    <div className="absolute inset-y-0 w-0.5 bg-red-500" style={{ left: `${breakeven}%` }} />
                    <span className="absolute inset-y-0 right-2 flex items-center text-xs tabular-nums font-medium text-gray-700 dark:text-gray-200">
                      {winEntry.place_roi.toFixed(1)}%
                    </span>
                  </div>
                  <span className="w-10 text-[10px] text-emerald-600 dark:text-emerald-400">Win</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GapMarginHeatmap({ grid }: { grid: GapMarginGridEntry[] }) {
  if (!grid || grid.length === 0) return null;

  // Build lookup: `${min_gap}-${max_margin}` → entry
  const lookup = new Map<string, GapMarginGridEntry>();
  for (const e of grid) {
    lookup.set(`${e.min_gap}-${e.max_margin}`, e);
  }

  const gaps = [3, 4, 5, 6];
  const margins = [0.6, 0.8, 1.0, 1.2, 1.5, null];
  const marginLabels = ['≤0.6', '≤0.8', '≤1.0', '≤1.2', '≤1.5', '制限なし'];

  // Current preset: gap≥5, margin制限なし（AR偏差値に移行済み）
  const presetGap = 5;

  return (
    <div className="mt-6 rounded-lg border border-gray-200 p-4 dark:border-gray-700">
      <h3 className="mb-1 text-sm font-semibold text-gray-700 dark:text-gray-300">Gap × AR(raw) ヒートマップ (単勝ROI)</h3>
      <p className="mb-3 text-xs text-gray-500">gap閾値とAR(勝ち馬タイム差)閾値の組み合わせ別ROI。枠線=現在gap閾値(5)。※現在のプリセットはAR偏差値で足切り</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <th className="py-2 text-left text-gray-500">gap \ AR</th>
              {marginLabels.map((label, i) => (
                <th key={i} className="py-2 text-center text-gray-500">{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {gaps.map((gap) => (
              <tr key={gap} className="border-b border-gray-50 dark:border-gray-800">
                <td className="py-2 font-medium text-gray-600 dark:text-gray-400">≥{gap}</td>
                {margins.map((margin, mi) => {
                  const entry = lookup.get(`${gap}-${margin}`);
                  const roi = entry?.win_roi ?? 0;
                  const count = entry?.count ?? 0;
                  const isPreset = gap === presetGap && margin === null;

                  let bgClass = 'bg-gray-50 dark:bg-gray-800/30';
                  if (count > 0) {
                    if (roi >= 120) bgClass = 'bg-green-200 dark:bg-green-900/40';
                    else if (roi >= 100) bgClass = 'bg-green-100 dark:bg-green-900/20';
                    else if (roi >= 80) bgClass = 'bg-yellow-50 dark:bg-yellow-900/10';
                    else bgClass = 'bg-red-50 dark:bg-red-900/10';
                  }

                  return (
                    <td key={mi} className={cn('py-2 text-center', bgClass,
                      isPreset && 'ring-2 ring-amber-500 ring-inset rounded'
                    )}>
                      {count > 0 ? (
                        <div>
                          <div className={cn('font-bold tabular-nums',
                            roi >= 100 ? 'text-green-700 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                          )}>
                            {roi.toFixed(1)}%
                          </div>
                          <div className="text-[10px] text-gray-400">{count}件/{entry!.win_hits}的中</div>
                        </div>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GapArdHeatmap({ grid, metric }: { grid: GapArdGridEntry[]; metric: 'win' | 'place' }) {
  if (!grid || grid.length === 0) return null;

  const lookup = new Map<string, GapArdGridEntry>();
  for (const e of grid) {
    lookup.set(`${e.min_gap}-${e.min_ard}`, e);
  }

  const gaps = [3, 4, 5, 6];
  const ards = [null, 45, 50, 55, 60, 65];
  const ardLabels = ['制限なし', '≥45', '≥50', '≥55', '≥60', '≥65'];

  // 現在のプリセット: gap≥5, ARd≥50
  const presetGap = 5;
  const presetArd = 50;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700">
            <th className="py-2 text-left text-gray-500">gap \ ARd</th>
            {ardLabels.map((label, i) => (
              <th key={i} className="py-2 text-center text-gray-500">{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {gaps.map((gap) => (
            <tr key={gap} className="border-b border-gray-50 dark:border-gray-800">
              <td className="py-2 font-medium text-gray-600 dark:text-gray-400">≥{gap}</td>
              {ards.map((ard, ai) => {
                const entry = lookup.get(`${gap}-${ard}`);
                const roi = metric === 'win' ? (entry?.win_roi ?? 0) : (entry?.place_roi ?? 0);
                const hits = metric === 'win' ? (entry?.win_hits ?? 0) : (entry?.place_hits ?? 0);
                const count = entry?.count ?? 0;
                const isPreset = gap === presetGap && ard === presetArd;

                let bgClass = 'bg-gray-50 dark:bg-gray-800/30';
                if (count > 0) {
                  if (roi >= 120) bgClass = 'bg-green-200 dark:bg-green-900/40';
                  else if (roi >= 100) bgClass = 'bg-green-100 dark:bg-green-900/20';
                  else if (roi >= 80) bgClass = 'bg-yellow-50 dark:bg-yellow-900/10';
                  else bgClass = 'bg-red-50 dark:bg-red-900/10';
                }

                return (
                  <td key={ai} className={cn('py-2 text-center', bgClass,
                    isPreset && 'ring-2 ring-amber-500 ring-inset rounded'
                  )}>
                    {count > 0 ? (
                      <div>
                        <div className={cn('font-bold tabular-nums',
                          roi >= 100 ? 'text-green-700 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                        )}>
                          {roi.toFixed(1)}%
                        </div>
                        <div className="text-[10px] text-gray-400">{count}件/{hits}的中</div>
                      </div>
                    ) : (
                      <span className="text-gray-300">-</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IntersectionHeatmap({ grid }: { grid: IntersectionGridEntry[] }) {
  if (!grid || grid.length === 0) return null;

  // Build lookup: `${gap}-${ev}-${margin}` → entry
  const lookup = new Map<string, IntersectionGridEntry>();
  for (const e of grid) {
    lookup.set(`${e.min_gap}-${e.min_ev}-${e.max_margin}`, e);
  }

  const gaps = [3, 4, 5, 6];
  const evs = [1.0, 1.3, 1.5, 2.0];
  const evLabels = ['≥1.0', '≥1.3', '≥1.5', '≥2.0'];

  // Show margin=60 as the main view (Intersection Filter condition)
  const margin = 60;

  // Preset highlight: gap≥4, EV≥1.3 (Intersection Filter)
  const presetGap = 4;
  const presetEv = 1.3;

  return (
    <div className="rounded-lg border border-blue-200 p-4 dark:border-blue-800">
      <h3 className="mb-1 text-sm font-semibold text-blue-700 dark:text-blue-400">
        Intersection Filter: Gap × EV × Margin ヒートマップ
      </h3>
      <p className="mb-3 text-xs text-gray-500">
        rank_w=1 対象。3条件の交差(C)が単独(A/B)より高ROI。枠線=推奨(gap≥4, EV≥1.3, m≤60)
      </p>

      {/* Intersection ROI (C) */}
      <div className="mb-4">
        <h4 className="mb-1 text-xs font-medium text-blue-600 dark:text-blue-400">
          交差条件 (gap≥N AND EV≥M AND margin≤{margin}) — 単勝ROI
        </h4>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="py-2 text-left text-gray-500">gap \ EV</th>
                {evLabels.map((label, i) => (
                  <th key={i} className="py-2 text-center text-gray-500">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {gaps.map((gap) => (
                <tr key={gap} className="border-b border-gray-50 dark:border-gray-800">
                  <td className="py-2 font-medium text-gray-600 dark:text-gray-400">≥{gap}</td>
                  {evs.map((ev, ei) => {
                    const entry = lookup.get(`${gap}-${ev}-${margin}`);
                    const arm = entry?.C_intersection;
                    const roi = arm?.win_roi ?? 0;
                    const count = arm?.count ?? 0;
                    const wins = arm?.wins ?? 0;
                    const pnl = arm?.pnl ?? 0;
                    const isPreset = gap === presetGap && ev === presetEv;

                    let bgClass = 'bg-gray-50 dark:bg-gray-800/30';
                    if (count > 0) {
                      if (roi >= 200) bgClass = 'bg-green-300 dark:bg-green-800/50';
                      else if (roi >= 120) bgClass = 'bg-green-200 dark:bg-green-900/40';
                      else if (roi >= 100) bgClass = 'bg-green-100 dark:bg-green-900/20';
                      else if (roi >= 80) bgClass = 'bg-yellow-50 dark:bg-yellow-900/10';
                      else bgClass = 'bg-red-50 dark:bg-red-900/10';
                    }

                    return (
                      <td key={ei} className={cn('py-2 text-center', bgClass,
                        isPreset && 'ring-2 ring-amber-500 ring-inset rounded'
                      )}>
                        {count > 0 ? (
                          <div>
                            <div className={cn('font-bold tabular-nums',
                              roi >= 100 ? 'text-green-700 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                            )}>
                              {roi.toFixed(1)}%
                            </div>
                            <div className="text-[10px] text-gray-400">{count}件/{wins}的中</div>
                            <div className={cn('text-[10px] tabular-nums', pnl >= 0 ? 'text-green-500' : 'text-red-400')}>
                              {pnl >= 0 ? '+' : ''}{pnl.toLocaleString()}
                            </div>
                          </div>
                        ) : (
                          <span className="text-gray-300">-</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Comparison: Gap-only vs EV-only vs Intersection for the preset */}
      {(() => {
        const preset = lookup.get(`${presetGap}-${presetEv}-${margin}`);
        if (!preset) return null;
        const arms = [
          { key: 'A', label: `Gap≥${presetGap} + m≤${margin}（gap単体）`, arm: preset.A_gap_margin, color: 'text-amber-600' },
          { key: 'B', label: `EV≥${presetEv} + m≤${margin}（EV単体）`, arm: preset.B_ev_margin, color: 'text-purple-600' },
          { key: 'C', label: `Gap≥${presetGap} × EV≥${presetEv} × m≤${margin}（交差）`, arm: preset.C_intersection, color: 'text-blue-600' },
        ];
        return (
          <div className="mt-2 rounded border border-gray-200 p-3 dark:border-gray-700">
            <h4 className="mb-2 text-xs font-medium text-gray-500">推奨条件の単独 vs 交差 比較</h4>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="py-1.5 text-left text-gray-500">条件</th>
                  <th className="py-1.5 text-right text-gray-500">件数</th>
                  <th className="py-1.5 text-right text-gray-500">的中率</th>
                  <th className="py-1.5 text-right text-gray-500">ROI</th>
                  <th className="py-1.5 text-right text-gray-500">P&L</th>
                  <th className="py-1.5 text-right text-gray-500">平均倍率</th>
                </tr>
              </thead>
              <tbody>
                {arms.map(({ key, label, arm, color }) => (
                  <tr key={key} className="border-b border-gray-50 dark:border-gray-800">
                    <td className={cn('py-1.5 font-medium', color)}>{label}</td>
                    <td className="py-1.5 text-right tabular-nums">{arm.count}</td>
                    <td className="py-1.5 text-right tabular-nums">{arm.win_rate}%</td>
                    <td className={cn('py-1.5 text-right tabular-nums font-bold',
                      arm.win_roi >= 100 ? 'text-green-600' : 'text-red-500'
                    )}>
                      {arm.win_roi.toFixed(1)}%
                    </td>
                    <td className={cn('py-1.5 text-right tabular-nums',
                      arm.pnl >= 0 ? 'text-green-600' : 'text-red-500'
                    )}>
                      {arm.pnl >= 0 ? '+' : ''}{arm.pnl.toLocaleString()}
                    </td>
                    <td className="py-1.5 text-right tabular-nums">{arm.avg_odds}x</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })()}
    </div>
  );
}

export default function ValueTab({ data }: { data: MlExperimentResultV2 }) {
  const placeVb = data.roi_analysis.value_bets.by_rank_gap;
  const winVb = data.roi_analysis.value_bets.win_by_rank_gap;
  const hasWinVb = winVb && winVb.length > 0;

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4 dark:border-emerald-800 dark:bg-emerald-950/20">
        <h3 className="mb-2 text-sm font-semibold text-emerald-800 dark:text-emerald-300">Value Bet戦略</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          勝利(W)モデル1位（rank_w=1）の馬に対して3条件の<strong>交差</strong>でフィルタ。
          推奨: <strong>Gap≥4 × EV≥1.3 × margin≤60</strong>（Intersection Filter, ROI 310%）。
          単勝のみ（複勝は全条件でマイナスROI）。
        </p>
      </div>

      {/* Intersection Filter Heatmap */}
      {data.intersection_grid && data.intersection_grid.length > 0 && (
        <IntersectionHeatmap grid={data.intersection_grid} />
      )}

      {/* Gap-based ROI tables */}
      <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">ランクギャップ別の回収率</h3>
        <p className="mb-3 text-xs text-gray-500">gap = 人気順位 - 独自ランク(VR)。gapが大きい = 市場より高い評価。VB判定の主軸フィルター</p>

        <div className={cn(hasWinVb ? 'grid grid-cols-1 gap-6 lg:grid-cols-2' : '')}>
          <GapTable title="Place VB (複勝)" vb={placeVb} color="blue" />
          {hasWinVb && <GapTable title="Win VB (単勝)" vb={winVb} color="emerald" />}
        </div>

        <RoiBarChart placeVb={placeVb} winVb={hasWinVb ? winVb : undefined} />
      </div>

      {/* Gap × ARd Heatmap */}
      {data.gap_ard_grid && data.gap_ard_grid.length > 0 && (
        <div className="rounded-lg border border-amber-200 p-4 dark:border-amber-800">
          <h3 className="mb-1 text-sm font-semibold text-amber-700 dark:text-amber-400">Gap × ARd ヒートマップ</h3>
          <p className="mb-3 text-xs text-gray-500">
            gap閾値とARd(AR偏差値)閾値の組み合わせ別ROI。枠線=現在プリセット(gap≥5, ARd≥50)。VB候補(VR≤3)対象
          </p>
          <div className="space-y-4">
            <div>
              <h4 className="mb-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">単勝ROI</h4>
              <GapArdHeatmap grid={data.gap_ard_grid} metric="win" />
            </div>
            <div>
              <h4 className="mb-1 text-xs font-medium text-blue-600 dark:text-blue-400">複勝ROI</h4>
              <GapArdHeatmap grid={data.gap_ard_grid} metric="place" />
            </div>
          </div>
        </div>
      )}

      {/* Gap × Margin Heatmap (raw) */}
      {data.gap_margin_grid && data.gap_margin_grid.length > 0 && (
        <GapMarginHeatmap grid={data.gap_margin_grid} />
      )}

    </div>
  );
}
