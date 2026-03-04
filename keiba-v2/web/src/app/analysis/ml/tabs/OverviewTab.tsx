'use client';

import { cn } from '@/lib/utils';
import { MetricCard } from '../utils';
import type { MlExperimentResultV2, MlModelResult, RegressionModelResult, HitAnalysisV2, ArdThresholdEntry, ObstacleModelMeta } from '../types';

function EceBadge({ ece }: { ece: number }) {
  if (ece < 0.03) {
    return <span className="ml-1.5 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Kelly適格</span>;
  }
  if (ece <= 0.05) {
    return <span className="ml-1.5 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">要注意</span>;
  }
  return <span className="ml-1.5 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">Kelly不適</span>;
}

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
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center text-xs text-gray-500 dark:text-gray-400">
            ECE
            {m.ece != null && <EceBadge ece={m.ece} />}
          </div>
          <div className="mt-1 text-xl font-bold tabular-nums">{m.ece != null ? m.ece.toFixed(4) : '-'}</div>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-gray-500">
        <div>Iter: <span className="font-medium text-gray-700 dark:text-gray-300">{m.best_iteration}</span></div>
        <div>Accuracy: <span className="font-medium text-gray-700 dark:text-gray-300">{(m.accuracy * 100).toFixed(1)}%</span></div>
        <div>Features: <span className="font-medium text-gray-700 dark:text-gray-300">{model.features.length}</span></div>
      </div>
    </div>
  );
}

function RegressionCard({ model }: { model: RegressionModelResult }) {
  const m = model.metrics;
  return (
    <div className="rounded-lg border border-amber-200 p-4 dark:border-amber-800">
      <h3 className="mb-3 text-sm font-semibold text-amber-700 dark:text-amber-400">
        AR (Aura Rating)
        <span className="ml-2 text-xs font-normal text-gray-400">能力予測 / 市場系除外 → AR, ARd, 複EV</span>
      </h3>
      <div className="grid grid-cols-3 gap-2">
        <MetricCard label="MAE (秒)" value={m.mae.toFixed(4)} highlight color="green" />
        <MetricCard label="相関係数" value={m.correlation.toFixed(4)} />
        <MetricCard label="BestIter" value={String(m.best_iteration)} />
      </div>
      <div className="mt-2 text-xs text-gray-500">
        Features: <span className="font-medium text-gray-700 dark:text-gray-300">{model.feature_count ?? model.features.length}</span>
        <span className="ml-3 text-gray-400">target: {model.target}</span>
      </div>
      <div className="mt-3 rounded border border-amber-100 bg-amber-50/50 p-2.5 text-xs text-gray-600 dark:border-amber-900/30 dark:bg-amber-950/10 dark:text-gray-400">
        <div className="mb-1 font-medium text-amber-700 dark:text-amber-400">ARの使われ方</div>
        <div className="space-y-0.5">
          <div><strong>AR</strong> — 勝ち馬とのタイム差を秒単位で予測（0に近いほど強い）。MAE={m.mae.toFixed(2)}秒は平均誤差</div>
          <div><strong>ARd (AR偏差値)</strong> — ARをレース内でz-score正規化（平均50, SD10）。50以上=レース平均以上の能力</div>
          <div><strong>複EV</strong> — ARの生確率 × 複勝オッズ。P(top3)はsum≈3.0の生値を使用（正規化するとsum=1.0で過小評価）</div>
          <div><strong>VBフィルター</strong> — ARd≥50をプリセット共通の足切り基準として使用</div>
        </div>
      </div>
    </div>
  );
}

