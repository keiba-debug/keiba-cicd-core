'use client';

import { useState, useMemo } from 'react';
import useSWR from 'swr';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------
// Types (SoT = data3/ml/bet_template_lab.json / export_bet_template_lab.py)
// ---------------------------------------------------------------
interface MonthlyCell {
  month: string;
  fire: number;
  inv: number;
  ret: number;
  hits: number;
  roi: number;
  pnl: number;
}

interface HitDetail {
  race_id: string;
  bet_type: string;
  horses: number[];
  payout: number;
}

interface Cell {
  condition: string;
  mark_mode: string;
  template: string;
  fire: number;
  hits: number;
  hit_rate: number;
  roi: number;
  roi_train: number;
  roi_valid: number;
  median_roi: number;
  avg_roi: number;
  plus_months: string;
  plus_month_count: number;
  n_months_fired: number;
  per_day: number;
  month_inv: number;
  interval: number | null;
  roi_first_half: number;
  roi_second_half: number;
  max_dd: number;
  max_streak: number;
  total_invested: number;
  total_return: number;
  monthly: MonthlyCell[];
  hit_details: HitDetail[];
}

interface ConditionMeta {
  key: string;
  label: string;
  desc: string;
}

interface TemplateMeta {
  key: string;
  label: string;
  system: string;
  ringfenced: boolean;
  note: string;
}

interface MarkModeMeta {
  key: string;
  label: string;
}

interface LabData {
  created_at: string;
  data_source: string;
  period_start: string;
  period_end: string;
  total_races: number;
  races_with_payouts: number;
  split_date: string;
  mark_vocab: string;
  mark_modes: MarkModeMeta[];
  months: string[];
  conditions: ConditionMeta[];
  templates: TemplateMeta[];
  cells: Cell[];
}

const fetcher = (url: string) => fetch(url).then(r => r.json());

// ---------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------
const BET_LABELS: Record<string, string> = {
  tansho: '単', fukusho: '複', umaren: '馬連', wide: 'ワイド',
  umatan: '馬単', sanrenpuku: '三連複', sanrentan: '三連単',
};

