'use client';

import useSWR from 'swr';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------
// Types (SoT = data3/ml/edge_validation.json / export_edge_validation.py)
// ---------------------------------------------------------------
interface EdgeDef {
  label: string;
  base_filter: string;
  edge_classes: string[];
  excluded_classes: string[];
  refined_filter: string;
}

interface EdgeSummary {
  n: number;
  wins: number;
  hit_rate: number;
  roi: number;
  ci_low: number;
  ci_high: number;
  k_underrate: number;
  actual_winrate: number;
  market_implied: number;
  zero_months: number;
  n_months: number;
  max_dd_pct_at_1pct: number;
}

interface ClassRow {
  cls: string;
  label: string;
  n: number;
  wins: number;
  roi: number;
  ci_low: number;
  ci_high: number;
  is_edge: boolean;
}

interface LeverRow {
  label: string;
  n: number;
  wins: number;
  roi: number;
  zero_months: number;
  is_core?: boolean;
}

interface Levers {
  odds_band: LeverRow[];
  gap: LeverRow[];
  pred_rank_w: LeverRow[];
  win_ev: LeverRow[];
}

interface SizingRow {
  level_pct: number;
  final_bank: number;
  net_pnl_pct: number;
  max_dd_pct: number;
  min_bank: number;
}

interface KellyRef {
  full_mean_pct: number;
  full_median_pct: number;
  full_max_pct: number;
  quarter_pct: number;
  half_pct: number;
}

interface MonthlyRow {
  month: string;
  n: number;
  wins: number;
  roi: number;
  pnl: number;
  cum_pnl: number;
}

interface TierRow {
  label: string;
  n: number;
  wins: number;
  roi: number;
}

interface Pick {
  race_id: string;
  umaban: number | null;
  horse_name: string;
  cls: string;
  odds: number;
  gap: number;
  win_ev: number;
  pred_rank_w: number;
  is_win: number;
  payout: number;
  finish_position: number | null;
  place_pay: number;
}

interface EdgeData {
  created_at: string;
  session: string;
  data_source: string;
  pkl_source: string;
  period_start: string;
  period_end: string;
  n_months: number;
  edge_def: EdgeDef;
  edge_summary: EdgeSummary;
  class_map: ClassRow[];
  levers: Levers;
  sizing_sim: SizingRow[];
  kelly_ref: KellyRef;
  monthly: MonthlyRow[];
  thickness_tiers: TierRow[];
  picks: Pick[];
  error?: string;
}

const fetcher = (url: string) => fetch(url).then(r => r.json());

// ---------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------
function roiColor(roi: number): string {
  return roi >= 100 ? 'text-emerald-600' : roi >= 90 ? 'text-amber-600' : 'text-red-500';
}

function fmtMonth(m: string): string {
  return m.length >= 6 ? `${m.slice(0, 4)}-${m.slice(4, 6)}` : m;
}

const VENUE_NAMES: Record<string, string> = {
  '01': '札幌', '02': '函館', '03': '福島', '04': '新潟', '05': '東京',
  '06': '中山', '07': '中京', '08': '京都', '09': '阪神', '10': '小倉',
};

function parseRaceId(id: string) {
  const y = id.slice(0, 4);
  const m = id.slice(4, 6);
  const d = id.slice(6, 8);
  const venueName = VENUE_NAMES[id.slice(8, 10)] ?? id.slice(8, 10);
  const raceNum = parseInt(id.slice(14, 16), 10);
  const date = `${y}-${m}-${d}`;
  return { date, venueName, raceNum, href: `/races-v2/${date}/${venueName}/${id}` };
}

