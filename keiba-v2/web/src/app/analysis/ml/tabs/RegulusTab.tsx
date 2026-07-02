'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Crown } from 'lucide-react';
import { FEATURE_LABELS, FEATURE_CATEGORIES, getFeatureCategory } from '../utils';
import type {
  RegulusModelMeta,
  ObstacleModelMetrics,
  RegulusRoiSummary,
  RegulusValueRow,
  RegulusSegmentRow,
} from '../types';

function MetricsCard({
  title,
  m,
  accent,
}: {
  title: string;
  m: ObstacleModelMetrics;
  accent: 'amber' | 'sky';
}) {
  const border = accent === 'amber' ? 'border-amber-200 dark:border-amber-800' : 'border-sky-200 dark:border-sky-800';
  const head = accent === 'amber' ? 'text-amber-600 dark:text-amber-400' : 'text-sky-600 dark:text-sky-400';
  const bigBg = accent === 'amber' ? 'bg-amber-50 dark:bg-amber-950/30' : 'bg-sky-50 dark:bg-sky-950/30';
  const bigTx = accent === 'amber' ? 'text-amber-600 dark:text-amber-400' : 'text-sky-600 dark:text-sky-400';
  return (
    <div className={cn('rounded-lg border p-4', border)}>
      <h3 className={cn('mb-3 text-sm font-semibold', head)}>{title}</h3>
      <div className="grid grid-cols-4 gap-2 text-sm">
        <div className={cn('rounded p-2 text-center', bigBg)}>
          <div className="text-xs text-gray-500">AUC</div>
          <div className={cn('text-lg font-bold', bigTx)}>{m.auc.toFixed(4)}</div>
        </div>
        <div className="rounded bg-gray-50 p-2 text-center dark:bg-gray-800/50">
          <div className="text-xs text-gray-500">ECE(cal)</div>
          <div className="font-medium">{m.ece_calibrated.toFixed(4)}</div>
        </div>
        <div className="rounded bg-gray-50 p-2 text-center dark:bg-gray-800/50">
          <div className="text-xs text-gray-500">Brier(cal)</div>
          <div className="font-medium">{m.brier_calibrated.toFixed(4)}</div>
        </div>
        <div className="rounded bg-gray-50 p-2 text-center dark:bg-gray-800/50">
          <div className="text-xs text-gray-500">Val AUC</div>
          <div className="font-medium">{m.auc_val.toFixed(4)}</div>
        </div>
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-gray-400">
        <span>best_iter {m.best_iteration}</span>
        <span>train {m.train_size.toLocaleString()} / test {m.test_size.toLocaleString()}</span>
      </div>
    </div>
  );
}

