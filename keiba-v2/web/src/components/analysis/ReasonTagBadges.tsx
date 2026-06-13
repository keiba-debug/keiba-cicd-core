import type { ReasonTag } from '@/lib/data/predictions-reader';
import { cn } from '@/lib/utils';

/**
 * E-005 理由タグ（接戦◎/出遅れ注意/低信頼）— 表示専用バッジ。
 *
 * 買う/買わない・スコアには一切影響しない（買い目層への介入は ROI を動かさない/逆効果と
 * 実証済みのため、シグナルの居場所は表示・運用）。Python ml/strategies/reason_tags.py が生成。
 *
 * 注目馬リスト（vb-table）と出馬表（HorseEntryTable）の両方で共用。
 * 内部は inline-flex gap-1。呼び出し側の文脈で外側マージンが要るときは className で渡す。
 */
export function ReasonTagBadges({ tags, className }: { tags?: ReasonTag[]; className?: string }) {
  if (!tags || tags.length === 0) return null;
  const cls = (level: ReasonTag['level']) =>
    level === 'good' ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300' :
    level === 'caution' ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' :
    'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300';
  return (
    <span className={cn('inline-flex items-center gap-1', className)}>
      {tags.map((t) => (
        <span
          key={t.type}
          className={cn(
            'px-1 py-0.5 rounded text-[9px] font-bold whitespace-nowrap',
            cls(t.level),
            t.low_confidence && 'opacity-60',
          )}
          title={t.detail + (t.low_confidence ? '（低信頼: 根拠データが小標本）' : '')}
        >
          {t.label}
        </span>
      ))}
    </span>
  );
}