// ---------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------
function MetricCard({ label, value, sub, color }: {
  label: string; value: string; sub?: string;
  color?: 'blue' | 'green' | 'red' | 'amber' | 'gray' | 'purple';
}) {
  const colors = {
    blue: 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30',
    green: 'border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/30',
    red: 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30',
    amber: 'border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30',
    gray: 'border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900/30',
    purple: 'border-purple-200 bg-purple-50 dark:border-purple-800 dark:bg-purple-950/30',
  };
  return (
    <div className={cn('rounded-lg border px-4 py-3', colors[color ?? 'gray'])}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-bold tabular-nums">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function LeverTable({ title, hint, rows }: { title: string; hint: string; rows: LeverRow[] }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-sm font-semibold">{title}</div>
      <div className="mb-2 text-xs text-muted-foreground">{hint}</div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th className="px-2 py-1 text-left font-medium">条件</th>
            <th className="px-2 py-1 text-right font-medium">n</th>
            <th className="px-2 py-1 text-right font-medium">的中</th>
            <th className="px-2 py-1 text-right font-medium">ROI</th>
            <th className="px-2 py-1 text-right font-medium">0月</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={cn('border-b', r.is_core && 'bg-emerald-50/60 dark:bg-emerald-950/20')}>
              <td className="px-2 py-1 font-medium">{r.label}{r.is_core && ' ★'}</td>
              <td className="px-2 py-1 text-right tabular-nums">{r.n}</td>
              <td className="px-2 py-1 text-right tabular-nums">{r.wins}</td>
              <td className={cn('px-2 py-1 text-right tabular-nums font-semibold', roiColor(r.roi))}>{r.roi.toFixed(0)}%</td>
              <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">{r.zero_months}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EdgeMonthlyChart({ monthly }: { monthly: MonthlyRow[] }) {
  const maxCum = Math.max(...monthly.map(d => Math.abs(d.cum_pnl)), 1);
  return (
    <div className="space-y-3">
      <div className="flex h-32 items-end gap-1">
        {monthly.map(d => {
          const height = Math.abs(d.cum_pnl) / maxCum * 100;
          return (
            <div key={d.month} className="flex h-full flex-1 flex-col items-center justify-end">
              <div
                className={cn('w-full rounded-t min-h-[2px]', d.cum_pnl >= 0 ? 'bg-emerald-500' : 'bg-red-400')}
                style={{ height: `${Math.max(height, 2)}%` }}
                title={`${fmtMonth(d.month)}: 累積${d.cum_pnl >= 0 ? '+' : ''}${d.cum_pnl}u`}
              />
              <div className="mt-1 text-[9px] text-muted-foreground">{d.month.slice(4, 6)}</div>
            </div>
          );
        })}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-muted-foreground">
              <th className="px-2 py-1 text-left font-medium">月</th>
              <th className="px-2 py-1 text-right font-medium">発火</th>
              <th className="px-2 py-1 text-right font-medium">的中</th>
              <th className="px-2 py-1 text-right font-medium">ROI</th>
              <th className="px-2 py-1 text-right font-medium">PnL(1u)</th>
              <th className="px-2 py-1 text-right font-medium">累積</th>
            </tr>
          </thead>
          <tbody>
            {monthly.map(d => (
              <tr key={d.month} className="border-b hover:bg-muted/30">
                <td className="px-2 py-1 font-medium">{fmtMonth(d.month)}</td>
                <td className="px-2 py-1 text-right tabular-nums">{d.n}</td>
                <td className="px-2 py-1 text-right tabular-nums">{d.wins}</td>
                <td className={cn('px-2 py-1 text-right tabular-nums font-semibold', roiColor(d.roi))}>{d.roi.toFixed(0)}%</td>
                <td className={cn('px-2 py-1 text-right tabular-nums', d.pnl >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                  {d.pnl >= 0 ? '+' : ''}{d.pnl.toFixed(1)}
                </td>
                <td className={cn('px-2 py-1 text-right tabular-nums font-semibold', d.cum_pnl >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                  {d.cum_pnl >= 0 ? '+' : ''}{d.cum_pnl.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SectionCard({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="mb-6 rounded-lg border bg-card p-4">
      <h2 className="text-base font-bold">{title}</h2>
      {sub && <p className="mt-0.5 mb-3 text-xs text-muted-foreground">{sub}</p>}
      {!sub && <div className="mb-3" />}
      {children}
    </section>
  );
}

function PicksTable({ picks }: { picks: Pick[] }) {
  const sorted = [...picks].reverse(); // 新しい順
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-2 py-2 font-medium">#</th>
            <th className="px-2 py-2 font-medium">日付</th>
            <th className="px-2 py-2 font-medium">場</th>
            <th className="px-2 py-2 text-right font-medium">R</th>
            <th className="px-2 py-2 text-right font-medium">馬番</th>
            <th className="px-2 py-2 font-medium">馬名</th>
            <th className="px-2 py-2 font-medium">クラス</th>
            <th className="px-2 py-2 text-right font-medium">オッズ</th>
            <th className="px-2 py-2 text-right font-medium">gap</th>
            <th className="px-2 py-2 text-right font-medium">winEV</th>
            <th className="px-2 py-2 text-center font-medium">着順</th>
            <th className="px-2 py-2 text-center font-medium">単勝</th>
            <th className="px-2 py-2 text-right font-medium">単勝配当</th>
            <th className="px-2 py-2 text-right font-medium">複勝配当</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((p, i) => {
            const r = parseRaceId(p.race_id);
            return (
              <tr
                key={`${p.race_id}-${p.umaban}`}
                className={cn('border-b hover:bg-muted/30', p.is_win === 1 && 'bg-emerald-50/60 dark:bg-emerald-950/20')}
              >
                <td className="px-2 py-1.5 text-muted-foreground tabular-nums">{i + 1}</td>
                <td className="px-2 py-1.5">
                  <a href={r.href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline dark:text-blue-400">{r.date}</a>
                </td>
                <td className="px-2 py-1.5 font-medium">{r.venueName}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{r.raceNum}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{p.umaban ?? '—'}</td>
                <td className="px-2 py-1.5">{p.horse_name}</td>
                <td className="px-2 py-1.5 text-xs text-muted-foreground">{p.cls}</td>
                <td className="px-2 py-1.5 text-right tabular-nums font-semibold">{p.odds.toFixed(1)}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{p.gap}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{p.win_ev.toFixed(2)}</td>
                <td className="px-2 py-1.5 text-center">
                  {p.finish_position == null
                    ? <span className="text-muted-foreground">—</span>
                    : <span className={cn('font-semibold tabular-nums',
                        p.finish_position === 1 ? 'text-emerald-600'
                          : p.finish_position <= 3 ? 'text-blue-600'
                            : 'text-muted-foreground')}>{p.finish_position}着</span>}
                </td>
                <td className="px-2 py-1.5 text-center">
                  {p.is_win === 1
                    ? <span className="font-bold text-emerald-600">的中</span>
                    : <span className="text-muted-foreground">✗</span>}
                </td>
                <td className={cn('px-2 py-1.5 text-right tabular-nums', p.payout > 0 ? 'font-bold text-emerald-600' : 'text-muted-foreground')}>
                  {p.payout > 0 ? p.payout.toLocaleString() : '—'}
                </td>
                <td className={cn('px-2 py-1.5 text-right tabular-nums', p.place_pay > 0 ? 'font-semibold text-blue-600' : 'text-muted-foreground')}>
                  {p.place_pay > 0 ? p.place_pay.toLocaleString() : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------
export default function EdgeValidationPage() {
  const { data, isLoading, error } = useSWR<EdgeData>('/api/edge-validation', fetcher);

  if (isLoading) {
    return <div className="flex h-64 items-center justify-center"><div className="text-gray-500">Loading...</div></div>;
  }
  if (error || !data || !('edge_summary' in data) || data.error) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2">
        <div className="text-red-500">{data?.error ?? (error as Error)?.message ?? 'No data'}</div>
        <p className="text-sm text-gray-500">python -m ml.export_edge_validation</p>
      </div>
    );
  }

  const es = data.edge_summary;
  const def = data.edge_def;
  const kr = data.kelly_ref;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      {/* Header */}
      <div className="mb-2">
        <h1 className="text-2xl font-bold">エッジ検証 — {def.label}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {fmtMonth(data.period_start)} 〜 {fmtMonth(data.period_end)}（{data.n_months}ヶ月OOS・実払戻）
          ／ {data.session} ／ 更新 {data.created_at.slice(0, 16).replace('T', ' ')}
        </p>
      </div>

      {/* in-sample caveat banner */}
      <div className="mb-5 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
        ⚠ これは df_test（{data.n_months}ヶ月OOS）上で精密化した <b>in-sample</b> の結果。複数レバーから最良を選んだ
        選択バイアスが残るため、真のforward性能はこれより低い見込み。毎週 <code>export_edge_validation</code> を回して
        forward実績を貯め、フラクショナル配分（1%以下スタート）で運用する前提。
      </div>

      {/* edge summary cards */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard label="ROI（実払戻）" value={`${es.roi.toFixed(1)}%`} sub={`CI95 [${es.ci_low.toFixed(0)}-${es.ci_high.toFixed(0)}]`} color={es.ci_low >= 100 ? 'green' : 'amber'} />
        <MetricCard label="市場の過小評価" value={`${es.k_underrate.toFixed(2)}x`} sub="エッジの源泉" color="purple" />
        <MetricCard label="実勝率 vs 市場" value={`${es.actual_winrate.toFixed(1)}%`} sub={`市場implied ${es.market_implied.toFixed(1)}%`} color="blue" />
        <MetricCard label="的中率" value={`${es.hit_rate.toFixed(1)}%`} sub={`${es.wins} / ${es.n} 件`} color="gray" />
        <MetricCard label="ゼロ的中月" value={`${es.zero_months} / ${es.n_months}`} sub="高分散の証" color={es.zero_months <= 3 ? 'gray' : 'amber'} />
        <MetricCard label="maxDD (1%/bet)" value={`${es.max_dd_pct_at_1pct.toFixed(0)}%`} sub="固定額配分" color="gray" />
      </div>

      {/* edge definition */}
      <div className="mb-6 rounded-lg border bg-muted/30 px-4 py-3 text-xs">
        <div className="font-semibold text-sm mb-1">採用条件（全て事前オッズで判定可＝ライブ運用可）</div>
        <div className="space-y-0.5 font-mono">
          <div><span className="text-muted-foreground">base　：</span>{def.base_filter}</div>
          <div><span className="text-muted-foreground">class ：</span>採用 {def.edge_classes.join(' / ')}　×　除外 {def.excluded_classes.join(' / ')}</div>
          <div><span className="text-muted-foreground">refine：</span>{def.refined_filter}</div>
        </div>
      </div>

      {/* class map (edge geography) */}
      <SectionCard title="エッジ地図 — gap≥5単勝のクラス別ROI" sub="新馬=モデルも盲目／OP=市場シャープ → 除外。中情報クラス（未勝利・条件・重賞）がsweet spot。">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="px-3 py-2 font-medium">クラス</th>
                <th className="px-3 py-2 text-right font-medium">n</th>
                <th className="px-3 py-2 text-right font-medium">的中</th>
                <th className="px-3 py-2 text-right font-medium">ROI</th>
                <th className="px-3 py-2 text-right font-medium">CI95%</th>
                <th className="px-3 py-2 text-center font-medium">採用</th>
              </tr>
            </thead>
            <tbody>
              {data.class_map.map(c => (
                <tr key={c.cls} className={cn('border-b', c.is_edge && 'bg-emerald-50/40 dark:bg-emerald-950/20')}>
                  <td className="px-3 py-2 font-medium">{c.label}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{c.n}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{c.wins}</td>
                  <td className={cn('px-3 py-2 text-right tabular-nums font-bold', roiColor(c.roi))}>{c.roi.toFixed(1)}%</td>
                  <td className="px-3 py-2 text-right tabular-nums text-xs text-muted-foreground">[{c.ci_low.toFixed(0)}-{c.ci_high.toFixed(0)}]</td>
                  <td className="px-3 py-2 text-center">{c.is_edge ? '✅' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {/* refinement levers */}
      <SectionCard title="レバー感度（参考・各条件の単独の効き）" sub="★committed は broad（全オッズ3クラス）★。下のスイープで「絞るとROIは上がるが分散も悪化」が見えるが、S175 監査で odds帯絞りは best-of-search の過学習（P(null max≥218%)=0.0625＝ノイズと区別不能）と判明し棄却。採用は絞らない broad。">
        <div className="grid gap-3 sm:grid-cols-2">
          <LeverTable title="オッズ帯" hint="★15-30倍に絞ると218%まで上がるが S175で過学習棄却★。committed=全オッズ(broad 130%)" rows={data.levers.odds_band} />
          <LeverTable title="gap閾値" hint="上げるとROI↑だが0月も増える（分散悪化）＝同じく絞りすぎ注意" rows={data.levers.gap} />
          <LeverTable title="pred_rank_w" hint="モデル本命ほど的中率↑（だが薄い）" rows={data.levers.pred_rank_w} />
          <LeverTable title="win_ev（モデルEV）" hint="≥1.0は live選定のサニティゲート（headline broad には未適用）" rows={data.levers.win_ev} />
        </div>
      </SectionCard>

      {/* sizing sim */}
      <SectionCard title="配分シミュ — 固定額（哲学§5準拠・オッズ非依存）" sub={`採用バケット ${es.n}件を時系列で。1点=初期bankrollの一定%（絶対額固定・bankrollでもオッズでも動かさない）。`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="px-3 py-2 font-medium">1点の額</th>
                <th className="px-3 py-2 text-right font-medium">最終bank</th>
                <th className="px-3 py-2 text-right font-medium">純損益</th>
                <th className="px-3 py-2 text-right font-medium">maxDD</th>
                <th className="px-3 py-2 text-right font-medium">min_bank</th>
              </tr>
            </thead>
            <tbody>
              {data.sizing_sim.map(s => (
                <tr key={s.level_pct} className={cn('border-b', s.level_pct === 1.0 && 'bg-emerald-50/40 dark:bg-emerald-950/20')}>
                  <td className="px-3 py-2 font-medium tabular-nums">{s.level_pct}%/bet{s.level_pct === 1.0 && ' ★推奨'}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.final_bank.toFixed(2)}x</td>
                  <td className={cn('px-3 py-2 text-right tabular-nums font-semibold', s.net_pnl_pct >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                    {s.net_pnl_pct >= 0 ? '+' : ''}{s.net_pnl_pct.toFixed(0)}%
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-red-500">{s.max_dd_pct.toFixed(0)}%</td>
                  <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{s.min_bank.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          参考（ケリーは配分には不採用・水準の上限サニティのみ）：フルケリー平均 {kr.full_mean_pct}% →
          <b> 1%/bet ≈ 1/4ケリー</b>・<b>2%/bet ≈ 1/2ケリー</b>。固定額1〜2%は破産安全圏。
        </p>
      </SectionCard>

      {/* monthly */}
      <SectionCard title="月別推移 — 採用バケット（1点1u固定）" sub="累積PnL（u単位）。3ヶ月のゼロ的中（高分散）に耐える前提。">
        <EdgeMonthlyChart monthly={data.monthly} />
      </SectionCard>

      {/* thickness tiers */}
      <SectionCard title="評価ベースの厚み候補（信号強度別ROI・哲学§5 OK）" sub="オッズでなく信号強度で厚みをつける軸。強信号ほどROI高い。">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="px-3 py-2 font-medium">ティア</th>
                <th className="px-3 py-2 text-right font-medium">n</th>
                <th className="px-3 py-2 text-right font-medium">的中</th>
                <th className="px-3 py-2 text-right font-medium">ROI</th>
              </tr>
            </thead>
            <tbody>
              {data.thickness_tiers.map((t, i) => (
                <tr key={i} className="border-b hover:bg-muted/30">
                  <td className="px-3 py-2 font-medium">{t.label}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{t.n}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{t.wins}</td>
                  <td className={cn('px-3 py-2 text-right tabular-nums font-bold', roiColor(t.roi))}>{t.roi.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {/* picks list — 対象機会の明細 */}
      <SectionCard title={`対象リスト — 採用バケット全${data.picks.length}件`} sub="該当した単勝機会の明細（新しい順）。日付クリックでレースページへ。着順の青=複勝圏(2-3着)。複勝配当は事前複勝最低オッズ×100=最低保証(確定払戻はこれ以上)。">
        <PicksTable picks={data.picks} />
      </SectionCard>

      <p className="mt-4 text-xs text-muted-foreground">
        SoT: <code>data3/ml/edge_validation.json</code> ／ 生成: <code>python -m ml.export_edge_validation</code> ／
        正本: <code>docs/market_calibration_edge_map.md</code>
      </p>
    </div>
  );
}
