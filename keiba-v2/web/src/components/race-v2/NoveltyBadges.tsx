/**
 * 未知数度バッジ (Session 119)
 *
 * バックテスト結果（2025-05〜2026-04, 46K entries）で各フラグ別ROI:
 *  - long_layoff (96.5%) / jockey_change (87.0%) → 影響少, info色
 *  - career_short (59.1%) / first_venue (58.3%) → 中, warning色
 *  - first_distance (56.7%) → 強, orange
 *  - first_surface (52.0%) → 最強の足切り材料, red
 *
 * VBフィルタは first_surface=1 / first_distance=1 / novelty_score>3 の馬を除外。
 */
import { cn } from '@/lib/utils';

export interface NoveltyFlags {
  novelty_score?: number;
  novelty_career_short?: number;
  novelty_first_surface?: number;
  novelty_first_distance?: number;
  novelty_first_venue?: number;
  novelty_long_layoff?: number;
  novelty_jockey_change?: number;
}

interface BadgeDef {
  key: keyof NoveltyFlags;
  label: string;
  full: string;
  color: string;
}

// バックテスト ROI の悪い順に並べる（左ほど危険信号が強い）
const BADGES: BadgeDef[] = [
  {
    key: 'novelty_first_surface',
    label: '初芝/ダ',
    full: '初めての芝 or ダート (VB ROI 52%)',
    color: 'bg-red-500 text-white',
  },
  {
    key: 'novelty_first_distance',
    label: '初距',
    full: '初距離帯 (±200m経験なし, VB ROI 57%)',
    color: 'bg-orange-500 text-white',
  },
  {
    key: 'novelty_first_venue',
    label: '初場',
    full: '初コース (VB ROI 58%)',
    color: 'bg-amber-400 text-amber-950',
  },
  {
    key: 'novelty_career_short',
    label: '少走',
    full: 'キャリア3走以下 (VB ROI 59%)',
    color: 'bg-yellow-300 text-yellow-900',
  },
  {
    key: 'novelty_jockey_change',
    label: '乗替',
    full: '騎手乗替 (VB ROI 87% — 影響軽微)',
    color: 'bg-sky-200 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200',
  },
  {
    key: 'novelty_long_layoff',
    label: '休',
    full: '長期休養 140日+ (VB ROI 96% — 影響軽微)',
    color: 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
  },
];

interface Props {
  entry: NoveltyFlags;
  /** "compact" = アイコン的な短縮表示, "full" = ラベル付き */
  variant?: 'compact' | 'full';
  /** trueなら影響軽微フラグ(乗替/休)も表示 */
  showMild?: boolean;
  className?: string;
}

export function NoveltyBadges({
  entry,
  variant = 'compact',
  showMild = false,
  className,
}: Props) {
  const active = BADGES.filter((b) => {
    if (!showMild && (b.key === 'novelty_jockey_change' || b.key === 'novelty_long_layoff')) {
      return false;
    }
    return Number(entry[b.key]) === 1;
  });

  if (active.length === 0) return null;

  return (
    <div className={cn('flex flex-wrap gap-0.5', className)}>
      {active.map((b) => (
        <span
          key={b.key}
          title={b.full}
          className={cn(
            'inline-flex items-center justify-center rounded font-bold leading-none whitespace-nowrap',
            variant === 'compact'
              ? 'px-1 py-0.5 text-[10px]'
              : 'px-1.5 py-0.5 text-xs',
            b.color,
          )}
        >
          {b.label}
        </span>
      ))}
    </div>
  );
}

/**
 * 単一の合計スコアバッジ (novelty_score 0-6)
 * リスト表示などで小さく出したい時用
 */
export function NoveltyScoreBadge({
  score,
  className,
}: {
  score?: number;
  className?: string;
}) {
  const s = Number(score) || 0;
  if (s === 0) return null;
  const color =
    s >= 4
      ? 'bg-red-500 text-white'
      : s === 3
        ? 'bg-orange-400 text-orange-950'
        : s === 2
          ? 'bg-amber-300 text-amber-900'
          : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200';
  return (
    <span
      title={`未知数度合計 ${s}/6 (4以上はVB候補から自動除外)`}
      className={cn(
        'inline-flex items-center justify-center rounded px-1 py-0.5 text-[10px] font-bold leading-none',
        color,
        className,
      )}
    >
      未{s}
    </span>
  );
}