function RoiCard({ title, roi, accent }: { title: string; roi: RegulusRoiSummary; accent: 'amber' | 'sky' }) {
  const pos = roi.roi >= 100;
  const roiColor = pos ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400';
  const head = accent === 'amber' ? 'text-amber-600 dark:text-amber-400' : 'text-sky-600 dark:text-sky-400';
  return (
    <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className={cn('text-sm font-semibold', head)}>{title}</h3>
        <span className="text-[11px] text-gray-400">Top1 予測 × 単勝 100円均等</span>
      </div>
      <div className="grid grid-cols-4 gap-2 text-center text-sm">
        <div>
          <div className="text-xs text-gray-500">単勝ROI</div>
          <div className={cn('text-lg font-bold tabular-nums', roiColor)}>{roi.roi.toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">的中率</div>
          <div className="font-medium tabular-nums">{roi.hit_rate.toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">複勝内率</div>
          <div className="font-medium tabular-nums">{roi.place_rate.toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">的中時平均オッズ</div>
          <div className="font-medium tabular-nums">{roi.mean_hit_odds.toFixed(2)}</div>
        </div>
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-gray-400 tabular-nums">
        <span>{roi.n}レース / {roi.hits}的中</span>
        <span className={pos ? 'text-emerald-600' : 'text-rose-600'}>
          収支 {roi.pnl >= 0 ? '+' : ''}{roi.pnl.toLocaleString()}円
        </span>
      </div>
    </div>
  );
}

function ValueTable({ rows }: { rows: RegulusValueRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-xs text-gray-500 dark:border-gray-700">
            <th className="px-2 py-1.5 text-left">条件</th>
            <th className="px-2 py-1.5 text-right">件数</th>
            <th className="px-2 py-1.5 text-right">単勝的中</th>
            <th className="px-2 py-1.5 text-right">単勝ROI</th>
            <th className="px-2 py-1.5 text-right">複勝ROI</th>
            <th className="px-2 py-1.5 text-right">平均オッズ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const win = r.win_roi ?? 0;
            return (
              <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                <td className="px-2 py-1.5 font-medium">{r.label}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{r.n}</td>
                <td className="px-2 py-1.5 text-right tabular-nums text-gray-500">
                  {r.win_hits != null ? r.win_hits : '—'}
                  {r.win_rate != null ? ` (${r.win_rate.toFixed(0)}%)` : ''}
                </td>
                <td className={cn('px-2 py-1.5 text-right font-semibold tabular-nums',
                  win >= 100 ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-600 dark:text-gray-300')}>
                  {r.win_roi != null ? `${r.win_roi.toFixed(0)}%` : '—'}
                </td>
                <td className={cn('px-2 py-1.5 text-right tabular-nums',
                  (r.place_roi ?? 0) >= 100 ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-600 dark:text-gray-300')}>
                  {r.place_roi != null ? `${r.place_roi.toFixed(0)}%` : '—'}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-gray-500">
                  {r.mean_odds != null ? r.mean_odds.toFixed(1) : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SegmentTable({ rows }: { rows: RegulusSegmentRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-xs text-gray-500 dark:border-gray-700">
            <th className="px-2 py-1.5 text-left">条件</th>
            <th className="px-2 py-1.5 text-right">件数</th>
            <th className="px-2 py-1.5 text-right">AUC</th>
            <th className="px-2 py-1.5 text-right">Top1勝率</th>
            <th className="px-2 py-1.5 text-right">Top1複勝率</th>
            <th className="px-2 py-1.5 text-right">Top1単ROI</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
              <td className="px-2 py-1.5 font-medium">{r.segment}</td>
              <td className="px-2 py-1.5 text-right tabular-nums">{r.n}</td>
              <td className="px-2 py-1.5 text-right tabular-nums">{r.auc != null ? r.auc.toFixed(4) : '—'}</td>
              <td className="px-2 py-1.5 text-right tabular-nums">{r.top1_win_rate != null ? `${r.top1_win_rate.toFixed(1)}%` : '—'}</td>
              <td className="px-2 py-1.5 text-right tabular-nums">{r.top1_place_rate != null ? `${r.top1_place_rate.toFixed(1)}%` : '—'}</td>
              <td className={cn('px-2 py-1.5 text-right tabular-nums',
                (r.top1_win_roi ?? 0) >= 100 ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-600 dark:text-gray-300')}>
                {r.top1_win_roi != null ? `${r.top1_win_roi.toFixed(0)}%` : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function RegulusTab({ meta }: { meta?: RegulusModelMeta | null }) {
  const [showModel, setShowModel] = useState<'p' | 'w'>('p');

  if (!meta || !meta.metrics_p) {
    return <div className="py-12 text-center text-gray-400">Regulusモデルが読み込まれていません</div>;
  }

  const hasW = meta.has_win_model && !!meta.metrics_w;
  const fi = showModel === 'p'
    ? (meta.feature_importance_p ?? [])
    : (meta.feature_importance_w ?? []);
  const maxImportance = fi[0]?.importance ?? 1;
  const barColor = showModel === 'p'
    ? { top: 'bg-amber-500', high: 'bg-amber-400', base: 'bg-amber-300 dark:bg-amber-600' }
    : { top: 'bg-sky-500', high: 'bg-sky-400', base: 'bg-sky-300 dark:bg-sky-600' };

  const value = showModel === 'p' ? meta.value_analysis_p : meta.value_analysis_w;
  const segment = showModel === 'p' ? meta.segment_analysis_p : meta.segment_analysis_w;

  return (
    <div className="space-y-6">
      {/* 表示専用の第二意見バナー */}
      <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/20">
        <Crown className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
        <div className="text-xs text-amber-800 dark:text-amber-300">
          <span className="font-semibold">3歳上 芝OP以上 専用の第二意見モデル。</span>{' '}
          軌跡/CID指数を中核に「経験豊富な王者級馬の対決」を読む専門家視点。
          OP+市場はシャープなため<strong>払戻エッジは狙わず表示専用</strong>（bet_engine非配線）。
          価値は本命精度・較正・polaris(汎用)との差分シグナル。
        </div>
      </div>

      {/* 最適化ノート (存在すれば) */}
      {meta.optimization_note && (
        <details className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-800/40">
          <summary className="cursor-pointer text-xs font-medium text-gray-600 dark:text-gray-300">
            最適化ノート (v{meta.version})
          </summary>
          <p className="mt-2 whitespace-pre-line text-xs leading-relaxed text-gray-600 dark:text-gray-400">
            {meta.optimization_note}
          </p>
        </details>
      )}

      {/* 適用条件 */}
      <div className="flex flex-wrap gap-2 text-xs">
        {meta.eligibility && (
          <>
            <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
              芝 / {meta.eligibility.grade_in.join('・')} / {meta.eligibility.min_age}歳上
            </span>
          </>
        )}
        {meta.feature_groups && (
          <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
            {meta.feature_groups.length}グループ / P {meta.feature_count_p}feat・W {meta.feature_count_w ?? '—'}feat
          </span>
        )}
      </div>

      {/* メトリクス */}
      <div className={cn('grid grid-cols-1 gap-4', hasW && 'lg:grid-cols-2')}>
        <MetricsCard title="好走(P) — is_top3" m={meta.metrics_p} accent="amber" />
        {hasW && meta.metrics_w && <MetricsCard title="勝利(W) — is_win" m={meta.metrics_w} accent="sky" />}
      </div>

      {/* ROI (参考: 払戻エッジ非期待) */}
      <div>
        <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
          Top1単勝ROI <span className="font-normal text-gray-400">(参考・OP+市場はシャープで100%割れが想定)</span>
        </h3>
        <div className={cn('grid grid-cols-1 gap-4', hasW && 'lg:grid-cols-2')}>
          <RoiCard title="好走(P) 上位" roi={meta.roi_analysis_p} accent="amber" />
          {hasW && meta.roi_analysis_w && <RoiCard title="勝利(W) 上位" roi={meta.roi_analysis_w} accent="sky" />}
        </div>
      </div>

      {/* Train/Test 期間 */}
      <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
        <div className="grid grid-cols-3 gap-2 text-xs text-gray-500">
          <div>Train: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.train_period} ({meta.train_races.toLocaleString()}R)</span></div>
          <div>Val: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.val_period} ({meta.val_races}R)</span></div>
          <div>Test: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.test_period} ({meta.test_races}R)</span></div>
        </div>
      </div>

      {/* P/W 切替 */}
      <div className="flex items-center gap-3">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">詳細分析</h3>
        <div className="flex gap-1">
          <button onClick={() => setShowModel('p')}
            className={cn('rounded-md px-3 py-1 text-xs font-medium',
              showModel === 'p' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' : 'bg-gray-100 text-gray-500 dark:bg-gray-800'
            )}>好走(P)</button>
          {hasW && (
            <button onClick={() => setShowModel('w')}
              className={cn('rounded-md px-3 py-1 text-xs font-medium',
                showModel === 'w' ? 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400' : 'bg-gray-100 text-gray-500 dark:bg-gray-800'
              )}>勝利(W)</button>
          )}
        </div>
      </div>

      {/* 最適化フェーズの分析 (存在すれば) */}
      {segment && segment.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold text-gray-500">条件別成績 (グレード帯 / 期間)</h4>
          <SegmentTable rows={segment} />
        </div>
      )}
      {value && value.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold text-gray-500">
            バリューゲート別 (第二意見シグナルの馬券価値検証)
          </h4>
          <ValueTable rows={value} />
        </div>
      )}

      {/* 特徴量重要度 */}
      <div>
        <h4 className="mb-3 text-xs font-semibold text-gray-500">
          特徴量重要度 (gain, 上位20) — {showModel === 'p' ? '好走(P)' : '勝利(W)'}
        </h4>
        <div className="space-y-1.5">
          {fi.slice(0, 20).map((f, i) => {
            const pct = (f.importance / maxImportance) * 100;
            const jaLabel = FEATURE_LABELS[f.feature];
            const category = getFeatureCategory(f.feature);
            const catInfo = category ? FEATURE_CATEGORIES[category] : null;
            return (
              <div key={f.feature} className="flex items-center gap-2">
                <div className="w-6 text-right text-xs text-gray-400 tabular-nums">{i + 1}</div>
                <div className="w-52 truncate text-sm flex items-center gap-1" title={jaLabel ? `${jaLabel} (${f.feature})` : f.feature}>
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