function formatTicket(h: HitDetail): string {
  const sep = (h.bet_type === 'umatan' || h.bet_type === 'sanrentan') ? '→' : '-';
  return h.horses.join(sep);
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

function roiColor(roi: number): string {
  return roi >= 100 ? 'text-emerald-600' : roi >= 90 ? 'text-amber-600' : 'text-red-500';
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

const SYSTEM_BADGE: Record<string, string> = {
  当てる: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  当たる: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300',
};

function TemplateTable({ cells, templates, onSelect, selected }: {
  cells: Cell[];
  templates: TemplateMeta[];
  onSelect: (key: string) => void;
  selected: string;
}) {
  const tmap = new Map(templates.map(t => [t.key, t]));
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">系統</th>
            <th className="px-3 py-2 font-medium">テンプレ</th>
            <th className="px-3 py-2 font-medium text-right">発火</th>
            <th className="px-3 py-2 font-medium text-right">的中率</th>
            <th className="px-3 py-2 font-medium text-right">ROI(全)</th>
            <th className="px-3 py-2 font-medium text-right">中央値</th>
            <th className="px-3 py-2 font-medium text-right">+月</th>
            <th className="px-3 py-2 font-medium text-right">OOS(valid)</th>
            <th className="px-3 py-2 font-medium text-right">月投資</th>
            <th className="px-3 py-2 font-medium text-right">的中間隔</th>
            <th className="px-3 py-2 font-medium text-right">maxDD</th>
            <th className="px-3 py-2 font-medium text-right">連敗</th>
          </tr>
        </thead>
        <tbody>
          {cells.map(c => {
            const t = tmap.get(c.template);
            const stable = c.median_roi >= 100;
            return (
              <tr
                key={c.template}
                onClick={() => onSelect(c.template)}
                className={cn(
                  'border-b transition-colors cursor-pointer',
                  selected === c.template ? 'bg-blue-50 dark:bg-blue-950/30' : 'hover:bg-muted/30',
                  stable && 'bg-emerald-50/40 dark:bg-emerald-950/20',
                )}
              >
                <td className="px-3 py-2">
                  <span className={cn('inline-block px-2 py-0.5 rounded text-xs font-semibold',
                    SYSTEM_BADGE[t?.system ?? ''] ?? 'bg-gray-100 text-gray-700')}>
                    {t?.system ?? '?'}
                  </span>
                </td>
                <td className="px-3 py-2 font-medium">
                  {t?.label ?? c.template}
                  {t?.ringfenced && (
                    <span className="ml-1.5 inline-block px-1.5 py-0.5 rounded text-[10px] bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300">隔離</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{c.fire.toLocaleString()}</td>
                <td className="px-3 py-2 text-right tabular-nums">{c.hit_rate.toFixed(0)}%</td>
                <td className={cn('px-3 py-2 text-right tabular-nums font-bold', roiColor(c.roi))}>{c.roi.toFixed(0)}%</td>
                <td className={cn('px-3 py-2 text-right tabular-nums font-bold', roiColor(c.median_roi))}>
                  {c.median_roi.toFixed(0)}%{stable && ' ★'}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{c.plus_months}</td>
                <td className={cn('px-3 py-2 text-right tabular-nums', roiColor(c.roi_valid))}>{c.roi_valid.toFixed(0)}%</td>
                <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{c.month_inv.toLocaleString()}</td>
                <td className="px-3 py-2 text-right tabular-nums">{c.interval != null ? `${c.interval.toFixed(0)}R` : '—'}</td>
                <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{c.max_dd.toLocaleString()}</td>
                <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{c.max_streak}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MonthlyChart({ monthly }: { monthly: MonthlyCell[] }) {
  let cum = 0;
  const cumData = monthly.map(m => { cum += m.pnl; return { ...m, cum }; });
  const maxCum = Math.max(...cumData.map(d => Math.abs(d.cum)), 1);
  return (
    <div className="space-y-3">
      <div className="flex items-end gap-1 h-32">
        {cumData.map(d => {
          const height = Math.abs(d.cum) / maxCum * 100;
          return (
            <div key={d.month} className="flex-1 flex flex-col items-center justify-end h-full">
              <div
                className={cn('w-full rounded-t transition-all min-h-[2px]', d.cum >= 0 ? 'bg-emerald-500' : 'bg-red-400')}
                style={{ height: `${Math.max(height, 2)}%` }}
                title={`${d.month}: ${d.cum >= 0 ? '+' : ''}${d.cum.toLocaleString()}`}
              />
              <div className="mt-1 text-[9px] text-muted-foreground rotate-0">{d.month.slice(5)}</div>
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
              <th className="px-2 py-1 text-right font-medium">投資</th>
              <th className="px-2 py-1 text-right font-medium">払戻</th>
              <th className="px-2 py-1 text-right font-medium">ROI</th>
              <th className="px-2 py-1 text-right font-medium">PnL</th>
              <th className="px-2 py-1 text-right font-medium">累積</th>
            </tr>
          </thead>
          <tbody>
            {cumData.map(d => (
              <tr key={d.month} className="border-b hover:bg-muted/30">
                <td className="px-2 py-1 font-medium">{d.month}</td>
                <td className="px-2 py-1 text-right tabular-nums">{d.fire}</td>
                <td className="px-2 py-1 text-right tabular-nums">{d.hits}</td>
                <td className="px-2 py-1 text-right tabular-nums">{d.inv.toLocaleString()}</td>
                <td className="px-2 py-1 text-right tabular-nums">{d.ret.toLocaleString()}</td>
                <td className={cn('px-2 py-1 text-right tabular-nums font-semibold', roiColor(d.roi))}>{d.roi.toFixed(0)}%</td>
                <td className={cn('px-2 py-1 text-right tabular-nums', d.pnl >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                  {d.pnl >= 0 ? '+' : ''}{d.pnl.toLocaleString()}
                </td>
                <td className={cn('px-2 py-1 text-right tabular-nums font-semibold', d.cum >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                  {d.cum >= 0 ? '+' : ''}{d.cum.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function HitDetailsTable({ hits }: { hits: HitDetail[] }) {
  if (!hits.length) return <p className="text-sm text-muted-foreground">的中なし</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">#</th>
            <th className="px-3 py-2 font-medium">日付</th>
            <th className="px-3 py-2 font-medium">場</th>
            <th className="px-3 py-2 font-medium text-right">R</th>
            <th className="px-3 py-2 font-medium">券種</th>
            <th className="px-3 py-2 font-medium">買い目</th>
            <th className="px-3 py-2 font-medium text-right">払戻</th>
          </tr>
        </thead>
        <tbody>
          {hits.map((h, i) => {
            const r = parseRaceId(h.race_id);
            return (
              <tr key={`${h.race_id}-${i}`} className="border-b hover:bg-muted/30">
                <td className="px-3 py-2 text-muted-foreground">{i + 1}</td>
                <td className="px-3 py-2">
                  <a href={r.href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline dark:text-blue-400">{r.date}</a>
                </td>
                <td className="px-3 py-2 font-medium">{r.venueName}</td>
                <td className="px-3 py-2 text-right tabular-nums">{r.raceNum}</td>
                <td className="px-3 py-2 text-xs text-muted-foreground">{BET_LABELS[h.bet_type] ?? h.bet_type}</td>
                <td className="px-3 py-2 font-mono tabular-nums">{formatTicket(h)}</td>
                <td className={cn('px-3 py-2 text-right tabular-nums font-bold',
                  h.payout >= 500000 ? 'text-emerald-600' : h.payout >= 100000 ? 'text-blue-600' : '')}>
                  {h.payout.toLocaleString()}
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
export default function BetLabPage() {
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);
  const apiUrl = selectedVersion ? `/api/bet-template-lab?version=${selectedVersion}` : '/api/bet-template-lab';
  const { data, isLoading, error } = useSWR<LabData>(apiUrl, fetcher);
  const { data: versionsData } = useSWR<{ versions: string[] }>(
    '/api/bet-template-lab/versions', fetcher,
    { revalidateOnFocus: false, dedupingInterval: 300_000 },
  );
  const versions = versionsData?.versions ?? [];

  const [modeKey, setModeKey] = useState<string>('ai');
  const [condKey, setCondKey] = useState<string>('ALL (全レース)');
  const [tplKey, setTplKey] = useState<string>('wide_anchor');

  const condCells = useMemo(
    () => data ? data.cells.filter(c => c.condition === condKey && c.mark_mode === modeKey) : [],
    [data, condKey, modeKey],
  );
  const selectedCell = useMemo(
    () => condCells.find(c => c.template === tplKey) ?? condCells[0],
    [condCells, tplKey],
  );

  // ベンチマーク: ALL × wide_anchor (中央値100%トントンの基準線・現モード)
  const benchmark = useMemo(
    () => data?.cells.find(c => c.condition === 'ALL (全レース)'
      && c.template === 'wide_anchor' && c.mark_mode === modeKey),
    [data, modeKey],
  );
  // 同 (条件×テンプレ) の対モード比較 (実AI印 ⇄ composite理論)
  const counterpart = useMemo(
    () => data && selectedCell
      ? data.cells.find(c => c.condition === condKey && c.template === selectedCell.template
        && c.mark_mode !== modeKey)
      : undefined,
    [data, selectedCell, condKey, modeKey],
  );

  if (isLoading) {
    return <div className="flex h-64 items-center justify-center"><div className="text-gray-500">Loading...</div></div>;
  }
  if (error || !data || !('cells' in data)) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2">
        <div className="text-red-500">{(error as Error)?.message ?? 'No data'}</div>
        <p className="text-sm text-gray-500">python -m ml.export_bet_template_lab</p>
      </div>
    );
  }

  const selCond = data.conditions.find(c => c.key === condKey);
  const selTpl = data.templates.find(t => t.key === selectedCell?.template);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">買い方ラボ</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            『馬券力の正体』テンプレ × 勝負レース条件 / AI印→買い目→haraimodoshi実配当精算
            {' / '}{data.period_start} ~ {data.period_end} / {data.total_races.toLocaleString()}R
            <span className="ml-2 text-xs">更新: {data.created_at.split('T')[0]}</span>
          </p>
        </div>
        {versions.length > 0 && (
          <select
            value={selectedVersion ?? ''}
            onChange={(e) => setSelectedVersion(e.target.value || null)}
            className="rounded-lg border border-gray-200 bg-background px-3 py-1.5 text-sm dark:border-gray-700"
          >
            <option value="">最新</option>
            {versions.map(v => <option key={v} value={v}>v{v}</option>)}
          </select>
        )}
      </div>

      {/* 印モード トグル (C案の主眼) */}
      <div className="mb-4 rounded-xl border bg-background p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-semibold">印モード</span>
          <div className="inline-flex rounded-lg border p-0.5">
            {data.mark_modes.map(m => (
              <button
                key={m.key}
                onClick={() => setModeKey(m.key)}
                className={cn('rounded-md px-3 py-1.5 text-sm transition-colors',
                  modeKey === m.key
                    ? (m.key === 'ai' ? 'bg-blue-600 text-white' : 'bg-purple-600 text-white')
                    : 'text-muted-foreground hover:bg-muted/40')}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {modeKey === 'ai' ? (
            <><span className="font-semibold text-blue-700 dark:text-blue-400">実AI印</span> = 出走表に出る印 (markSet=2・複勝率の崖で頭数カット)。
            <span className="font-semibold"> 画面のAI印で買ったらどうなるか</span>。◎単独レースが多く、相手印が無いと三連系/ワイドは組めず発火が減る。</>
          ) : (
            <><span className="font-semibold text-purple-700 dark:text-purple-400">composite理論</span> = composite序列から ◎○▲△Ⅲ を常に上位5頭へ機械割当。
            <span className="font-semibold"> 印を最適配置したら届く上限</span>。全レースで全テンプレが発火する。両モードの差 = 印ロジック(markSet=2)の改善余地。</>
          )}
        </p>
      </div>

      {/* 2層フレーミング + 結論 */}
      <div className="mb-6 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 dark:border-emerald-800 dark:bg-emerald-950/20">
          <div className="text-sm font-semibold text-emerald-800 dark:text-emerald-300">① 本線 — トントン基盤 (死なない・楽しい)</div>
          <p className="mt-1 text-xs text-muted-foreground">
            全レース×ワイド堅実党 = 中央値ROI 100% (控除率を埋めきってトントン)。複勝堅実党 = maxDD最小・連敗短。大負けしない土台。
            <span className="font-semibold text-emerald-700 dark:text-emerald-400"> AI印のエッジは本物</span> (機械買いで控除率10-22pt埋める)。
          </p>
        </div>
        <div className="rounded-xl border border-purple-200 bg-purple-50/50 p-4 dark:border-purple-800 dark:bg-purple-950/20">
          <div className="text-sm font-semibold text-purple-800 dark:text-purple-300">② ロマン枠 — 長期期待値の望み (隔離・高分散)</div>
          <p className="mt-1 text-xs text-muted-foreground">
            軸強/荒れ × 高配当系 = 平均ROI&gt;100% だが<span className="font-semibold text-amber-700 dark:text-amber-400">中央値は負け</span> (1-2ヶ月の万馬券依存)。
            確実な金脈ではない。少額・隔離で「⚡勝負レース」に挑む遊び枠。
          </p>
        </div>
      </div>

      {/* ベンチマーク サマリ */}
      {benchmark && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard label="基準線" value="ALL×ワイド堅実党" sub="トントンのベンチ" color="purple" />
          <MetricCard label="中央値ROI" value={`${benchmark.median_roi.toFixed(0)}%`} sub={`+月 ${benchmark.plus_months}`} color={benchmark.median_roi >= 100 ? 'green' : 'amber'} />
          <MetricCard label="ROI(全期間)" value={`${benchmark.roi.toFixed(1)}%`} sub={`的中率 ${benchmark.hit_rate.toFixed(0)}%`} color="blue" />
          <MetricCard label="OOS(valid)" value={`${benchmark.roi_valid.toFixed(0)}%`} sub={`train ${benchmark.roi_train.toFixed(0)}%`} color="gray" />
          <MetricCard label="maxDD / 連敗" value={`${(benchmark.max_dd / 1000).toFixed(0)}k / ${benchmark.max_streak}`} sub="リスク" color="amber" />
          <MetricCard label="月投資" value={benchmark.month_inv.toLocaleString()} sub={`発火 ${benchmark.fire.toLocaleString()}R`} color="gray" />
        </div>
      )}

      {/* 条件セレクタ */}
      <div className="mb-4 rounded-xl border bg-background p-4">
        <h2 className="mb-2 text-sm font-semibold text-muted-foreground">勝負レース条件</h2>
        <div className="flex flex-wrap gap-2">
          {data.conditions.map(c => (
            <button
              key={c.key}
              onClick={() => setCondKey(c.key)}
              className={cn('rounded-lg border px-3 py-1.5 text-sm transition-colors',
                condKey === c.key ? 'border-blue-500 bg-blue-50 font-semibold text-blue-700 dark:bg-blue-950/40 dark:text-blue-300' : 'border-gray-200 hover:bg-muted/40 dark:border-gray-700')}
            >
              {c.label}
            </button>
          ))}
        </div>
        {selCond?.desc && <p className="mt-2 text-xs text-muted-foreground">{selCond.desc}</p>}
      </div>

      {/* テンプレ比較テーブル */}
      <div className="mb-6 rounded-xl border bg-background p-4">
        <h2 className="mb-3 text-lg font-semibold">
          テンプレ別成績 <span className="text-sm font-normal text-muted-foreground">— {condKey}</span>
        </h2>
        <TemplateTable cells={condCells} templates={data.templates} onSelect={setTplKey} selected={selectedCell?.template ?? ''} />
        <p className="mt-2 text-xs text-muted-foreground">
          ★ = 中央値ROI≥100% (月の半分以上でプラス = 安定指標)。ROI(全)は万馬券1本で跳ねるので<span className="font-semibold">中央値で判定</span>。OOS(valid)= {data.split_date}以降の実質OOS。
        </p>
      </div>

      {/* 選択テンプレ詳細 */}
      {selectedCell && (
        <>
          {/* 実AI印 ⇄ composite理論 の対比 */}
          {counterpart && (
            <div className="mb-6 rounded-xl border bg-background p-4">
              <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
                実AI印 ⇄ composite理論 — {selTpl?.label ?? selectedCell.template} / {condKey}
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs text-muted-foreground">
                      <th className="px-3 py-2 font-medium">モード</th>
                      <th className="px-3 py-2 font-medium text-right">発火</th>
                      <th className="px-3 py-2 font-medium text-right">的中率</th>
                      <th className="px-3 py-2 font-medium text-right">ROI(全)</th>
                      <th className="px-3 py-2 font-medium text-right">中央値</th>
                      <th className="px-3 py-2 font-medium text-right">OOS(valid)</th>
                      <th className="px-3 py-2 font-medium text-right">月投資</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[selectedCell, counterpart].map(c => {
                      const isAi = c.mark_mode === 'ai';
                      return (
                        <tr key={c.mark_mode} className={cn('border-b', c.mark_mode === modeKey && 'bg-muted/30 font-medium')}>
                          <td className="px-3 py-2">
                            <span className={cn('inline-block px-2 py-0.5 rounded text-xs font-semibold',
                              isAi ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300' : 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300')}>
                              {isAi ? '実AI印' : 'composite理論'}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums">{c.fire.toLocaleString()}</td>
                          <td className="px-3 py-2 text-right tabular-nums">{c.hit_rate.toFixed(0)}%</td>
                          <td className={cn('px-3 py-2 text-right tabular-nums font-bold', roiColor(c.roi))}>{c.roi.toFixed(0)}%</td>
                          <td className={cn('px-3 py-2 text-right tabular-nums font-bold', roiColor(c.median_roi))}>{c.median_roi.toFixed(0)}%</td>
                          <td className={cn('px-3 py-2 text-right tabular-nums', roiColor(c.roi_valid))}>{c.roi_valid.toFixed(0)}%</td>
                          <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{c.month_inv.toLocaleString()}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                実AI印は発火が{selectedCell.mark_mode === 'ai'
                  ? (counterpart.fire > 0 ? `${(selectedCell.fire / counterpart.fire * 100).toFixed(0)}%` : '—')
                  : (selectedCell.fire > 0 ? `${(counterpart.fire / selectedCell.fire * 100).toFixed(0)}%` : '—')}
                {' '}(理論比)。発火が落ちるのは相手印が崖でカットされ三連系/ワイドが組めないレースが出るため。
              </p>
            </div>
          )}

          <div className="mb-6 rounded-xl border bg-background p-4">
            <h2 className="mb-1 text-lg font-semibold">
              月別推移: {selTpl?.label ?? selectedCell.template}
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                [{data.mark_modes.find(m => m.key === modeKey)?.label}] 中央値 {selectedCell.median_roi.toFixed(0)}% / 平均 {selectedCell.avg_roi.toFixed(0)}%
              </span>
            </h2>
            {selTpl?.note && <p className="mb-3 text-xs text-muted-foreground">{selTpl.note}</p>}
            <MonthlyChart monthly={selectedCell.monthly} />
          </div>

          <div className="rounded-xl border bg-background p-4">
            <h2 className="mb-3 text-lg font-semibold">
              的中明細 (高配当 top{selectedCell.hit_details.length})
              <span className="ml-2 text-sm font-normal text-muted-foreground">{selectedCell.hits}的中 / 的中率 {selectedCell.hit_rate.toFixed(0)}%</span>
            </h2>
            <HitDetailsTable hits={selectedCell.hit_details} />
          </div>
        </>
      )}

      {/* データ注記 */}
      <p className="mt-6 text-xs text-muted-foreground">
        ※ {data.data_source}。flat 100円/点。印語彙={data.mark_vocab} (AI印 markSet=2 と統一・上位5頭の序列印)。
        後知恵の表示用で、正直なOOSは各セルの train/valid 分割 ({data.split_date}) を参照。
      </p>
    </div>
  );
}
