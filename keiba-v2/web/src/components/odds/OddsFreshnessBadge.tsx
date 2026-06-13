'use client';

/**
 * オッズ鮮度（as-of）バッジ
 *
 * 「表示中のオッズがいつ時点か」を一目で示す共通コンポーネント。
 * EV>1.0 判定の土台が古いオッズかもしれない事故（=損金）を防ぐ。
 *
 * - 着順が出ている（hasResults）→ 確定オッズ扱いで警告なし
 * - 速報（OB15 等で正確な時刻不明 / exact=false）→ neutral「速報」
 * - 正確な as-of あり → 「HH:MM（N分前）」を鮮度色（緑/橙/赤）で表示
 */

import { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { OddsFreshness } from '@/lib/data/rt-data-types';

interface OddsFreshnessBadgeProps {
  freshness?: OddsFreshness | null;
  /** 着順が出ている＝確定オッズ。鮮度警告を出さない */
  hasResults?: boolean;
  /** ラベル接頭辞（"オッズ" | "生成" 等） */
  prefix?: string;
  /** 橙警告のしきい値（分） */
  warnMin?: number;
  /** 赤警告（要更新）のしきい値（分） */
  staleMin?: number;
  className?: string;
}

/** N秒ごとに現在時刻(ms)を返す（"N分前"をライブ更新するため） */
function useNowMs(intervalMs = 30000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

function formatAgo(min: number): string {
  if (min < 1) return 'たった今';
  if (min < 60) return `${min}分前`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m > 0 ? `${h}時間${m}分前` : `${h}時間前`;
}

export function OddsFreshnessBadge({
  freshness,
  hasResults = false,
  prefix = 'オッズ',
  warnMin = 10,
  staleMin = 30,
  className,
}: OddsFreshnessBadgeProps) {
  const now = useNowMs();

  if (!freshness) return null;

  const base =
    'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap';

  // 確定（着順あり）→ 鮮度警告なし
  if (hasResults) {
    return (
      <span className={cn(base, 'bg-muted text-muted-foreground', className)} title="確定オッズ">
        <Clock className="h-3 w-3" />
        {prefix}
        {freshness.label ? ` ${freshness.label}` : ''} 確定
      </span>
    );
  }

  // 速報（OB15 等・正確な時刻が記録されていない）
  if (!freshness.exact || freshness.asOf == null) {
    return (
      <span
        className={cn(base, 'bg-muted text-muted-foreground', className)}
        title="速報オッズ（取得時刻は記録されていません）"
      >
        <Clock className="h-3 w-3" />
        {prefix}
        {freshness.label ? ` ${freshness.label}` : ''} 速報
      </span>
    );
  }

  const minutesAgo = Math.max(0, Math.floor((now - freshness.asOf) / 60000));
  const tone =
    minutesAgo >= staleMin
      ? 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300'
      : minutesAgo >= warnMin
        ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
        : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300';

  return (
    <span
      className={cn(base, tone, className)}
      title={`${prefix}発表 ${freshness.label ?? ''}（${formatAgo(minutesAgo)}）`}
    >
      <Clock className="h-3 w-3" />
      {prefix} {freshness.label ?? '—'}
      <span className="opacity-80">
        （{formatAgo(minutesAgo)}
        {minutesAgo >= staleMin ? '・要更新' : ''}）
      </span>
    </span>
  );
}
