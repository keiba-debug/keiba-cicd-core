'use client';

import { useState, useMemo } from 'react';
import useSWR from 'swr';
import { cn } from '@/lib/utils';
import type { CharacterResult, CharacterMonthly } from './types';
import type { CharacterSimData } from './types';
import CharacterChart, { type TrajectorySeries } from './CharacterChart';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const CHAR_COLORS: Record<string, string> = {
  honmei: '#ef4444',          // red 本命党
  wide_kenjitsu: '#3b82f6',   // blue ワイド堅実党
  fukusho_kenjitsu: '#10b981', // green 複勝堅実党
  sanrentan_roman: '#f59e0b', // amber 三連単ロマン党
  myomi: '#a855f7',           // purple 妙味党
};

function CharTable({ chars, selected, onSelect }: {
  chars: CharacterResult[];
  selected: string | null;
  onSelect: (k: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-2 py-2 font-medium">キャラ</th>
            <th className="px-2 py-2 font-medium">テンプレ</th>
            <th className="px-2 py-2 font-medium text-right">df%</th>
            <th className="px-2 py-2 font-medium text-right">finalW</th>
            <th className="px-2 py-2 font-medium text-right">growth</th>
            <th className="px-2 py-2 font-medium text-right">maxDD</th>
            <th className="px-2 py-2 font-medium text-right">Sharpe</th>
            <th className="px-2 py-2 font-medium text-right">ruin</th>
            <th className="px-2 py-2 font-medium text-right">flatROI</th>
            <th className="px-2 py-2 font-medium text-right">median</th>
            <th className="px-2 py-2 font-medium text-right">OOS(valid)</th>
            <th className="px-2 py-2 font-medium text-right">+月</th>
            <th className="px-2 py-2 font-medium text-right">的中率</th>
            <th className="px-2 py-2 font-medium text-right">days</th>
          </tr>
        </thead>
        <tbody>
          {chars.map((c) => (
            <tr
              key={c.key}
              onClick={() => onSelect(c.key)}
              className={cn(
                'border-b cursor-pointer transition-colors hover:bg-muted/30',
                selected === c.key && 'bg-muted/40',
              )}
            >
              <td className="px-2 py-2 font-medium whitespace-nowrap">
                <span className="inline-block w-3 h-3 rounded-full mr-2 align-middle"
                  style={{ backgroundColor: CHAR_COLORS[c.key] ?? '#888' }} />
                {c.name}
                {c.ringfenced && <span className="ml-1 text-xs text-amber-600">[隔離]</span>}
                {c.odds_dependent && <span className="ml-1 text-amber-600">⚠</span>}
              </td>
              <td className="px-2 py-2 text-xs text-muted-foreground max-w-[180px] truncate"
                title={c.template_meta.map((t) => t.label).join(', ')}>
                {c.template_meta.map((t) => t.label).join(', ')}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">{(c.day_fraction * 100).toFixed(0)}%</td>
              <td className="px-2 py-2 text-right tabular-nums font-semibold">{c.final_w.toLocaleString()}</td>
              <td className={cn('px-2 py-2 text-right tabular-nums',
                c.growth_pct >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                {c.growth_pct >= 0 ? '+' : ''}{c.growth_pct}%
              </td>
              <td className="px-2 py-2 text-right tabular-nums text-red-500">{c.max_dd_pct}%</td>
              <td className={cn('px-2 py-2 text-right tabular-nums',
                c.sharpe >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                {c.sharpe.toFixed(2)}
              </td>
              <td className="px-2 py-2 text-right tabular-nums text-red-500">{c.ruin_prob_pct}%</td>
              <td className={cn('px-2 py-2 text-right tabular-nums',
                c.flat_roi_pct >= 100 ? 'text-emerald-600' : 'text-red-500')}>
                {c.flat_roi_pct}%
              </td>
              <td className={cn('px-2 py-2 text-right tabular-nums font-semibold',
                c.median_roi >= 100 ? 'text-emerald-600' : 'text-amber-600')}>
                {c.median_roi}%
              </td>
              <td className={cn('px-2 py-2 text-right tabular-nums',
                c.roi_valid >= 100 ? 'text-emerald-600' : 'text-red-500')}>
                {c.roi_valid}%
              </td>
              <td className="px-2 py-2 text-right tabular-nums text-xs">{c.plus_months}</td>
              <td className="px-2 py-2 text-right tabular-nums">{c.hit_rate}%</td>
              <td className="px-2 py-2 text-right tabular-nums text-muted-foreground">{c.bet_days}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MonthlyTable({ monthly }: { monthly: CharacterMonthly[] }) {
  if (!monthly.length) {
    return <div className="text-sm text-muted-foreground">月別データなし</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-2 py-2 font-medium">月</th>
            <th className="px-2 py-2 font-medium text-right">発火</th>
            <th className="px-2 py-2 font-medium text-right">的中</th>
            <th className="px-2 py-2 font-medium text-right">投資</th>
            <th className="px-2 py-2 font-medium text-right">払戻</th>
            <th className="px-2 py-2 font-medium text-right">ROI</th>
            <th className="px-2 py-2 font-medium text-right">PnL</th>
          </tr>
        </thead>
        <tbody>
          {monthly.map((m) => (
            <tr key={m.month} className="border-b">
              <td className="px-2 py-1.5 font-medium tabular-nums">{m.month}</td>
              <td className="px-2 py-1.5 text-right tabular-nums">{m.fire}</td>
              <td className="px-2 py-1.5 text-right tabular-nums">{m.hits}</td>
              <td className="px-2 py-1.5 text-right tabular-nums">{m.inv.toLocaleString()}</td>
              <td className="px-2 py-1.5 text-right tabular-nums">{m.ret.toLocaleString()}</td>
              <td className={cn('px-2 py-1.5 text-right tabular-nums',
                m.roi >= 100 ? 'text-emerald-600' : 'text-red-500')}>{m.roi}%</td>
              <td className={cn('px-2 py-1.5 text-right tabular-nums',
                m.pnl >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                {m.pnl >= 0 ? '+' : ''}{m.pnl.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CharacterSimPage() {
  const [version, setVersion] = useState<string | null>(null);
  const apiUrl = version ? `/api/character-simulation?version=${version}` : '/api/character-simulation';
  const { data, error, isLoading } = useSWR<CharacterSimData>(apiUrl, fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 });
  const { data: versionsData } = useSWR<{ versions: string[] }>(
    '/api/character-simulation/versions', fetcher,
    { revalidateOnFocus: false, dedupingInterval: 300_000 });
  const versions = versionsData?.versions ?? [];

  const [selectedChar, setSelectedChar] = useState<string | null>(null);

  const series: TrajectorySeries[] = useMemo(() => {
    if (!data) return [];
    return data.characters.map((c) => ({
      key: c.key, label: c.name, color: CHAR_COLORS[c.key] ?? '#888',
      base: c.eff_w0, history: c.history,
    }));
  }, [data]);

  if (isLoading) {
    return <div className="flex h-64 items-center justify-center text-gray-500">Loading...</div>;
  }
  if (error || !data) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2">
        <div className="text-red-500">{(error as Error)?.message ?? 'No data'}</div>
        <p className="text-sm text-gray-500">python -m ml.export_character_simulation</p>
      </div>
    );
  }

  const chars = data.characters;
  const sel = chars.find((c) => c.key === selectedChar) ?? chars[0] ?? null;
  const warned = chars.filter((c) => c.warnings.length > 0);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            キャラ別シミュレーション
            <span className="ml-2 text-base font-normal text-muted-foreground">v{data.sim_version}</span>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            初期 {data.initial_bankroll.toLocaleString()}円 / {data.period_start}~{data.period_end} / {data.total_races}R / {data.months.length}ヶ月
            <span className="ml-2">更新 {data.created_at.slice(0, 16).replace('T', ' ')}</span>
          </p>
        </div>
        {versions.length > 0 && (
          <select
            value={version ?? ''}
            onChange={(e) => setVersion(e.target.value || null)}
            className="rounded-lg border border-gray-200 bg-background px-3 py-1.5 text-sm dark:border-gray-700"
          >
            <option value="">Latest</option>
            {versions.map((v) => <option key={v} value={v}>v{v}</option>)}
          </select>
        )}
      </div>

      {/* 後知恵バナー */}
      <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs dark:border-amber-800 dark:bg-amber-950/30">
        <div className="font-semibold text-amber-700 dark:text-amber-400">⚠ 読み方の注意</div>
        <p className="mt-1 text-amber-900/70 dark:text-amber-200/70">{data.data_source}</p>
        {warned.map((c) => (
          <div key={c.key} className="mt-1.5 text-amber-900/70 dark:text-amber-200/70">
            <span className="font-medium">
              {c.name}{c.ringfenced ? ' [隔離]' : ''}{c.odds_dependent ? ' ⚠' : ''}
            </span>
            ：{c.warnings.join(' / ')}
          </div>
        ))}
      </div>

      {/* チャート */}
      <div className="mb-6 rounded-xl border bg-background p-4">
        <h2 className="mb-1 text-lg font-semibold">資金軌道 (初期=100 の指数)</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          各キャラ独立 bankroll の複利推移。 ringfenced (三連単ロマン) は隔離枠・補充なし。
          スケール差を吸収するため初期=100で正規化 (絶対額は下表 finalW)。
        </p>
        <CharacterChart series={series} />
      </div>

      {/* メトリクステーブル */}
      <div className="mb-6 rounded-xl border bg-background p-4">
        <h2 className="mb-3 text-lg font-semibold">キャラ比較</h2>
        <CharTable chars={chars} selected={sel?.key ?? null} onSelect={setSelectedChar} />
        <p className="mt-2 text-xs text-muted-foreground">
          finalW/growth/maxDD/Sharpe/ruin = 複利 (全期間・後知恵込み)。
          flatROI/median/OOS(valid)/+月 = flat 100円集計の検証規律。
          <span className="font-medium">median (月別ROI中央値) ≥100%</span> が万馬券に騙されない安定指標。
          ⚠=オッズ依存・[隔離]=ringfence (finalW は隔離枠基準)。 行クリックで月別。
        </p>
      </div>

      {/* 月別詳細 */}
      {sel && (
        <div className="rounded-xl border bg-background p-4">
          <h2 className="mb-3 text-lg font-semibold">
            月別推移：<span style={{ color: CHAR_COLORS[sel.key] ?? '#888' }}>{sel.name}</span>
          </h2>
          <MonthlyTable monthly={sel.monthly} />
        </div>
      )}
    </div>
  );
}
