'use client';

/**
 * 本命EV単 検証ページ (Session 178・スリーブ専用検証)
 *
 * 自動投票の ★本命EV単スリーブ★ (= 推奨馬券プリセット tansho_ippon) のバックテスト成績。
 * データ源 = bankroll_simulation.json (simulate_strategy_redesign.py / /api/simulation/result)。
 * ★現行シミュ(v2.3-s164)を表示★。旧称「単勝一本」/旧 polaris 2.1b の ROI156% は更新前の数値。
 * 逆張り単(gap)の /analysis/edge-validation に対応する、本命EV単専用の検証先。
 */
import { useMemo } from 'react';
import { useSimulationResult } from '@/hooks/useSimulationResult';
import { cn } from '@/lib/utils';
import type { SimulationResult } from '@/app/analysis/simulation/types';

const PRESET = 'tansho_ippon';

function MetricCard({ label, value, sub, color }: {
  label: string; value: string; sub?: string;
  color?: 'blue' | 'green' | 'red' | 'amber' | 'gray' | 'sky';
}) {
  const colors = {
    blue: 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30',
    green: 'border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/30',
    red: 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30',
    amber: 'border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30',
    gray: 'border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900/30',
    sky: 'border-sky-200 bg-sky-50 dark:border-sky-800 dark:bg-sky-950/30',
  };
  return (
    <div className={cn('rounded-lg border px-4 py-3', colors[color ?? 'gray'])}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-bold tabular-nums">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function roiColor(roi: number): string {
  return roi >= 100 ? 'text-emerald-600' : roi >= 90 ? 'text-amber-600' : 'text-red-500';
}
function growthColor(p: number): string {
  return p > 0 ? 'text-emerald-600' : p < 0 ? 'text-red-500' : 'text-muted-foreground';
}

export default function HonmeiEvValidationPage() {
  const { data, isLoading, error } = useSimulationResult();

  const rows = useMemo<SimulationResult[]>(
    () => (data?.results ?? []).filter(r => r.preset === PRESET),
    [data],
  );
  // 代表 = flat500 (flat 500円/点・最も素直なベンチ)、無ければ先頭
  const ref = useMemo(
    () => rows.find(r => r.budget_label === 'flat500') ?? rows[0],
    [rows],
  );

  if (isLoading) {
    return <div className="flex h-64 items-center justify-center text-gray-500">Loading...</div>;
  }
  if (error || !data || rows.length === 0 || !ref) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2">
        <div className="text-red-500">本命EV単の検証データがありません</div>
        <p className="text-sm text-gray-500">python -m ml.simulate_strategy_redesign</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      {/* Header */}
      <div className="mb-2">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-sky-500 text-white text-sm font-bold">本命EV単</span>
          <h1 className="text-2xl font-bold">検証 — AI本命×市場過小評価×高EVの単勝</h1>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          自動投票の本命EV単スリーブ（推奨馬券プリセット tansho_ippon と同条件）のバックテスト成績。
          単勝1点・haraimodoshi 実払戻精算。
        </p>
      </div>

      {/* 出どころ banner */}
      <div className="mb-6 rounded-lg border border-sky-200 bg-sky-50/50 px-4 py-2 text-xs dark:border-sky-800 dark:bg-sky-950/20">
        モデル <span className="font-semibold">{data.model_version ?? '—'}</span>
        {' / '}更新 {data.created_at ? data.created_at.split('T')[0] : '—'}
        {' / '}初期bankroll ¥{data.initial_bankroll.toLocaleString()}
        <span className="ml-2 text-muted-foreground">
          ※ 現行シミュの値。旧「単勝一本」/ polaris 2.1b の ROI156% は更新前の数値です。
        </span>
      </div>

      {/* 採用条件 */}
      <div className="mb-6 rounded-lg border bg-muted/30 px-4 py-3 text-xs">
        <div className="font-semibold text-sm mb-1">採用条件（全て事前オッズで判定可＝ライブ運用可）</div>
        <div className="font-mono">
          rank_w=1（AI本命） ∧ win_vb_gap≥3（市場の過小評価） ∧ win_ev≥1.3（単勝EV）
          ∧ predicted_margin≤60（接戦＝勝ち切れる） → 単勝1点 / 1レース1点
        </div>
      </div>

      {/* Headline metrics (戦略レベル・予算非依存) */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard label="Flat ROI（実払戻）" value={`${ref.flat_roi.toFixed(1)}%`} sub="100円/点の素ROI" color={ref.flat_roi >= 100 ? 'green' : 'amber'} />
        <MetricCard label="的中率" value={`${(ref.win_hit_rate ?? 0).toFixed(1)}%`} sub={`${ref.total_bets} 件`} color="blue" />
        <MetricCard label="連敗（最大）" value={`${ref.max_loss_streak}`} sub="高分散の証" color="amber" />
        <MetricCard label="maxDD (flat500)" value={`${ref.max_dd.toFixed(0)}%`} sub="固定額" color="gray" />
        <MetricCard label="Calmar (flat500)" value={`${ref.calmar.toFixed(2)}`} sub="成長/DD" color={ref.calmar >= 0 ? 'sky' : 'red'} />
        <MetricCard label="bet日数" value={`${ref.bet_days}`} sub={`勝${ref.win_days}/負${ref.lose_days}`} color="gray" />
      </div>

      {/* 予算別比較 */}
      <div className="mb-6 rounded-xl border bg-background p-4">
        <h2 className="mb-1 text-lg font-semibold">配分別の成績</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          Flat ROI（素の期待値）は配分に依らず一定。比率を上げるほど成長期待は増えるが
          <span className="font-semibold">maxDD・連敗も悪化</span>（高分散エッジは小さめの比率＋flat が安全）。
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="px-3 py-2 font-medium">配分</th>
                <th className="px-3 py-2 text-right font-medium">最終bankroll</th>
                <th className="px-3 py-2 text-right font-medium">成長率</th>
                <th className="px-3 py-2 text-right font-medium">Flat ROI</th>
                <th className="px-3 py-2 text-right font-medium">maxDD</th>
                <th className="px-3 py-2 text-right font-medium">Calmar</th>
                <th className="px-3 py-2 text-right font-medium">Sharpe</th>
                <th className="px-3 py-2 text-right font-medium">最大連敗</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.budget_label} className={cn('border-b', r.budget_label === 'flat500' && 'bg-sky-50/40 dark:bg-sky-950/20')}>
                  <td className="px-3 py-2 font-medium">
                    {r.budget_label}{r.budget_label === 'flat500' && ' ★'}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">¥{r.final_bankroll.toLocaleString()}</td>
                  <td className={cn('px-3 py-2 text-right tabular-nums font-bold', growthColor(r.roi_pct))}>
                    {r.roi_pct >= 0 ? '+' : ''}{r.roi_pct.toFixed(1)}%
                  </td>
                  <td className={cn('px-3 py-2 text-right tabular-nums', roiColor(r.flat_roi))}>{r.flat_roi.toFixed(1)}%</td>
                  <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{r.max_dd.toFixed(0)}%</td>
                  <td className={cn('px-3 py-2 text-right tabular-nums', r.calmar >= 0 ? 'text-emerald-600' : 'text-red-500')}>{r.calmar.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{r.sharpe.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{r.max_loss_streak}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          ★ = flat500（flat 500円/点）。自動投票スリーブは「残高×比率」の比例配分（破産ガード内包）。
        </p>
      </div>

      {/* footer note */}
      <p className="text-xs text-muted-foreground">
        ※ SoT: <code>data3/ml/bankroll_simulation.json</code> ／ 生成: <code>python -m ml.simulate_strategy_redesign</code>。
        逆張り単の検証は <a href="/analysis/edge-validation" className="text-sky-600 hover:underline">エッジ検証ページ</a>。
      </p>
    </div>
  );
}