function Top1Card({ label, v2, color }: { label: string; v2: HitAnalysisV2; color: string }) {
  return (
    <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
      <h4 className={cn('mb-2 text-xs font-semibold', color)}>{label}</h4>
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded bg-gray-50 p-2.5 text-center dark:bg-gray-800/50">
          <div className="text-[10px] text-gray-500">Top1 勝率</div>
          <div className={cn('mt-0.5 text-lg font-bold tabular-nums', color)}>
            {(v2.top1_win_rate * 100).toFixed(1)}%
          </div>
          <div className="text-[10px] text-gray-400">{v2.top1_wins}/{v2.top1_total}R</div>
        </div>
        <div className="rounded bg-gray-50 p-2.5 text-center dark:bg-gray-800/50">
          <div className="text-[10px] text-gray-500">Top1 好走率</div>
          <div className={cn('mt-0.5 text-lg font-bold tabular-nums', color)}>
            {(v2.top1_place_rate * 100).toFixed(1)}%
          </div>
          <div className="text-[10px] text-gray-400">{v2.top1_places}/{v2.top1_total}R</div>
        </div>
      </div>
    </div>
  );
}

function Top3DistributionBar({ v2 }: { v2: HitAnalysisV2 }) {
  const dist = v2.top3_distribution;
  const total = dist.reduce((s, d) => s + d.races, 0);
  const colors = [
    'bg-red-300 dark:bg-red-700',
    'bg-yellow-300 dark:bg-yellow-600',
    'bg-green-300 dark:bg-green-600',
    'bg-emerald-400 dark:bg-emerald-500',
  ];
  return (
    <div>
      <div className="flex h-6 w-full overflow-hidden rounded">
        {dist.map((d) => (
          d.races > 0 && (
            <div key={d.count} className={cn('flex items-center justify-center text-[10px] font-medium text-gray-800 dark:text-white', colors[d.count])}
              style={{ width: `${(d.races / total) * 100}%` }}
              title={`${d.count}頭: ${d.races}R (${d.pct}%)`}>
              {d.pct >= 5 && `${d.pct}%`}
            </div>
          )
        ))}
      </div>
      <div className="mt-1.5 flex gap-3 text-[10px] text-gray-500">
        {dist.map((d) => (
          <div key={d.count} className="flex items-center gap-1">
            <span className={cn('inline-block h-2 w-2 rounded-sm', colors[d.count])} />
            {d.count}頭: {d.races}R ({d.pct}%)
          </div>
        ))}
      </div>
    </div>
  );
}

function ObstacleModelCard({ meta }: { meta: ObstacleModelMeta }) {
  const m = meta.metrics;
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-purple-200 p-4 dark:border-purple-800">
        <h3 className="mb-3 text-sm font-semibold text-purple-700 dark:text-purple-400">
          障害モデル
          <span className="ml-2 text-xs font-normal text-gray-400">3着内予測 / 75特徴量 / {meta.version}</span>
        </h3>
        <div className="grid grid-cols-3 gap-2">
          <MetricCard label="AUC" value={m.auc.toFixed(4)} highlight color="blue" />
          <MetricCard label="Brier (cal)" value={m.brier_calibrated.toFixed(4)} />
          <MetricCard label="ECE (cal)" value={m.ece_calibrated.toFixed(4)} />
        </div>
        <div className="mt-2 grid grid-cols-4 gap-2 text-xs text-gray-500">
          <div>Iter: <span className="font-medium text-gray-700 dark:text-gray-300">{m.best_iteration}</span></div>
          <div>Accuracy: <span className="font-medium text-gray-700 dark:text-gray-300">{(m.accuracy * 100).toFixed(1)}%</span></div>
          <div>Features: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.feature_count}</span></div>
          <div>AUC(val): <span className="font-medium text-gray-700 dark:text-gray-300">{m.auc_val.toFixed(4)}</span></div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Top1Card label="障害 Top1" v2={meta.hit_analysis} color="text-purple-600 dark:text-purple-400" />
        <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
          <h4 className="mb-2 text-xs font-semibold text-purple-600 dark:text-purple-400">ROI</h4>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded bg-gray-50 p-2.5 text-center dark:bg-gray-800/50">
              <div className="text-[10px] text-gray-500">単勝ROI</div>
              <div className={cn('mt-0.5 text-lg font-bold tabular-nums', meta.roi_analysis.top1_win_roi >= 100 ? 'text-green-600' : 'text-red-500')}>
                {meta.roi_analysis.top1_win_roi.toFixed(1)}%
              </div>
              <div className="text-[10px] text-gray-400">{meta.roi_analysis.top1_bets}R</div>
            </div>
            <div className="rounded bg-gray-50 p-2.5 text-center dark:bg-gray-800/50">
              <div className="text-[10px] text-gray-500">複勝ROI</div>
              <div className={cn('mt-0.5 text-lg font-bold tabular-nums', meta.roi_analysis.top1_place_roi >= 100 ? 'text-green-600' : 'text-red-500')}>
                {meta.roi_analysis.top1_place_roi.toFixed(1)}%
              </div>
              <div className="text-[10px] text-gray-400">{meta.roi_analysis.top1_bets}R</div>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
        <div className="mb-1 text-xs font-medium text-purple-600 dark:text-purple-400">Top3 的中分布</div>
        <Top3DistributionBar v2={meta.hit_analysis} />
      </div>

      <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
        <div className="grid grid-cols-3 gap-2 text-xs text-gray-500">
          <div>Train: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.train_period} ({meta.train_races}R / {meta.train_entries.toLocaleString()}頭)</span></div>
          <div>Val: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.val_period} ({meta.val_races}R / {meta.val_entries.toLocaleString()}頭)</span></div>
          <div>Test: <span className="font-medium text-gray-700 dark:text-gray-300">{meta.test_period} ({meta.test_races}R / {meta.test_entries.toLocaleString()}頭)</span></div>
        </div>
      </div>
    </div>
  );
}

function ArdAnalysisTable({ entries }: { entries: ArdThresholdEntry[] }) {
  return (
    <div className="rounded-lg border border-amber-200 p-4 dark:border-amber-800">
      <h3 className="mb-1 text-sm font-semibold text-amber-700 dark:text-amber-400">ARd (AR偏差値) 閾値別成績</h3>
      <p className="mb-3 text-[10px] text-gray-500">全出走馬のうちARd条件を満たす馬の勝率・好走率。閾値が高いほど精鋭揃い</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-gray-500 dark:border-gray-700">
            <th className="py-2 text-left">条件</th>
            <th className="py-2 text-right">該当頭数</th>
            <th className="py-2 text-right">勝率</th>
            <th className="py-2 text-right">好走率(3着内)</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.threshold} className="border-b border-gray-50 dark:border-gray-800">
              <td className="py-2 font-medium">{'\u2265'}{e.threshold}</td>
              <td className="py-2 text-right tabular-nums text-gray-500">{e.total.toLocaleString()}</td>
              <td className="py-2 text-right tabular-nums">
                <span className={cn('font-medium', e.win_rate >= 0.15 ? 'text-green-600 dark:text-green-400' : e.win_rate >= 0.10 ? 'text-blue-600 dark:text-blue-400' : '')}>
                  {(e.win_rate * 100).toFixed(1)}%
                </span>
              </td>
              <td className="py-2 text-right tabular-nums">
                <span className={cn('font-bold', e.place_rate >= 0.45 ? 'text-green-600 dark:text-green-400' : e.place_rate >= 0.35 ? 'text-blue-600 dark:text-blue-400' : '')}>
                  {(e.place_rate * 100).toFixed(1)}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function OverviewTab({ data, obstacleModel }: { data: MlExperimentResultV2; obstacleModel?: ObstacleModelMeta | null }) {
  const ha = Array.isArray(data.hit_analysis) ? null : data.hit_analysis;
  const hitPlace = ha?.place ?? ha?.value ?? (Array.isArray(data.hit_analysis) ? data.hit_analysis : []);
  const hasV2 = !!(ha?.place_v2 ?? ha?.accuracy_v2);
  const hasWin = !!(data.models.win ?? data.models.win_value);
  const hasAura = !!(data.models.aura ?? data.models.regression_value);

  return (
    <div className="space-y-6">
      {/* Place Model */}
      <div>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">好走モデル (3着内)</h2>
        <div className="grid grid-cols-1 gap-4">
          <ModelCard title="好走(P)" model={data.models.place ?? data.models.value!} color="blue" targetLabel="市場系除外 → P%, Gap, 頭%" />
        </div>
      </div>

      {/* Win Model */}
      {hasWin && (
        <div>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">勝利モデル (1着)</h2>
          <div className="grid grid-cols-1 gap-4">
            <ModelCard title="勝利(W)" model={(data.models.win ?? data.models.win_value)!} color="emerald" targetLabel="市場系除外 → W%, EV, 頭%" />
          </div>
        </div>
      )}

      {/* Aura (AR) Model */}
      {hasAura && (
        <div>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">能力予測モデル (着差)</h2>
          <RegressionCard model={(data.models.aura ?? data.models.regression_value)!} />
        </div>
      )}

      {/* Obstacle Model */}
      {obstacleModel && (
        <div>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-purple-600 dark:text-purple-400">障害モデル (3着内)</h2>
          <ObstacleModelCard meta={obstacleModel} />
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
          <div><span className="text-gray-500">学習件数: </span><span className="font-medium">{(data.models.place ?? data.models.value)!.metrics.train_size.toLocaleString()}</span></div>
          <div><span className="text-gray-500">テスト件数: </span><span className="font-medium">{(data.models.place ?? data.models.value)!.metrics.test_size.toLocaleString()}</span></div>
        </div>
        {data.split.val && (
          <div className="mt-1 text-xs text-gray-400">3-way split: Train / Val(early stopping) / Test(純粋評価)</div>
        )}
      </div>

      {/* Hit Analysis v2 */}
      {(() => {
        const placeV2 = ha?.place_v2 ?? ha?.accuracy_v2;
        const winV2 = ha?.win_v2;
        const auraV2 = ha?.aura_v2 ?? ha?.regression_v2;
        const cardCount = 1 + (winV2 ? 1 : 0) + (auraV2 ? 1 : 0);
        return hasV2 && placeV2 ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
              <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
                Top1 成績比較
                <span className="ml-2 text-xs font-normal text-gray-400">各モデルの予測1位がどれだけ当たるか</span>
              </h3>
              <div className={cn('grid gap-3', cardCount >= 3 ? 'grid-cols-3' : cardCount === 2 ? 'grid-cols-2' : 'grid-cols-1')}>
                <Top1Card label="好走(P)" v2={placeV2} color="text-blue-600 dark:text-blue-400" />
                {winV2 && (
                  <Top1Card label="勝利(W)" v2={winV2} color="text-emerald-600 dark:text-emerald-400" />
                )}
                {auraV2 && (
                  <Top1Card label="能力(AR)" v2={auraV2} color="text-amber-600 dark:text-amber-400" />
                )}
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
              <h3 className="mb-1 text-sm font-semibold text-gray-700 dark:text-gray-300">
                Top3 的中分布
              </h3>
              <p className="mb-3 text-[10px] text-gray-500">予測上位3頭のうち何頭が3着以内に入ったかの分布</p>
              <div className="space-y-3">
                <div>
                  <div className="mb-1 text-xs font-medium text-blue-600 dark:text-blue-400">好走(P)</div>
                  <Top3DistributionBar v2={placeV2} />
                </div>
                {winV2 && (
                  <div>
                    <div className="mb-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">勝利(W)</div>
                    <Top3DistributionBar v2={winV2} />
                  </div>
                )}
                {auraV2 && (
                  <div>
                    <div className="mb-1 text-xs font-medium text-amber-600 dark:text-amber-400">能力(AR)</div>
                    <Top3DistributionBar v2={auraV2} />
                  </div>
                )}
              </div>
            </div>

            {ha?.ard_analysis && ha.ard_analysis.length > 0 && (
              <ArdAnalysisTable entries={ha.ard_analysis} />
            )}
          </div>
        ) : hitPlace.length > 0 && (
          /* Legacy fallback */
          <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
            <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
              Top-N予測の的中率
            </h3>
            <div>
              <h4 className="mb-2 text-xs font-medium text-blue-600 dark:text-blue-400">好走(P)</h4>
              <div className="grid grid-cols-3 gap-3">
                {hitPlace.map((h) => (
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
          </div>
        );
      })()}
    </div>
  );
}
